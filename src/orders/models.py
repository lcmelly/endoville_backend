"""
Models for ordering and shipping.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

import base64
from hashlib import sha256

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from django.utils.encoding import force_bytes


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
        previous_status = None
        if self.pk:
            previous_status = (
                Order.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )

        super().save(*args, **kwargs)

        if (
            self.status == OrderStatus.CANCELLED
            and previous_status != OrderStatus.CANCELLED
        ):
            self.payments.filter(
                status=PaymentStatus.PENDING,
                is_deleted=False,
            ).update(
                status=PaymentStatus.CANCELLED,
                updated_at=timezone.now(),
            )

    def recalculate_is_fully_paid(self) -> bool:
        """
        Order is fully paid if the sum of completed payment amounts (converted to primary
        currency) >= order total. Order total is in primary currency (e.g. USD).
        """
        from .currency_utils import amount_to_primary

        completed_sum = Decimal("0")
        for payment in self.payments.filter(status=PaymentStatus.COMPLETED, is_deleted=False):
            completed_sum += amount_to_primary(payment.amount, payment.currency)

        total = self.total
        if total is None:
            total = Decimal("0")
        elif not isinstance(total, Decimal):
            total = Decimal(str(total))

        return completed_sum >= total


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
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

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
        old_status = None
        if self.pk:
            try:
                old_status = Shipment.objects.get(pk=self.pk).status
            except Shipment.DoesNotExist:
                pass
        super().save(*args, **kwargs)
        # Auto-update order status from shipment status
        new_status = self.status
        if new_status != old_status:
            order = self.order
            if new_status == ShippingStatus.DELIVERED:
                if order.status != OrderStatus.COMPLETE:
                    Order.objects.filter(pk=order.pk).update(
                        status=OrderStatus.COMPLETE, updated_at=timezone.now()
                    )
            elif new_status in (ShippingStatus.DISPATCHED, ShippingStatus.OUT_FOR_DELIVERY):
                if order.status not in (OrderStatus.SHIPPING, OrderStatus.COMPLETE):
                    Order.objects.filter(pk=order.pk).update(
                        status=OrderStatus.SHIPPING, updated_at=timezone.now()
                    )

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

    # External ids / links
    checkout_url = models.URLField(blank=True)
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
        order = self.order
        should_be_paid = order.recalculate_is_fully_paid()
        updates = {}
        if order.is_fully_paid != should_be_paid:
            updates["is_fully_paid"] = should_be_paid
        # Auto: when fully paid, move to PROCESSING (if still payment-pending/placed)
        if should_be_paid and order.status in (OrderStatus.PAYMENT_PENDING, OrderStatus.PLACED):
            updates["status"] = OrderStatus.PROCESSING
        if updates:
            updates["updated_at"] = timezone.now()
            Order.objects.filter(pk=order.pk).update(**updates)

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
        # Track if status is changing to COMPLETED
        is_newly_completed = False
        if self.pk:
            try:
                old_payment = OrderPayment.objects.get(pk=self.pk)
                if old_payment.status != PaymentStatus.COMPLETED and self.status == PaymentStatus.COMPLETED:
                    is_newly_completed = True
            except OrderPayment.DoesNotExist:
                pass

        super().save(*args, **kwargs)
        self._sync_order_paid_flag()

        # Send confirmation email when payment is completed
        if is_newly_completed:
            transaction.on_commit(lambda: send_order_confirmation_email(self.order_id))

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
        should_be_paid = order.recalculate_is_fully_paid()
        updates = {}
        if order.is_fully_paid != should_be_paid:
            updates["is_fully_paid"] = should_be_paid
        if not should_be_paid and order.status == OrderStatus.PROCESSING:
            updates["status"] = OrderStatus.PAYMENT_PENDING
        if updates:
            updates["updated_at"] = timezone.now()
            Order.objects.filter(pk=order.pk).update(**updates)
        return res
