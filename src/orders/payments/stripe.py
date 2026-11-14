"""
Stripe payment integration.

Credentials are loaded only from the PaymentCredentials model (DB). Store your
Stripe secret key via the staff API: POST /api/orders/payment-credentials/ with
provider=stripe, environment=sandbox|live, and private_key=sk_...
"""

import logging

from orders.models import OrderPayment, PaymentCredentials, PaymentProvider, PaymentStatus

logger = logging.getLogger(__name__)


class StripeAPI:
    def __init__(self):
        self.credentials = self._get_latest_credentials()
        if not self.credentials:
            raise ValueError("No active Stripe credentials found")

        # Decrypt only when building the provider client; never persisted or returned
        self.secret_key = self.credentials.get_private_key()
        if not self.secret_key:
            raise ValueError("Stripe secret key is missing (store it as the private key).")

        try:
            import stripe  # type: ignore
        except Exception as e:
            raise ImportError(
                "Stripe SDK not installed. Add `stripe` to requirements to use this integration."
            ) from e

        self.stripe = stripe
        self.stripe.api_key = self.secret_key

    def _get_latest_credentials(self):
        """Load active Stripe credentials from DB (PaymentCredentials)."""
        try:
            return (
                PaymentCredentials.objects.filter(
                    provider=PaymentProvider.STRIPE,
                    is_active=True,
                )
                .latest("created_at")
            )
        except PaymentCredentials.DoesNotExist:
            return None

    def create_checkout_session(self, payment: OrderPayment, success_url: str, cancel_url: str):
        """
        Creates a Stripe Checkout Session and stores the session URL + id on OrderPayment.
        """
        try:
            session = self.stripe.checkout.Session.create(
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                line_items=[
                    {
                        "price_data": {
                            "currency": payment.currency.lower(),
                            "product_data": {"name": f"Order #{payment.order_id}"},
                            "unit_amount": int(payment.amount * 100),
                        },
                        "quantity": 1,
                    }
                ],
                metadata={"order_id": str(payment.order_id), "payment_id": str(payment.id)},
            )

            payment.provider_payment_id = getattr(session, "id", "") or ""
            payment.checkout_url = getattr(session, "url", "") or ""
            payment.status = PaymentStatus.PENDING
            payment.raw_provider_response = {"id": payment.provider_payment_id, "url": payment.checkout_url}
            payment.save()
            return {"success": True, "checkout_url": payment.checkout_url, "session_id": payment.provider_payment_id}
        except Exception as e:
            payment.status = PaymentStatus.FAILED
            payment.raw_provider_response = {"error": str(e)}
            payment.save(update_fields=["status", "raw_provider_response", "updated_at"])
            return {"success": False, "error": str(e)}

    def check_payment_status(self, payment: OrderPayment):
        """
        Read the Checkout Session and mark the payment completed when Stripe has been paid.
        An expired session is cancelled so it is no longer treated as open.
        """
        if payment.status in (
            PaymentStatus.COMPLETED,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
            PaymentStatus.REFUND_INITIATED,
            PaymentStatus.REFUNDED,
        ):
            return {
                "success": True,
                "status": payment.status,
                "state": payment.provider_state or "",
                "message": f"Payment already {payment.status}",
            }
        session_id = (payment.provider_payment_id or "").strip()
        if not session_id:
            return {"success": False, "error": "No Stripe checkout session id found"}
        try:
            session = self.stripe.checkout.Session.retrieve(session_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

        session_status = str(getattr(session, "status", "") or "")
        payment_status = str(getattr(session, "payment_status", "") or "")
        payment.provider_state = payment_status or session_status
        payment.raw_provider_response = {
            "id": str(getattr(session, "id", "") or session_id),
            "status": session_status,
            "payment_status": payment_status,
        }
        update_fields = ["provider_state", "raw_provider_response", "updated_at"]
        if payment_status == "paid" or (session_status == "complete" and payment_status == "no_payment_required"):
            payment.status = PaymentStatus.COMPLETED
            update_fields.append("status")
        elif session_status == "expired":
            payment.status = PaymentStatus.CANCELLED
            update_fields.append("status")
        payment.save(update_fields=update_fields)
        return {
            "success": True,
            "status": payment.status,
            "state": payment.provider_state,
            "is_complete": payment.status == PaymentStatus.COMPLETED,
        }


def sync_open_stripe_payments(order) -> str | None:
    """
    Ask Stripe about pending checkout sessions on this order.
    Returns an error string when an open session could not be checked.
    """
    open_payments = list(
        OrderPayment.objects.filter(
            order=order,
            provider=PaymentProvider.STRIPE,
            is_deleted=False,
            status__in=(PaymentStatus.PENDING, PaymentStatus.PROCESSING),
        ).exclude(provider_payment_id="")
    )
    if not open_payments:
        return None
    try:
        client = StripeAPI()
    except (ValueError, ImportError) as exc:
        return str(exc)
    for payment in open_payments:
        result = client.check_payment_status(payment)
        if not result.get("success"):
            return result.get("error") or "Could not check the Stripe payment."
    return None


def sync_all_open_stripe_payments() -> int:
    """
    Check every pending Stripe checkout session. One failed session does not stop the rest.
    Returns how many sessions were checked.
    """
    open_payments = list(
        OrderPayment.objects.filter(
            provider=PaymentProvider.STRIPE,
            is_deleted=False,
            status__in=(PaymentStatus.PENDING, PaymentStatus.PROCESSING),
        ).exclude(provider_payment_id="")
    )
    if not open_payments:
        return 0
    try:
        client = StripeAPI()
    except (ValueError, ImportError) as exc:
        logger.warning("Stripe payment status check skipped: %s", exc)
        return 0
    checked = 0
    for payment in open_payments:
        try:
            result = client.check_payment_status(payment)
        except Exception as exc:
            logger.warning("Stripe payment %s status check failed: %s", payment.pk, exc)
            continue
        if result.get("success"):
            checked += 1
        else:
            logger.warning(
                "Stripe payment %s status check failed: %s",
                payment.pk,
                result.get("error") or "unknown error",
            )
    return checked


def complete_payment_for_session(session_id: str) -> OrderPayment | None:
    """
    Mark the OrderPayment for this Stripe Checkout session as completed.
    Called from the Stripe webhook on checkout.session.completed.
    Idempotent: if already completed, returns the payment without error.
    """
    try:
        payment = OrderPayment.objects.get(
            provider=PaymentProvider.STRIPE,
            provider_payment_id=session_id,
        )
    except OrderPayment.DoesNotExist:
        return None
    if payment.status in (
        PaymentStatus.COMPLETED,
        PaymentStatus.REFUND_INITIATED,
        PaymentStatus.REFUNDED,
    ):
        return payment
    payment.status = PaymentStatus.COMPLETED
    payment.save(update_fields=["status", "updated_at"])
    return payment

