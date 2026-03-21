from decimal import Decimal
import logging

from django.conf import settings
from django.utils import timezone

from .currency_utils import get_primary_currency
from .models import Order
from users.utils import send_template_email


logger = logging.getLogger(__name__)


def _format_money(value):
    if value is None:
        value = Decimal("0")
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


def _payment_status_color(status):
    if status == "completed":
        return "#16a34a"
    if status in {"failed", "cancelled"}:
        return "#dc2626"
    return "#f59e0b"


def _first_image_url(first_item):
    if not first_item:
        return ""
    variant = getattr(first_item, "variant", None)
    product = getattr(first_item, "product", None)
    variant_urls = getattr(variant, "image_urls", None) or []
    if variant_urls:
        return variant_urls[0]
    product_urls = getattr(product, "image_urls", None) or []
    if product_urls:
        return product_urls[0]
    return ""


def send_order_confirmation_email(order_id):
    template_key = getattr(settings, "ZEPTOMAIL_ORDER_CONFIRMATION_TEMPLATE_KEY", "")
    if not template_key:
        return False

    try:
        order = (
            Order.objects.select_related("user", "shipping_address", "shipment")
            .prefetch_related("items__product", "items__variant", "payments")
            .get(pk=order_id)
        )
    except Order.DoesNotExist:
        logger.warning("Order confirmation email skipped; order %s not found.", order_id)
        return False

    # Only send email if order has at least one completed payment
    from .models import PaymentStatus
    has_completed_payment = order.payments.filter(
        status=PaymentStatus.COMPLETED,
        is_deleted=False
    ).exists()
    if not has_completed_payment:
        logger.info("Order confirmation email skipped; no completed payment for order %s.", order.id)
        return False

    recipient_email = (
        getattr(order.shipping_address, "email", None)
        or getattr(order.user, "email", None)
        or ""
    ).strip()
    if not recipient_email:
        logger.info("Order confirmation email skipped; no recipient email for order %s.", order.id)
        return False

    recipient_name = (
        getattr(order.shipping_address, "full_name", None)
        or getattr(order.user, "first_name", None)
        or "Customer"
    )
    primary_currency = get_primary_currency()
    currency_code = getattr(primary_currency, "code", None) or "USD"

    first_item = order.items.order_by("id").first()
    item_count = order.items.count()
    product_name = ""
    if first_item:
        product_name = first_item.product_name
        if item_count > 1:
            product_name = f"{product_name} +{item_count - 1} more"
    first_image_url = _first_image_url(first_item)

    latest_payment = order.payments.filter(is_deleted=False).order_by("-created_at").first()
    try:
        shipment = order.shipment
    except Order.shipment.RelatedObjectDoesNotExist:
        shipment = None

    merge_data = {
        "item": {
            "quantity": str(first_item.quantity) if first_item else "",
            "variant_description": first_item.variant_description if first_item else "",
            "unit_price": _format_money(first_item.unit_price if first_item else None),
            "product_name": first_item.product_name if first_item else "",
            "barcode": first_item.barcode if first_item else "",
            "line_total": _format_money(first_item.line_total if first_item else None),
            "image_url": first_image_url,
        },
        "checkout_url": latest_payment.checkout_url if latest_payment else "",
        "support_phone": getattr(settings, "SUPPORT_PHONE", ""),
        "payment_status": latest_payment.get_status_display() if latest_payment else "Pending",
        "payment_invoice_id": latest_payment.provider_invoice_id if latest_payment else "",
        "team": getattr(settings, "DEFAULT_FROM_NAME", "Endoville Health"),
        "product_name": product_name,
        "image_url": first_image_url,
        "shipping_fee": _format_money(order.shipping_fee),
        "order_date": timezone.localtime(order.created_at).strftime("%Y-%m-%d %H:%M"),
        "order_status": order.get_status_display(),
        "total": _format_money(order.total),
        "carrier": shipment.carrier if shipment else "",
        "support_email": getattr(settings, "SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL),
        "current_year": str(timezone.now().year),
        "subtotal": _format_money(order.subtotal),
        "payment_provider": latest_payment.get_provider_display() if latest_payment else "",
        "name": recipient_name,
        "tracking_number": shipment.tracking_number if shipment else "",
        "currency": currency_code,
        "payment_status_color": _payment_status_color(latest_payment.status if latest_payment else "pending"),
        "shipping_address": {
            "country": order.shipping_address.country,
            "full_name": order.shipping_address.full_name,
            "city": order.shipping_address.city,
            "phone": order.shipping_address.phone,
            "address_line_1": order.shipping_address.address_line_1,
            "address_line_2": order.shipping_address.address_line_2,
            "postal_code": order.shipping_address.postal_code,
            "email": recipient_email,
        },
        "order_id": str(order.id),
        "tracking_url": shipment.tracking_url if shipment else "",
    }

    return send_template_email(
        to_email=recipient_email,
        template_key=template_key,
        merge_data=merge_data,
        to_name=recipient_name,
    )
