"""Keep stored sale totals in step with order lines."""

from decimal import Decimal

from django.db.models import Sum
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from products.counters import adjust_products_sold
from products.models import ProductVariant

from .models import COUNTED_LINE_AVAILABILITY, Order, OrderItem, OrderStatus

CLOSED_SALE_STATUSES = {OrderStatus.CANCELLED, OrderStatus.REFUNDED}


@receiver(pre_delete, sender=ProductVariant)
def release_variant_stock_holds(sender, instance, **kwargs):
    OrderItem.objects.filter(variant_id=instance.pk, stock_taken=True).update(stock_taken=False)


def _sale_is_open(order_id):
    status = Order.objects.filter(pk=order_id).values_list("status", flat=True).first()
    return status not in CLOSED_SALE_STATUSES


def _counted_sale(product_id, quantity, line_total, availability):
    if availability not in COUNTED_LINE_AVAILABILITY or not product_id:
        return None
    return (product_id, int(quantity or 0), Decimal(str(line_total or 0)))


def _apply_order_units(order, sign):
    rows = (
        order.items.filter(availability__in=COUNTED_LINE_AVAILABILITY)
        .values("product_id")
        .annotate(qty=Sum("quantity"), revenue=Sum("line_total"))
    )
    for row in rows:
        adjust_products_sold(
            row["product_id"],
            sign * (row["qty"] or 0),
            sign * (row["revenue"] or Decimal("0")),
        )


@receiver(pre_save, sender=Order)
def remember_order_sale_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._sales_previous_status = None
        return
    instance._sales_previous_status = (
        Order.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    )


@receiver(post_save, sender=Order)
def sync_order_sale_status(sender, instance, created, **kwargs):
    if created:
        return
    previous = getattr(instance, "_sales_previous_status", None)
    if previous is None or previous == instance.status:
        return
    was_open = previous not in CLOSED_SALE_STATUSES
    is_open = instance.status not in CLOSED_SALE_STATUSES
    if was_open == is_open:
        return
    _apply_order_units(order=instance, sign=1 if is_open else -1)


@receiver(pre_save, sender=OrderItem)
def remember_order_item_sale(sender, instance, **kwargs):
    if not instance.pk:
        instance._sold_before = None
        return
    instance._sold_before = (
        OrderItem.objects.filter(pk=instance.pk)
        .values("product_id", "quantity", "line_total", "availability")
        .first()
    )


@receiver(post_save, sender=OrderItem)
def sync_order_item_sale(sender, instance, created, **kwargs):
    if not _sale_is_open(instance.order_id):
        return
    after = _counted_sale(instance.product_id, instance.quantity, instance.line_total, instance.availability)
    if created:
        if after:
            adjust_products_sold(after[0], after[1], after[2])
        return
    before_row = getattr(instance, "_sold_before", None)
    if not before_row:
        return
    before = _counted_sale(
        before_row["product_id"],
        before_row["quantity"],
        before_row["line_total"],
        before_row["availability"],
    )
    if before == after:
        return
    if before:
        adjust_products_sold(before[0], -before[1], before[2] * -1)
    if after:
        adjust_products_sold(after[0], after[1], after[2])


@receiver(pre_delete, sender=OrderItem)
def release_order_item_sale(sender, instance, **kwargs):
    if not _sale_is_open(instance.order_id):
        return
    counted = _counted_sale(instance.product_id, instance.quantity, instance.line_total, instance.availability)
    if not counted:
        return
    adjust_products_sold(counted[0], -counted[1], counted[2] * -1)
