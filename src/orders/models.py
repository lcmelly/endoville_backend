"""
Models for ordering and shipping.
"""

import contextvars
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

import base64
import uuid
from hashlib import sha256

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import MinValueValidator
from django.db.models import Sum
from django.utils.encoding import force_bytes


def _log_order_status(order, new_status):
    from users.audit import log_staff_change

    previous = order.status
    if previous == new_status:
        return
    log_staff_change(
        action="order.status_changed",
        target_type="order",
        target_id=order.pk,
        order_id=order.pk,
        summary=f"Order #{order.pk} status {previous} -> {new_status}",
        changes={"status": {"from": previous, "to": new_status}},
    )


def _writes_status(update_fields):
    return update_fields is None or "status" in update_fields


def shipment_status_aligned_to_order(order_status, shipment_status, previous_order_status):
    """
    Parcel status implied by an order status that was just stored.
    Cancelled and refunded orders keep the parcel where it is.
    """
    if order_status == OrderStatus.COMPLETE:
        return ShippingStatus.DELIVERED
    if order_status == OrderStatus.SHIPPING:
        if shipment_status in (ShippingStatus.DISPATCHED, ShippingStatus.OUT_FOR_DELIVERY):
            return shipment_status
        return ShippingStatus.DISPATCHED
    if previous_order_status in (OrderStatus.SHIPPING, OrderStatus.COMPLETE) and order_status in (
        OrderStatus.PAYMENT_PENDING,
        OrderStatus.PLACED,
        OrderStatus.PROCESSING,
    ):
        return ShippingStatus.ORDER_PLACED
    return None


def order_status_aligned_to_shipment(shipment_status, order):
    """
    Order status implied by a shipment status that was just stored.
    Rewinding the parcel to placed returns a paid order to processing.
    """
    if shipment_status == ShippingStatus.DELIVERED:
        return OrderStatus.COMPLETE
    if shipment_status in (ShippingStatus.DISPATCHED, ShippingStatus.OUT_FOR_DELIVERY):
        return OrderStatus.SHIPPING
    if shipment_status == ShippingStatus.ORDER_PLACED and order.status in (
        OrderStatus.SHIPPING,
        OrderStatus.COMPLETE,
    ):
        if order.recalculate_is_fully_paid():
            return OrderStatus.PROCESSING
        return OrderStatus.PAYMENT_PENDING
    return None


# Orders whose refund rows are still being written. Status is derived once
# those rows exist, so a half-written refund cannot flip the order to cancelled.
_refund_commands = contextvars.ContextVar("order_refund_commands", default=frozenset())


def send_order_confirmation_email(order_id):
    """
    Proxy function so callers/tests can patch `orders.models.send_order_confirmation_email`
    without importing email code at module import time.
    """
    from .emails import send_order_confirmation_email as _send_order_confirmation_email

    return _send_order_confirmation_email(order_id)


class ShippingStatus(models.TextChoices):
    ORDER_PLACED = "ORDER_PLACED", "Order placed"
    DISPATCHED = "DISPATCHED", "Dispatched"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY", "Out for delivery"
    DELIVERED = "DELIVERED", "Delivered"


class OrderStatus(models.TextChoices):
    PAYMENT_PENDING = "PAYMENT_PENDING", "Payment Pending"
    PLACED = "PLACED", "Placed"  # legacy
    PROCESSING = "PROCESSING", "Processing"
    SHIPPING = "SHIPPING", "Shipping"
    COMPLETE = "COMPLETE", "Complete"
    CANCELLED = "CANCELLED", "Cancelled"
    REFUNDED = "REFUNDED", "Refunded"


class LineAvailability(models.TextChoices):
    PENDING = "pending", "Pending confirmation"
    CONFIRMED = "confirmed", "Confirmed"
    UNAVAILABLE = "unavailable", "Unavailable"
    REPLACED = "replaced", "Replaced"


# Lines that still belong on the bill and count as a sale. Unavailable and
# replaced rows stay on the order so the customer can see what changed.
COUNTED_LINE_AVAILABILITY = (LineAvailability.PENDING, LineAvailability.CONFIRMED)
SHIPPED_LINE_AVAILABILITY = (LineAvailability.CONFIRMED,)


class Warehouse(models.Model):
    """
    Receiving warehouse. Placed orders are shipped here.
    This is not the customer's delivery address.
    """

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default="USA")
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_active:
            Warehouse.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)

    def __str__(self):
        return self.name


class ShippingCountryRate(models.Model):
    """
    USD charged for one unit of product weight to one destination country.

    Admins edit these rows, or replace the whole table through the shipping rates API.
    A shipment lighter than unit_weight pays fee. A heavier shipment pays
    (weight ÷ unit_weight) × fee.
    """

    country = models.CharField(max_length=100, unique=True)
    unit_weight = models.PositiveIntegerField(
        default=1000,
        validators=[MinValueValidator(1)],
        help_text="Grams in one shipping unit. A lighter shipment is charged as one unit.",
    )
    fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="USD for one unit of weight. Heavier shipments multiply this by weight ÷ unit weight.",
    )

    class Meta:
        ordering = ["country"]

    def __str__(self):
        return f"{self.country}: {self.fee} USD per {self.unit_weight} g"


class ShippingAddress(models.Model):
    """
    Snapshot of shipping address for an order.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)

    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default="Nigeria")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.city}"


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="cart", on_delete=models.CASCADE
    )
    last_reminder_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Activity time plus the last reminder step that succeeded: 12, 24, or 48 hours.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    def __str__(self):
        return f"Cart for {self.user}"

    def mark_active(self):
        self.last_reminder_at = None
        self.save(update_fields=["last_reminder_at", "updated_at"])

    def clear_items(self):
        self.items.all().delete()
        self.mark_active()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, null=True, blank=True)
    variant = models.ForeignKey(
        "products.ProductVariant", on_delete=models.CASCADE, null=True, blank=True
    )
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(product__isnull=False) & models.Q(variant__isnull=True))
                    | (models.Q(product__isnull=True) & models.Q(variant__isnull=False))
                ),
                name="orders_cartitem_product_xor_variant",
            ),
            models.UniqueConstraint(
                fields=["cart", "product"],
                condition=models.Q(product__isnull=False),
                name="orders_cartitem_unique_product_per_cart",
            ),
            models.UniqueConstraint(
                fields=["cart", "variant"],
                condition=models.Q(variant__isnull=False),
                name="orders_cartitem_unique_variant_per_cart",
            ),
        ]

    def __str__(self):
        target = self.variant_id or self.product_id
        return f"CartItem {target} x{self.quantity}"


class Order(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="orders", on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.PAYMENT_PENDING, db_index=True
    )

    shipping_address = models.ForeignKey(
        ShippingAddress, related_name="orders", on_delete=models.PROTECT
    )
    warehouse = models.ForeignKey(
        Warehouse,
        related_name="orders",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="US warehouse this order is shipped to.",
    )

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_fully_paid = models.BooleanField(default=False, db_index=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user}"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        writing_status = _writes_status(update_fields)
        previous_status = None
        if self.pk:
            previous_status = (
                Order.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )

        fee_written = update_fields is not None and "shipping_fee" in update_fields
        if fee_written:
            self.total = (Decimal(self.subtotal or 0) + Decimal(self.shipping_fee or 0)).quantize(Decimal("0.01"))
            kwargs["update_fields"] = list(set(update_fields) | {"total"})

        status_changed = (
            writing_status and previous_status is not None and previous_status != self.status
        )
        if (
            status_changed
            and previous_status not in (OrderStatus.SHIPPING, OrderStatus.COMPLETE)
            and self.status in (OrderStatus.SHIPPING, OrderStatus.COMPLETE)
        ):
            self.assert_ready_to_ship()

        with transaction.atomic():
            super().save(*args, **kwargs)
            if status_changed:
                self._apply_status_change(previous_status)
            if fee_written and not getattr(self, "_applying_paid_state", False):
                self.apply_paid_state()

    def _apply_status_change(self, previous_status):
        if previous_status is not None:
            from users.audit import log_staff_change

            log_staff_change(
                action="order.status_changed",
                target_type="order",
                target_id=self.pk,
                order_id=self.pk,
                summary=f"Order #{self.pk} status {previous_status} -> {self.status}",
                changes={"status": {"from": previous_status, "to": self.status}},
            )

        if self.status in (OrderStatus.CANCELLED, OrderStatus.REFUNDED):
            from users.audit import log_staff_change

            pending_ids = list(
                self.payments.filter(
                    status=PaymentStatus.PENDING,
                    is_deleted=False,
                ).values_list("pk", flat=True)
            )
            if pending_ids:
                self.payments.filter(pk__in=pending_ids).update(
                    status=PaymentStatus.CANCELLED,
                    updated_at=timezone.now(),
                )
                for payment_id in pending_ids:
                    log_staff_change(
                        action="payment.status_changed",
                        target_type="payment",
                        target_id=payment_id,
                        order_id=self.pk,
                        summary=f"Payment #{payment_id} on order #{self.pk} pending -> cancelled",
                        changes={"status": {"from": PaymentStatus.PENDING, "to": PaymentStatus.CANCELLED}},
                    )
        if self.status == OrderStatus.REFUNDED:
            self._record_completed_refunds()

        if not getattr(self, "_aligning_fulfillment", False):
            self._align_shipment(previous_status)

    def _align_shipment(self, previous_status):
        try:
            shipment = self.shipment
        except Shipment.DoesNotExist:
            return
        target = shipment_status_aligned_to_order(self.status, shipment.status, previous_status)
        if target is None:
            return
        fields = []
        if shipment.status != target:
            shipment.status = target
            fields.append("status")
        if target == ShippingStatus.DELIVERED and shipment.delivered_at is None:
            shipment.delivered_at = timezone.now()
            fields.append("delivered_at")
        if not fields:
            return
        fields.append("updated_at")
        shipment._aligning_fulfillment = True
        try:
            shipment.save(update_fields=fields)
        finally:
            shipment._aligning_fulfillment = False

    def recalculate_is_fully_paid(self) -> bool:
        """
        Order is fully paid if the sum of received payment amounts (converted to primary
        currency) >= order total. Order total is in primary currency (e.g. USD).
        A refund that is only initiated still counts. A completed refund does not.
        """
        from .currency_utils import amount_to_primary

        received = Decimal("0")
        payments = self.payments.filter(
            status__in=(
                PaymentStatus.COMPLETED,
                PaymentStatus.REFUND_INITIATED,
                PaymentStatus.REFUNDED,
            ),
            is_deleted=False,
        )
        for payment in payments:
            received += amount_to_primary(payment.amount, payment.currency, usd_rate=payment.usd_rate)
        for refund in OrderRefund.objects.filter(payment__in=payments, status=RefundStatus.COMPLETED):
            received -= amount_to_primary(
                refund.amount, refund.currency, usd_rate=refund.payment.usd_rate
            )
        if received < 0:
            received = Decimal("0")
        completed_sum = received

        total = self.total
        if total is None:
            total = Decimal("0")
        elif not isinstance(total, Decimal):
            total = Decimal(str(total))

        return completed_sum >= total

    def _record_completed_refunds(self):
        """
        Marking the order refunded completes open refunds and writes a completed
        refund for any amount still held on each payment. The order status is
        derived after those rows exist, and this does not run again while that
        derivation saves the order.
        """
        active = _refund_commands.get()
        if self.pk in active:
            return
        token = _refund_commands.set(active | {self.pk})
        try:
            self._write_outstanding_refunds()
            self.derive_refunded_status()
        finally:
            _refund_commands.reset(token)

    def _write_outstanding_refunds(self):
        payments = self.payments.filter(
            is_deleted=False,
            status__in=(
                PaymentStatus.COMPLETED,
                PaymentStatus.REFUND_INITIATED,
                PaymentStatus.REFUNDED,
            ),
        )
        for payment in payments:
            for refund in payment.refunds.filter(status=RefundStatus.INITIATED):
                refund.status = RefundStatus.COMPLETED
                refund.save(update_fields=["status", "completed_at", "updated_at"])
            remaining = payment.refundable_amount()
            if remaining > 0:
                OrderRefund.objects.create(
                    order=self,
                    payment=payment,
                    amount=remaining,
                    currency=payment.currency,
                    status=RefundStatus.COMPLETED,
                    reason="Order marked refunded",
                )

        cache = getattr(self, "_prefetched_objects_cache", None)
        if cache is not None:
            cache.pop("refunds", None)

    def derive_refunded_status(self):
        """
        REFUNDED means every held payment has been refunded.
        Until that is true, a refunded order goes back to cancelled.
        """
        if self.status not in (OrderStatus.CANCELLED, OrderStatus.REFUNDED):
            return

        taken = self.payments.filter(is_deleted=False).exclude(
            status__in=(
                PaymentStatus.PENDING,
                PaymentStatus.PROCESSING,
                PaymentStatus.FAILED,
                PaymentStatus.CANCELLED,
            )
        )
        if not taken.exists():
            return

        fully_refunded = not taken.exclude(status=PaymentStatus.REFUNDED).exists()
        if fully_refunded and self.status != OrderStatus.REFUNDED:
            self.status = OrderStatus.REFUNDED
            self.save(update_fields=["status", "updated_at"])
        elif not fully_refunded and self.status == OrderStatus.REFUNDED:
            self.status = OrderStatus.CANCELLED
            self.save(update_fields=["status", "updated_at"])

    def apply_paid_state(self):
        """
        is_fully_paid means the bill is covered.
        PROCESSING means that, and the parcel has not left.
        SHIPPING and COMPLETE stay with the parcel.
        """
        if getattr(self, "_applying_paid_state", False):
            return
        self._applying_paid_state = True
        try:
            self.refresh_from_db(fields=["status", "is_fully_paid", "total"])
            covered = self.recalculate_is_fully_paid()
            new_status = self.status
            if covered and self.status in (OrderStatus.PAYMENT_PENDING, OrderStatus.PLACED):
                new_status = OrderStatus.PROCESSING
            elif not covered and self.status == OrderStatus.PROCESSING:
                new_status = OrderStatus.PAYMENT_PENDING
            status_changed = self.status != new_status
            if not status_changed and self.is_fully_paid == covered:
                return
            self.is_fully_paid = covered
            self.status = new_status
            fields = ["is_fully_paid", "updated_at"]
            if status_changed:
                fields.append("status")
            self.save(update_fields=fields)
        finally:
            self._applying_paid_state = False

    def refresh_paid_flag(self):
        self.apply_paid_state()

    def recalculate_totals(self):
        cache = getattr(self, "_prefetched_objects_cache", None)
        if cache is not None:
            cache.pop("items", None)
        subtotal = Decimal("0")
        for item in self.items.filter(availability__in=COUNTED_LINE_AVAILABILITY):
            subtotal += Decimal(item.line_total)
        self.subtotal = subtotal.quantize(Decimal("0.01"))
        shipping_fee = self.shipping_fee if self.shipping_fee is not None else Decimal("0")
        self.total = (self.subtotal + Decimal(shipping_fee)).quantize(Decimal("0.01"))
        self.save(update_fields=["subtotal", "total", "updated_at"])
        self.refresh_paid_flag()

    def _ensure_lines_editable(self):
        if self.status not in (OrderStatus.PAYMENT_PENDING, OrderStatus.PLACED, OrderStatus.PROCESSING):
            raise ValidationError("Order lines can be changed while the order is still being processed.")

    def assert_ready_to_ship(self):
        """
        Every line is confirmed, unavailable, or replaced before the parcel can leave.
        At least one confirmed line has to remain when the order has items.
        """
        pending = list(
            self.items.filter(availability=LineAvailability.PENDING)
            .order_by("id")
            .values_list("product_name", flat=True)
        )
        if pending:
            names = ", ".join(pending)
            raise ValidationError(
                f"Confirm every item before this order can ship. Still unconfirmed: {names}."
            )
        if self.items.exists() and not self.items.filter(availability=LineAvailability.CONFIRMED).exists():
            raise ValidationError("There is no confirmed item to ship.")

    @staticmethod
    def _shelf(product, variant):
        if variant is not None:
            if variant.track_stock and variant.stock is not None:
                return variant
            return None
        if product is not None and product.track_stock and product.stock is not None:
            return product
        return None

    @staticmethod
    def _move_stock(shelf, delta):
        shelf.stock += delta
        shelf._stock_movement = True
        shelf.save(update_fields=["stock", "updated_at"])

    @staticmethod
    def _restock_line(item):
        if not item.stock_taken:
            return
        item.stock_taken = False
        item.save(update_fields=["stock_taken"])
        if item.variant_id:
            shelf = item.variant
        elif item.product_id:
            shelf = item.product
        else:
            shelf = None
        if shelf is None or shelf.stock is None:
            return
        Order._move_stock(shelf, item.quantity)

    @staticmethod
    def _take_stock(product, variant, quantity):
        shelf = Order._shelf(product, variant)
        if shelf is None:
            return False
        if shelf.stock < quantity:
            kind = "variant" if variant is not None else "product"
            raise ValidationError(f"Insufficient {kind} stock.")
        Order._move_stock(shelf, -quantity)
        return True

    def issue_price_difference_refund(self, difference_primary, reason, user):
        """
        Record initiated refunds that cover a drop in the order total.
        Amounts are taken from completed payments, in payment currency.
        """
        from .currency_utils import amount_to_primary, primary_to_currency_amount

        difference_primary = Decimal(str(difference_primary or 0)).quantize(Decimal("0.01"))
        if difference_primary <= 0:
            return []

        created = []
        payments = self.payments.filter(
            is_deleted=False,
            status__in=(PaymentStatus.COMPLETED, PaymentStatus.REFUND_INITIATED),
        ).order_by("created_at", "id")
        for payment in payments:
            if difference_primary <= 0:
                break
            refundable = payment.refundable_amount()
            if refundable <= 0:
                continue
            refundable_primary = amount_to_primary(refundable, payment.currency, usd_rate=payment.usd_rate)
            if refundable_primary <= 0:
                continue
            take_primary = min(difference_primary, refundable_primary)
            if take_primary == refundable_primary:
                take_amount = refundable
            else:
                take_amount = primary_to_currency_amount(take_primary, payment.currency, payment.usd_rate)
                if take_amount > refundable:
                    take_amount = refundable
            if take_amount <= 0:
                continue
            created.append(
                OrderRefund.objects.create(
                    order=self,
                    payment=payment,
                    amount=take_amount,
                    currency=payment.currency,
                    status=RefundStatus.INITIATED,
                    reason=reason,
                    initiated_by=user,
                )
            )
            difference_primary -= amount_to_primary(take_amount, payment.currency, usd_rate=payment.usd_rate)
        return created

    @transaction.atomic
    def confirm_line(self, item, user, note=""):
        self._ensure_lines_editable()
        if item.order_id != self.id:
            raise ValidationError("That line is not on this order.")
        if item.availability in (LineAvailability.UNAVAILABLE, LineAvailability.REPLACED):
            raise ValidationError("That item is not being shipped.")
        item.availability = LineAvailability.CONFIRMED
        cleaned = (note or "").strip()
        if cleaned:
            item.availability_note = cleaned
        item.decided_at = timezone.now()
        item.decided_by = user if getattr(user, "is_authenticated", False) else None
        item.save(
            update_fields=["availability", "availability_note", "decided_at", "decided_by"]
        )
        from users.audit import log_staff_change

        log_staff_change(
            action="order.line_confirmed",
            target_type="order",
            target_id=self.pk,
            order_id=self.pk,
            summary=f"Confirmed {item.product_name} on order #{self.pk}",
            changes={"item_id": item.pk, "product_name": item.product_name, "availability": item.availability},
        )

    @transaction.atomic
    def mark_line_unavailable(self, item, user, note=""):
        self._ensure_lines_editable()
        if item.order_id != self.id:
            raise ValidationError("That line is not on this order.")
        if item.availability == LineAvailability.UNAVAILABLE:
            return []
        if item.availability == LineAvailability.REPLACED:
            raise ValidationError("That item was already replaced.")
        removed_name = item.product_name
        difference = Decimal(item.line_total)
        self._restock_line(item)
        item.availability = LineAvailability.UNAVAILABLE
        item.availability_note = (note or "").strip()
        item.decided_at = timezone.now()
        item.decided_by = user if getattr(user, "is_authenticated", False) else None
        item.save(
            update_fields=["availability", "availability_note", "decided_at", "decided_by"]
        )
        self.recalculate_totals()
        refunds = self.issue_price_difference_refund(
            difference, f"Marked {removed_name} unavailable", user
        )
        from users.audit import log_staff_change, money

        log_staff_change(
            action="order.line_removed",
            target_type="order",
            target_id=self.pk,
            order_id=self.pk,
            summary=f"Marked {removed_name} unavailable on order #{self.pk}",
            changes={
                "product_name": removed_name,
                "availability": LineAvailability.UNAVAILABLE,
                "line_total": money(difference),
                "total": money(self.total),
                "refund_ids": [refund.pk for refund in refunds],
            },
        )
        return refunds

    @transaction.atomic
    def remove_line(self, item, user, note=""):
        return self.mark_line_unavailable(item, user, note=note)

    @transaction.atomic
    def replace_line(self, item, product, variant, quantity, user):
        self._ensure_lines_editable()
        if item.order_id != self.id:
            raise ValidationError("That line is not on this order.")
        if item.availability in (LineAvailability.UNAVAILABLE, LineAvailability.REPLACED):
            raise ValidationError("That item is not being shipped.")
        if variant is not None:
            product = variant.product
        old_name = item.product_name
        old_total = Decimal(item.line_total)
        self._restock_line(item)
        stock_taken = self._take_stock(product, variant, quantity)

        if variant is not None:
            unit_price = variant.price if variant.price is not None else product.price
            barcode = variant.barcode or ""
            opts = list(variant.options.select_related("attribute").all())
            variant_description = ", ".join(f"{o.attribute.name}: {o.value}" for o in opts)
        else:
            unit_price = product.price
            barcode = product.barcode or ""
            variant_description = ""

        new_total = (Decimal(unit_price) * quantity).quantize(Decimal("0.01"))
        item.availability = LineAvailability.REPLACED
        item.decided_at = timezone.now()
        item.decided_by = user if getattr(user, "is_authenticated", False) else None
        item.save(update_fields=["availability", "decided_at", "decided_by"])
        replacement = OrderItem.objects.create(
            order=self,
            product=product,
            variant=variant,
            product_name=product.name,
            variant_description=variant_description,
            barcode=barcode,
            quantity=quantity,
            unit_price=unit_price,
            line_total=new_total,
            availability=LineAvailability.CONFIRMED,
            replaces=item,
            decided_at=item.decided_at,
            decided_by=item.decided_by,
            stock_taken=stock_taken,
        )

        self.recalculate_totals()
        difference = (old_total - new_total).quantize(Decimal("0.01"))
        refunds = self.issue_price_difference_refund(
            difference, f"Replaced {old_name} with {product.name}", user
        )
        from users.audit import log_staff_change, money

        log_staff_change(
            action="order.line_replaced",
            target_type="order",
            target_id=self.pk,
            order_id=self.pk,
            summary=f"Replaced {old_name} with {product.name} on order #{self.pk}",
            changes={
                "from_item_id": item.pk,
                "to_item_id": replacement.pk,
                "from_product": old_name,
                "to_product": product.name,
                "from_line_total": money(old_total),
                "to_line_total": money(new_total),
                "quantity": quantity,
                "total": money(self.total),
                "refund_ids": [refund.pk for refund in refunds],
            },
        )
        return refunds


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)

    # Optional links to catalog (kept nullable so order history survives catalog changes)
    product = models.ForeignKey("products.Product", on_delete=models.SET_NULL, null=True, blank=True)
    variant = models.ForeignKey(
        "products.ProductVariant", on_delete=models.SET_NULL, null=True, blank=True
    )

    product_name = models.CharField(max_length=255)  # snapshot
    variant_description = models.CharField(max_length=255, blank=True)  # snapshot like "Color: Red, Size: XL"
    barcode = models.CharField(max_length=64, blank=True)  # snapshot (if variant)

    quantity = models.PositiveIntegerField()
    stock_taken = models.BooleanField(
        default=True,
        help_text="True when checkout reduced a stock number for this line.",
    )
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    availability = models.CharField(
        max_length=20,
        choices=LineAvailability.choices,
        default=LineAvailability.PENDING,
        db_index=True,
    )
    availability_note = models.CharField(max_length=255, blank=True)
    replaces = models.OneToOneField(
        "self",
        related_name="replacement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="decided_order_items",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"


class Shipment(models.Model):
    """
    Shipping info for an order (carrier/tracking/status).
    """

    order = models.OneToOneField(Order, related_name="shipment", on_delete=models.CASCADE)

    status = models.CharField(
        max_length=30,
        choices=ShippingStatus.choices,
        default=ShippingStatus.ORDER_PLACED,
        db_index=True,
    )
    carrier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True, db_index=True)
    tracking_url = models.URLField(blank=True)

    estimated_delivery_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def mark_delivered(self):
        self.status = ShippingStatus.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=["status", "delivered_at", "updated_at"])

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        writing_status = _writes_status(update_fields)
        old_status = None
        if self.pk:
            old_status = Shipment.objects.filter(pk=self.pk).values_list("status", flat=True).first()
        if writing_status:
            self._require_lines_ready(old_status)
        with transaction.atomic():
            super().save(*args, **kwargs)
            if getattr(self, "_aligning_fulfillment", False):
                return
            if writing_status and old_status != self.status:
                self._align_order()

    def _align_order(self):
        order = self.order
        order.refresh_from_db(fields=["status", "is_fully_paid", "total"])
        target = order_status_aligned_to_shipment(self.status, order)
        if target is None or order.status == target:
            return
        order.status = target
        order._aligning_fulfillment = True
        try:
            order.save(update_fields=["status", "updated_at"])
        finally:
            order._aligning_fulfillment = False

    def _require_lines_ready(self, old_status):
        forward = (
            ShippingStatus.DISPATCHED,
            ShippingStatus.OUT_FOR_DELIVERY,
            ShippingStatus.DELIVERED,
        )
        if self.status not in forward or self.status == old_status:
            return
        order_status = Order.objects.filter(pk=self.order_id).values_list("status", flat=True).first()
        if order_status in (OrderStatus.SHIPPING, OrderStatus.COMPLETE):
            return
        self.order.assert_ready_to_ship()

    def __str__(self):
        return f"Shipment for Order #{self.order_id}"


class ShipmentEvent(models.Model):
    """
    Timestamped history of shipping status updates for the user to track progress.
    """

    shipment = models.ForeignKey(Shipment, related_name="events", on_delete=models.CASCADE)
    status = models.CharField(max_length=30, choices=ShippingStatus.choices, db_index=True)
    message = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["occurred_at", "id"]

    def save(self, *args, **kwargs):
        previous_status = None
        if self.pk:
            previous_status = (
                ShipmentEvent.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )

        with transaction.atomic():
            super().save(*args, **kwargs)
            if previous_status != self.status:
                self._advance_shipment()

    def _advance_shipment(self):
        """
        A dispatched, out-for-delivery, or delivered event moves the shipment
        forward. Shipment.save then keeps the order on the same step.
        An earlier event does not rewind a parcel that has already moved on.
        """
        rank = {
            ShippingStatus.ORDER_PLACED: 0,
            ShippingStatus.DISPATCHED: 1,
            ShippingStatus.OUT_FOR_DELIVERY: 2,
            ShippingStatus.DELIVERED: 3,
        }
        event_rank = rank.get(self.status, 0)
        if event_rank < 1:
            return

        shipment = Shipment.objects.select_related("order").get(pk=self.shipment_id)
        if event_rank > rank.get(shipment.status, 0):
            shipment.status = self.status
            update_fields = ["status", "updated_at"]
            if self.status == ShippingStatus.DELIVERED and shipment.delivered_at is None:
                shipment.delivered_at = self.occurred_at or timezone.now()
                update_fields.append("delivered_at")
            shipment.save(update_fields=update_fields)
            return

        if self.status == ShippingStatus.DELIVERED and shipment.delivered_at is None:
            shipment.delivered_at = self.occurred_at or timezone.now()
            shipment.save(update_fields=["delivered_at", "updated_at"])
        shipment._align_order()

    def __str__(self):
        return f"{self.status} @ {self.occurred_at:%Y-%m-%d %H:%M}"


class PaymentProvider(models.TextChoices):
    INTASEND = "intasend", "IntaSend"
    STRIPE = "stripe", "Stripe"
    PESAPAL = "pesapal", "Pesapal"
    CASH = "cash", "Cash"
    OTHER = "other", "Other"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"
    REFUND_INITIATED = "refund_initiated", "Refund initiated"
    REFUNDED = "refunded", "Refunded"


class RefundStatus(models.TextChoices):
    INITIATED = "initiated", "Initiated"
    COMPLETED = "completed", "Completed"


CLOSED_PAYMENT_STATUSES = (
    PaymentStatus.COMPLETED,
    PaymentStatus.FAILED,
    PaymentStatus.CANCELLED,
    PaymentStatus.REFUND_INITIATED,
    PaymentStatus.REFUNDED,
)


class PaymentCredentials(models.Model):
    """
    Stores payment provider credentials for the whole app.
    The private/secret key is encrypted on save (via set_private_key) and stored
    in encrypted_private_key. It is only decrypted when calling get_private_key()
    to initialize provider API clients (IntaSend, Stripe); the decrypted value
    is never persisted or returned in API responses.
    """

    provider = models.CharField(max_length=20, choices=PaymentProvider.choices, db_index=True)
    environment = models.CharField(
        max_length=20, choices=[("sandbox", "Sandbox"), ("live", "Live")], default="sandbox"
    )

    # e.g. IntaSend publishable key (stored in plain text; not sensitive)
    api_key = models.CharField(max_length=255, blank=True)
    # Provider secret/private key stored encrypted at rest. Set only via set_private_key().
    encrypted_private_key = models.TextField(blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["provider", "environment", "is_active"]),
        ]

    @staticmethod
    def _fernet():
        """
        Derive a stable Fernet key from Django SECRET_KEY.
        """
        secret = getattr(settings, "SECRET_KEY", None)
        if not secret:
            raise ImproperlyConfigured("SECRET_KEY must be set to use PaymentCredentials encryption.")
        digest = sha256(force_bytes(secret)).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    def set_private_key(self, raw_private_key: str):
        """Encrypt and store the private key. Call this on create/update; never persist raw key."""
        if not raw_private_key:
            self.encrypted_private_key = ""
            return
        f = self._fernet()
        self.encrypted_private_key = f.encrypt(force_bytes(raw_private_key)).decode("utf-8")

    def get_private_key(self) -> str:
        """Decrypt and return the private key. Only call when needed for provider API (IntaSend/Stripe)."""
        if not self.encrypted_private_key:
            return ""
        f = self._fernet()
        return f.decrypt(force_bytes(self.encrypted_private_key)).decode("utf-8")

    def __str__(self):
        return f"{self.provider} ({self.environment})"

    def save(self, *args, **kwargs):
        """
        Ensure only one active credentials row exists per (provider, environment).
        If encrypted_private_key looks like plain text (e.g. was pasted in admin), encrypt it.
        """
        # Fernet ciphertext in base64 always starts with "gAAAAA"; otherwise treat as plain text
        if self.encrypted_private_key and not self.encrypted_private_key.strip().startswith("gAAAAA"):
            self.set_private_key(self.encrypted_private_key)
        super().save(*args, **kwargs)
        if self.is_active:
            PaymentCredentials.objects.filter(
                provider=self.provider,
                environment=self.environment,
                is_active=True,
            ).exclude(pk=self.pk).update(is_active=False)


class OrderPayment(models.Model):
    """
    Tracks payment attempts/links/status for an Order.
    """

    order = models.ForeignKey(Order, related_name="payments", on_delete=models.CASCADE)
    provider = models.CharField(max_length=20, choices=PaymentProvider.choices, db_index=True)
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING, db_index=True
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="KES")
    usd_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Units of this payment currency per 1 USD when the payment was created.",
    )

    # External ids / links
    checkout_url = models.URLField(blank=True)
    transaction_id = models.CharField(max_length=64, unique=True, null=True, blank=True, db_index=True)
    provider_payment_id = models.CharField(max_length=255, blank=True, db_index=True)
    provider_invoice_id = models.CharField(max_length=255, blank=True, db_index=True)
    provider_state = models.CharField(max_length=255, blank=True)

    raw_provider_response = models.JSONField(default=dict, blank=True)

    # Soft delete (staff)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="deleted_order_payments"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.provider} for Order #{self.order_id} ({self.status})"

    def _sync_order_paid_flag(self):
        self.order.apply_paid_state()

    def soft_delete(self, user=None):
        """
        Soft delete the payment and recompute order paid flag.
        """
        if self.is_deleted:
            return
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user is not None:
            self.deleted_by = user
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "updated_at"])

    def save(self, *args, **kwargs):
        normalized = (self.transaction_id or "").strip() or None
        if self.transaction_id != normalized:
            self.transaction_id = normalized
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = list(set(update_fields) | {"transaction_id"})

        # Track if status is changing to COMPLETED
        is_newly_completed = False
        previous_status = None
        is_new = self.pk is None
        if self.pk:
            try:
                old_payment = OrderPayment.objects.get(pk=self.pk)
                previous_status = old_payment.status
                if old_payment.status != PaymentStatus.COMPLETED and self.status == PaymentStatus.COMPLETED:
                    is_newly_completed = True
            except OrderPayment.DoesNotExist:
                pass

        super().save(*args, **kwargs)
        self._sync_order_paid_flag()
        from users.audit import log_staff_change, money

        if is_new:
            log_staff_change(
                action="payment.recorded",
                target_type="payment",
                target_id=self.pk,
                order_id=self.order_id,
                summary=f"Recorded {self.provider} payment {money(self.amount)} {self.currency} on order #{self.order_id}",
                changes={
                    "provider": self.provider,
                    "status": self.status,
                    "amount": money(self.amount),
                    "currency": self.currency,
                    "transaction_id": self.transaction_id,
                },
            )
        elif previous_status is not None and previous_status != self.status:
            log_staff_change(
                action="payment.status_changed",
                target_type="payment",
                target_id=self.pk,
                order_id=self.order_id,
                summary=f"Payment #{self.pk} on order #{self.order_id} {previous_status} -> {self.status}",
                changes={"status": {"from": previous_status, "to": self.status}},
            )

        # Send confirmation email when payment is completed
        if is_newly_completed:
            transaction.on_commit(lambda: send_order_confirmation_email(self.order_id))

    def refundable_amount(self) -> Decimal:
        used = self.refunds.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        remaining = (Decimal(self.amount) - Decimal(used)).quantize(Decimal("0.01"))
        if remaining < 0:
            return Decimal("0.00")
        return remaining

    def delete(self, *args, **kwargs):
        """
        Default to soft delete. Pass hard=True to hard delete.
        """
        hard = kwargs.pop("hard", False)
        if not hard:
            user = kwargs.pop("user", None)
            self.soft_delete(user=user)
            # Django expects delete() to return (count, details); we mimic a single-row delete.
            return (1, {self.__class__.__name__: 1})

        order = self.order
        res = super().delete(*args, **kwargs)
        order.apply_paid_state()
        return res


class OrderRefund(models.Model):
    """
    Refund of a completed payment on a cancelled order.
    Initiated and completed refunds are what the order and payment show.
    """

    order = models.ForeignKey(Order, related_name="refunds", on_delete=models.CASCADE)
    payment = models.ForeignKey(OrderPayment, related_name="refunds", on_delete=models.PROTECT)
    status = models.CharField(
        max_length=20,
        choices=RefundStatus.choices,
        default=RefundStatus.INITIATED,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10)
    reason = models.TextField()
    transaction_id = models.CharField(max_length=64, unique=True, db_index=True)
    provider_refund_id = models.CharField(max_length=255, blank=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="initiated_refunds",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"Refund {self.status} for Order #{self.order_id}"

    def save(self, *args, **kwargs):
        if self.payment_id and not self.order_id:
            self.order_id = self.payment.order_id

        self.reason = (self.reason or "").strip()
        if not self.reason:
            raise ValidationError("A reason is required.")
        self.transaction_id = (self.transaction_id or "").strip()
        if not self.transaction_id:
            self.transaction_id = f"rf-{uuid.uuid4().hex}"

        previous_status = None
        previous_amount = None
        if self.pk:
            previous = OrderRefund.objects.filter(pk=self.pk).values("status", "amount").first()
            if previous is not None:
                previous_status = previous["status"]
                previous_amount = previous["amount"]

        if self.status == RefundStatus.COMPLETED and self.completed_at is None:
            self.completed_at = timezone.now()
        elif self.status != RefundStatus.COMPLETED:
            self.completed_at = None

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = list(
                set(update_fields) | {"status", "completed_at", "updated_at", "reason", "transaction_id"}
            )

        with transaction.atomic():
            super().save(*args, **kwargs)
            from users.audit import log_staff_change, money

            if previous_status is None:
                log_staff_change(
                    action="refund.recorded",
                    target_type="refund",
                    target_id=self.pk,
                    order_id=self.order_id,
                    summary=f"Refund {money(self.amount)} {self.currency} {self.status} for order #{self.order_id}",
                    changes={
                        "payment_id": self.payment_id,
                        "status": self.status,
                        "amount": money(self.amount),
                        "currency": self.currency,
                        "reason": self.reason,
                        "transaction_id": self.transaction_id,
                    },
                )
            elif previous_status != self.status:
                log_staff_change(
                    action="refund.status_changed",
                    target_type="refund",
                    target_id=self.pk,
                    order_id=self.order_id,
                    summary=f"Refund #{self.pk} on order #{self.order_id} {previous_status} -> {self.status}",
                    changes={
                        "status": {"from": previous_status, "to": self.status},
                        "amount": money(self.amount),
                        "currency": self.currency,
                    },
                )
            amount_changed = previous_amount is not None and Decimal(previous_amount) != Decimal(self.amount)
            if previous_status != self.status or amount_changed:
                self._reflect_status()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        self._reflect_status()
        return result

    def _reflect_status(self):
        payment = OrderPayment.objects.get(pk=self.payment_id)
        if payment.status not in (
            PaymentStatus.COMPLETED,
            PaymentStatus.REFUND_INITIATED,
            PaymentStatus.REFUNDED,
        ):
            payment.order.apply_paid_state()
            self._reflect_on_order()
            return

        completed = payment.refunds.filter(status=RefundStatus.COMPLETED).aggregate(total=Sum("amount"))[
            "total"
        ] or Decimal("0")
        has_initiated = payment.refunds.filter(status=RefundStatus.INITIATED).exists()
        if Decimal(completed) >= Decimal(payment.amount):
            target_status = PaymentStatus.REFUNDED
        elif has_initiated:
            target_status = PaymentStatus.REFUND_INITIATED
        else:
            target_status = PaymentStatus.COMPLETED

        if payment.status != target_status:
            payment.status = target_status
            payment.save(update_fields=["status", "updated_at"])
        else:
            payment._sync_order_paid_flag()
        self._reflect_on_order()

    def _reflect_on_order(self):
        if self.order_id in _refund_commands.get():
            return
        order = Order.objects.get(pk=self.order_id)
        order.derive_refunded_status()
