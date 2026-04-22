from decimal import Decimal
import logging

from django.conf import settings
from django.utils.html import escape
from django.utils import timezone

from .currency_utils import get_primary_currency
from .models import Cart, Order
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


def _cart_reminder_item_rows_html(summaries, currency_code: str) -> str:
    """Pre-rendered <tr>…</tr> rows for ZeptoMail (no array loops in HTML)."""
    cur = escape(currency_code or "")
    rows = []
    for row in summaries:
        name = escape(row.get("name") or "")
        qty = escape(row.get("quantity") or "")
        up = escape(row.get("unit_price") or "")
        lt = escape(row.get("line_total") or "")
        rows.append(
            "<tr>"
            '<td style="-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;'
            'mso-table-lspace:0pt;mso-table-rspace:0pt;padding:15px 12px;'
            'border-bottom:1px solid #F0F0F0;vertical-align:top;" valign="top">'
            f'<p style="font-weight:500;margin:0 0 4px;font-size:14px;color:#333;">{name}</p>'
            "</td>"
            '<td style="-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;'
            'mso-table-lspace:0pt;mso-table-rspace:0pt;padding:15px 12px;'
            'text-align:center;font-size:14px;color:#333;border-bottom:1px solid #F0F0F0;'
            'vertical-align:top;" align="center" valign="top">'
            f"{qty}</td>"
            '<td style="-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;'
            'mso-table-lspace:0pt;mso-table-rspace:0pt;padding:15px 12px;'
            'text-align:right;border-bottom:1px solid #F0F0F0;vertical-align:top;" '
            'align="right" valign="top">'
            f'<p style="font-weight:500;margin:0 0 2px;font-size:14px;color:#333;">{cur} {lt}</p>'
            f'<p style="margin:0;font-size:11px;color:#888;">{cur} {up} each</p>'
            "</td>"
            "</tr>"
        )
    return "".join(rows)


def send_abandoned_cart_reminder_email(cart_id, reminder_hours):
    template_key = getattr(settings, "ZEPTOMAIL_CART_REMINDER_TEMPLATE_KEY", "")
    if not template_key:
        return False

    try:
        cart = (
            Cart.objects.select_related("user")
            .prefetch_related("items__product", "items__variant", "items__variant__product")
            .get(pk=cart_id)
        )
    except Cart.DoesNotExist:
        logger.warning("Cart reminder email skipped; cart %s not found.", cart_id)
        return False

    items = list(cart.items.all())
    if not items:
        logger.info("Cart reminder email skipped; cart %s has no items.", cart.id)
        return False

    recipient_email = (getattr(cart.user, "email", None) or "").strip()
    if not recipient_email:
        logger.info("Cart reminder email skipped; no recipient email for cart %s.", cart.id)
        return False

    recipient_name = getattr(cart.user, "first_name", None) or "Customer"
    primary_currency = get_primary_currency()
    currency_code = getattr(primary_currency, "code", None) or "USD"

    subtotal = Decimal("0")
    item_summaries = []
    for item in items:
        product = item.variant.product if item.variant else item.product
        if item.variant and item.variant.price is not None:
            unit_price = Decimal(item.variant.price)
        elif item.variant:
            unit_price = Decimal(item.variant.product.price)
        else:
            unit_price = Decimal(item.product.price)
        line_total = (unit_price * item.quantity).quantize(Decimal("0.01"))
        subtotal += line_total
        item_summaries.append(
            {
                "name": product.name if product else "",
                "quantity": str(item.quantity),
                "unit_price": _format_money(unit_price),
                "line_total": _format_money(line_total),
            }
        )

    cart_url = (getattr(settings, "FRONTEND_CART_URL", "") or "").strip()
    merge_data = {
        "name": recipient_name,
        "team": getattr(settings, "DEFAULT_FROM_NAME", "Endoville Health"),
        "support_email": getattr(settings, "SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL),
        "support_phone": getattr(settings, "SUPPORT_PHONE", ""),
        "current_year": str(timezone.now().year),
        "reminder_hours": str(reminder_hours),
        "item_count": str(len(items)),
        "subtotal": _format_money(subtotal),
        "currency": currency_code,
        "cart_items": item_summaries,
        "cart_items_html": _cart_reminder_item_rows_html(item_summaries, currency_code),
        "cart_url": cart_url or "#",
    }

    return send_template_email(
        to_email=recipient_email,
        template_key=template_key,
        merge_data=merge_data,
        to_name=recipient_name,
    )
