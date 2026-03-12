"""
IntaSend payment integration using the official SDK.

    from intasend import APIService

    token = "YOUR-API-TOKEN"
    publishable_key = "YOUR-PUBLISHABLE-KEY"
    service = APIService(token=token, publishable_key=publishable_key, test=True)

Credentials are stored in PaymentCredentials (api_key=publishable key,
encrypted_private_key=token/secret). We load them and create APIService the same way.
"""

from decimal import Decimal

from django.conf import settings

from intasend import APIService

from orders.currency_utils import amount_to_primary, order_total_in_currency
from orders.models import OrderPayment, PaymentCredentials, PaymentProvider, PaymentStatus


class IntaSendAPI:
    """IntaSend API integration using APIService(token=..., publishable_key=..., test=...)."""

    def __init__(self, user=None):
        credentials = self._get_latest_credentials()
        if not credentials:
            raise ValueError("No active IntaSend credentials found")
        if not credentials.api_key:
            raise ValueError("IntaSend publishable key (api_key) is missing")
        if not credentials.encrypted_private_key:
            raise ValueError("IntaSend token (private key) is missing")
        token = credentials.get_private_key()
        if not token:
            raise ValueError("Failed to decrypt IntaSend private key")
        publishable_key = credentials.api_key
        test = credentials.environment == "sandbox"
        self.service = APIService(token=token, publishable_key=publishable_key, test=test)

    def _get_latest_credentials(self):
        try:
            return PaymentCredentials.objects.filter(
                provider=PaymentProvider.INTASEND,
                is_active=True,
            ).latest("created_at")
        except PaymentCredentials.DoesNotExist:
            return None

    @staticmethod
    def _format_phone_number(phone_number: str) -> str:
        """Format phone for IntaSend (e.g. Kenya 254...): strip non-digits, ensure 254 prefix."""
        digits_only = "".join(filter(str.isdigit, phone_number))
        if digits_only.startswith("0"):
            digits_only = "254" + digits_only[1:]
        if not digits_only.startswith("254"):
            digits_only = "254" + digits_only
        return digits_only

    def _get_redirect_url(self, payment: OrderPayment) -> str:
        """URL to redirect the customer after payment (success/finish)."""
        base = getattr(
            settings,
            "INTASEND_REDIRECT_URL_BASE",
            "https://yourdomain.com/payment/success/",
        )
        return f"{base}{payment.id}/"

    @staticmethod
    def _to_dict(obj):
        """Convert SDK response to dict for storage."""
        if isinstance(obj, dict):
            return obj
        out = {}
        for key in ("id", "url", "state", "invoice_id", "invoice_url"):
            if hasattr(obj, key):
                out[key] = getattr(obj, key)
        return out

    def create_payment_link(
        self,
        payment: OrderPayment,
        *,
        phone_number: str | None = None,
        email: str | None = None,
    ):
        """
        Create a checkout link for this order payment via IntaSend collect.checkout().
        Sets payment.checkout_url from response.get("url"). Returns success dict with payment_url or error.
        """
        try:
            order = payment.order
            ship = getattr(order, "shipping_address", None)
            phone_number = phone_number or (getattr(ship, "phone", None) or "")
            email = email or (getattr(ship, "email", None) or "") or f"order-{order.id}@endovillehealth.com"
            if phone_number:
                phone_number = self._format_phone_number(phone_number)

            redirect_url = self._get_redirect_url(payment)
            comment = f"Order #{order.id}"

            response = self.service.collect.checkout(
                phone_number=phone_number or None,
                email=email,
                amount=float(payment.amount),
                currency=payment.currency,
                comment=comment,
                redirect_url=redirect_url,
            )

            if isinstance(response, dict):
                checkout_url = response.get("url") or ""
                # Store IntaSend checkout/invoice id (used for check_payment_status)
                payment.provider_invoice_id = str(response.get("id") or response.get("invoice_id") or "")
                payment.provider_state = str(response.get("state", "") or response.get("paid", "") or "")
                payment.raw_provider_response = dict(response)
            else:
                checkout_url = getattr(response, "url", None) or ""
                payment.provider_invoice_id = str(
                    getattr(response, "id", "") or getattr(response, "invoice_id", "") or ""
                )
                payment.provider_state = str(getattr(response, "state", "") or "")
                payment.raw_provider_response = self._to_dict(response)

            payment.checkout_url = checkout_url
            payment.status = PaymentStatus.PENDING
            payment.save()

            if not payment.checkout_url:
                payment.status = PaymentStatus.FAILED
                payment.raw_provider_response["_error"] = "IntaSend did not return a checkout URL"
                payment.save(update_fields=["status", "raw_provider_response", "updated_at"])
                return {"success": False, "error": "IntaSend did not return a checkout URL"}

            return {
                "success": True,
                "payment_url": payment.checkout_url,
                "invoice_id": payment.provider_invoice_id,
            }
        except Exception as e:
            payment.status = PaymentStatus.FAILED
            payment.raw_provider_response = {"error": str(e)}
            payment.save(update_fields=["status", "raw_provider_response", "updated_at"])
            return {"success": False, "error": str(e)}

    def _amount_to_kes(self, amount: Decimal, currency_code: str) -> float:
        """Convert amount from given currency to KES using app currency rates."""
        if (currency_code or "").strip().upper() == "KES":
            return float(amount)
        amount_primary = amount_to_primary(amount, currency_code)
        amount_kes = order_total_in_currency(amount_primary, "KES")
        return float(amount_kes)

    def initiate_stk_push(
        self,
        payment: OrderPayment,
        *,
        phone_number: str,
        email: str | None = None,
        narrative: str | None = None,
    ):
        """
        Initiate M-Pesa STK push payment using IntaSend SDK.
        Amount is converted to KES using currency rates. phone_number is required.
        """
        try:
            order = payment.order
            email = email or getattr(order.shipping_address, "email", None) or f"order-{order.id}@endovillehealth.com"
            narrative = narrative or f"Order #{order.id}"

            phone_number = self._format_phone_number(phone_number)
            amount_kes = self._amount_to_kes(Decimal(str(payment.amount)), payment.currency)

            response = self.service.collect.mpesa_stk_push(
                phone_number=phone_number,
                email=email,
                amount=amount_kes,
                narrative=narrative,
            )

            if isinstance(response, dict):
                payment.provider_payment_id = str(response.get("id") or "")
                if response.get("invoice"):
                    inv = response["invoice"]
                    payment.provider_invoice_id = str(inv.get("invoice_id") or "")
                    payment.provider_state = str(inv.get("state") or "")
                payment.raw_provider_response = dict(response)
            else:
                payment.provider_payment_id = str(getattr(response, "id", "") or "")
                if getattr(response, "invoice", None):
                    inv = response.invoice
                    payment.provider_invoice_id = str(getattr(inv, "invoice_id", "") or "")
                    payment.provider_state = str(getattr(inv, "state", "") or "")
                payment.raw_provider_response = self._to_dict(response)

            payment.status = PaymentStatus.PROCESSING
            payment.save()

            invoice_id = None
            state = "PENDING"
            if isinstance(response, dict):
                if response.get("invoice"):
                    invoice_id = response["invoice"].get("invoice_id")
                    state = response["invoice"].get("state", state)
            elif getattr(response, "invoice", None):
                invoice_id = getattr(response.invoice, "invoice_id", None)
                state = getattr(response.invoice, "state", state)

            return {
                "success": True,
                "payment_id": payment.provider_payment_id,
                "invoice_id": invoice_id,
                "state": state,
                "message": "STK push sent successfully",
            }
        except Exception as e:
            payment.status = PaymentStatus.FAILED
            payment.raw_provider_response = {"error": str(e)}
            payment.save(update_fields=["status", "raw_provider_response", "updated_at"])
            return {"success": False, "error": str(e)}

    @staticmethod
    def _intasend_state_to_status(state: str) -> str | None:
        """Map IntaSend API state to our PaymentStatus; None means leave unchanged."""
        s = (state or "").upper()
        if s in ("COMPLETE", "COMPLETED", "PAID", "SETTLED"):
            return PaymentStatus.COMPLETED
        if s == "CANCELLED":
            return PaymentStatus.CANCELLED
        if s in ("FAILED", "EXPIRED", "REVERSED"):
            return PaymentStatus.FAILED
        return None

    def check_payment_status(self, payment: OrderPayment):
        """
        Check the status of a payment using the IntaSend API.
        Uses invoice ID (provider_invoice_id) when available via collect.status(invoice_id=...),
        otherwise payment ID via get_payment_request. Updates payment from API response.
        """
        try:
            if payment.status in (PaymentStatus.COMPLETED, PaymentStatus.FAILED, PaymentStatus.CANCELLED):
                return {
                    "success": True,
                    "state": payment.provider_state or "UNKNOWN",
                    "status": payment.status,
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                    "message": f"Payment already {payment.status}",
                }

            if not payment.provider_invoice_id and not payment.provider_payment_id:
                return {"success": False, "error": "No IntaSend payment ID or invoice ID found"}

            # Prefer invoice ID: query IntaSend API using invoice ID when we have it
            if payment.provider_invoice_id:
                response = self.service.collect.status(invoice_id=payment.provider_invoice_id)
            elif payment.provider_payment_id:
                response = self.service.collect.get_payment_request(payment.provider_payment_id)
            else:
                return {"success": False, "error": "No IntaSend payment ID or invoice ID found"}

            def apply_state_and_save(state: str, api_response) -> None:
                payment.provider_state = str(state)
                new_status = self._intasend_state_to_status(state)
                if new_status:
                    payment.status = new_status
                payment.raw_provider_response = (
                    dict(api_response) if isinstance(api_response, dict) else self._to_dict(api_response)
                )
                payment.save(
                    update_fields=["provider_state", "raw_provider_response", "updated_at"]
                    + (["status"] if new_status else [])
                )

            if isinstance(response, dict):
                if "invoice" in response and response["invoice"]:
                    invoice = response["invoice"]
                    state = invoice.get("state", "UNKNOWN")
                    apply_state_and_save(state, response)
                    return {
                        "success": True,
                        "state": state,
                        "status": payment.status,
                        "amount": invoice.get("net_amount"),
                        "currency": invoice.get("currency"),
                        "mpesa_reference": invoice.get("api_ref"),
                        "failed_reason": invoice.get("failed_reason"),
                        "provider": invoice.get("provider"),
                        "charges": invoice.get("charges"),
                    }
                return {"success": False, "error": "No invoice data in response"}

            if hasattr(response, "invoice") and response.invoice:
                invoice = response.invoice
                state = getattr(invoice, "state", "UNKNOWN")
                apply_state_and_save(state, response)
                return {
                    "success": True,
                    "state": state,
                    "status": payment.status,
                    "amount": getattr(invoice, "net_amount", None),
                    "currency": getattr(invoice, "currency", None),
                    "mpesa_reference": getattr(invoice, "api_ref", None),
                    "failed_reason": getattr(invoice, "failed_reason", None),
                    "provider": getattr(invoice, "provider", None),
                    "charges": getattr(invoice, "charges", None),
                }
            return {"success": False, "error": "Invalid response structure from IntaSend SDK"}
        except Exception as e:
            return {"success": False, "error": str(e)}
