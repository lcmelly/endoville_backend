"""
IntaSend payment integration (uses official SDK if installed).

This module is intentionally defensive: if the `intasend` package isn't installed,
it will raise a helpful error when you try to initialize the client.
"""

from django.conf import settings
from orders.models import OrderPayment, PaymentCredentials, PaymentProvider, PaymentStatus


class IntaSendAPI:
    """
    IntaSend API integration class using official SDK.

    Credentials are stored globally in PaymentCredentials (not per-user).
    """

    def __init__(self):
        self.credentials = self._get_latest_credentials()
        if not self.credentials:
            raise ValueError("No active IntaSend credentials found")

        if not self.credentials.api_key:
            raise ValueError("IntaSend API key is missing")
        if not self.credentials.encrypted_private_key:
            raise ValueError("IntaSend private key is missing")

        self.secret_key = self.credentials.get_private_key()
        if not self.secret_key:
            raise ValueError("Failed to decrypt IntaSend private key")

        self.api_key = self.credentials.api_key
        self.sandbox = self.credentials.environment == "sandbox"

        try:
            from intasend import APIService  # type: ignore
        except Exception as e:
            raise ImportError(
                "IntaSend SDK not installed. Add `intasend` to requirements to use this integration."
            ) from e

        self.service = APIService(token=self.secret_key, publishable_key=self.api_key, test=self.sandbox)

    def _get_latest_credentials(self):
        try:
            return (
                PaymentCredentials.objects.filter(
                    provider=PaymentProvider.INTASEND,
                    is_active=True,
                )
                .latest("created_at")
            )
        except PaymentCredentials.DoesNotExist:
            return None

    def create_payment_link(self, payment: OrderPayment):
        """
        Create a hosted payment link for the given OrderPayment.
        """
        try:
            response = self.service.collect.payment_link(
                amount=float(payment.amount),
                currency=payment.currency,
                reference=str(payment.id),
                callback_url=self._get_callback_url(),
                success_url=self._get_success_url(payment.id),
                fail_url=self._get_fail_url(payment.id),
                metadata={"order_id": str(payment.order_id), "payment_id": str(payment.id)},
            )

            payment.provider_invoice_id = getattr(response, "id", "") or ""
            payment.provider_state = getattr(response, "state", "") or ""
            payment.checkout_url = getattr(response, "url", "") or ""
            payment.status = PaymentStatus.PENDING
            payment.raw_provider_response = self._to_dict(response)
            payment.save()

            return {"success": True, "payment_url": payment.checkout_url, "invoice_id": payment.provider_invoice_id}
        except Exception as e:
            payment.status = PaymentStatus.FAILED
            payment.raw_provider_response = {"error": str(e)}
            payment.save(update_fields=["status", "raw_provider_response", "updated_at"])
            return {"success": False, "error": str(e)}

    def initiate_stk_push(
        self,
        payment: OrderPayment,
        phone_number: str | None = None,
        email: str | None = None,
        narrative: str | None = None,
    ):
        """
        Initiate M-Pesa STK push payment using IntaSend SDK.

        By default, uses the order's shipping address phone/email if present.
        """
        try:
            order = payment.order
            ship_addr = getattr(order, "shipping_address", None)

            phone_number = phone_number or getattr(ship_addr, "phone", "") or ""
            email = email or getattr(ship_addr, "email", "") or ""
            narrative = narrative or f"Order #{order.id}"

            if not phone_number:
                raise ValueError("phone_number is required for STK push")

            phone_number = self._format_phone_number(phone_number)

            response = self.service.collect.mpesa_stk_push(
                phone_number=phone_number,
                email=email or f"order-{order.id}@endovillehealth.com",
                amount=float(payment.amount),
                narrative=narrative,
            )

            provider_payment_id = None
            invoice_id = None
            state = "PENDING"

            if isinstance(response, dict):
                provider_payment_id = response.get("id")
                invoice = response.get("invoice") or {}
                invoice_id = invoice.get("invoice_id") or invoice.get("id")
                state = invoice.get("state") or response.get("state") or state
            else:
                provider_payment_id = getattr(response, "id", None)
                invoice = getattr(response, "invoice", None)
                if invoice:
                    invoice_id = getattr(invoice, "invoice_id", None) or getattr(invoice, "id", None)
                    state = getattr(invoice, "state", state)

            payment.provider_payment_id = provider_payment_id or payment.provider_payment_id
            payment.provider_invoice_id = invoice_id or payment.provider_invoice_id
            payment.provider_state = state or payment.provider_state
            payment.status = PaymentStatus.PROCESSING
            payment.raw_provider_response = response if isinstance(response, dict) else self._to_dict(response)
            payment.save()

            return {
                "success": True,
                "payment_id": provider_payment_id,
                "invoice_id": invoice_id,
                "state": state,
                "message": "STK push sent successfully",
            }
        except Exception as e:
            payment.status = PaymentStatus.FAILED
            payment.raw_provider_response = {"error": str(e)}
            payment.save(update_fields=["status", "raw_provider_response", "updated_at"])
            return {"success": False, "error": str(e)}

    def check_payment_status(self, payment: OrderPayment):
        """
        Check payment status using IntaSend collect endpoints.
        """
        try:
            if payment.status in [PaymentStatus.COMPLETED, PaymentStatus.FAILED, PaymentStatus.CANCELLED]:
                return {"success": True, "status": payment.status, "state": payment.provider_state}

            if not payment.provider_invoice_id and not payment.provider_payment_id:
                return {"success": False, "error": "No IntaSend invoice/payment id found on this payment."}

            if payment.provider_invoice_id:
                response = self.service.collect.status(invoice_id=payment.provider_invoice_id)
            else:
                response = self.service.collect.get_payment_request(payment.provider_payment_id)

            data = response if isinstance(response, dict) else self._to_dict(response)
            payment.raw_provider_response = data
            payment.save(update_fields=["raw_provider_response", "updated_at"])
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _to_dict(obj):
        if isinstance(obj, dict):
            return obj
        # best-effort conversion
        d = {}
        for k in ["id", "state", "url", "invoice", "net_amount", "currency", "charges", "provider", "failed_reason"]:
            if hasattr(obj, k):
                d[k] = getattr(obj, k)
        return d

    @staticmethod
    def _format_phone_number(phone_number: str) -> str:
        """
        Format phone number for IntaSend API (Kenya default):
        - strip non-digits
        - if starts with 0 -> 254...
        - if doesn't start with 254 -> prefix 254
        """
        digits_only = "".join(filter(str.isdigit, phone_number))
        if digits_only.startswith("0"):
            digits_only = "254" + digits_only[1:]
        if not digits_only.startswith("254"):
            digits_only = "254" + digits_only
        return digits_only

    def _get_callback_url(self):
        return getattr(settings, "INTASEND_CALLBACK_URL", "https://yourdomain.com/api/orders/payments/intasend/webhook/")

    def _get_success_url(self, payment_id):
        base = getattr(settings, "INTASEND_SUCCESS_URL_BASE", "https://yourdomain.com/payment/success/")
        return f"{base}{payment_id}/"

    def _get_fail_url(self, payment_id):
        base = getattr(settings, "INTASEND_FAIL_URL_BASE", "https://yourdomain.com/payment/failed/")
        return f"{base}{payment_id}/"

