"""
Stripe payment integration.

Credentials are loaded only from the PaymentCredentials model (DB). Store your
Stripe secret key via the staff API: POST /api/orders/payment-credentials/ with
provider=stripe, environment=sandbox|live, and private_key=sk_...
"""

from orders.models import OrderPayment, PaymentCredentials, PaymentProvider, PaymentStatus


class StripeAPI:
    def __init__(self):
        self.credentials = self._get_latest_credentials()
        if not self.credentials:
            raise ValueError("No active Stripe credentials found")

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
    if payment.status == PaymentStatus.COMPLETED:
        return payment
    payment.status = PaymentStatus.COMPLETED
    payment.save(update_fields=["status", "updated_at"])
    return payment

