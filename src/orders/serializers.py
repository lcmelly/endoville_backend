"""
Serializers for orders app.
"""

from decimal import Decimal

from background_task.models import CompletedTask, Task
from django.db import transaction
from rest_framework import serializers

from products.models import Product, ProductVariant, VariationOption

from .currency_utils import order_total_in_currency
from .models import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderPayment,
    PaymentProvider,
    PaymentCredentials,
    Shipment,
    ShipmentEvent,
    ShippingAddress,
)


class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = [
            "id",
            "full_name",
            "phone",
            "email",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "country",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ShipmentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentEvent
        fields = ["id", "status", "message", "location", "occurred_at"]
        read_only_fields = ["id"]


class ShipmentSerializer(serializers.ModelSerializer):
    events = ShipmentEventSerializer(many=True, read_only=True)

    class Meta:
        model = Shipment
        fields = [
            "id",
            "status",
            "carrier",
            "tracking_number",
            "tracking_url",
            "estimated_delivery_at",
            "delivered_at",
            "created_at",
            "updated_at",
            "events",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "variant",
            "product_name",
            "variant_description",
            "barcode",
            "quantity",
            "unit_price",
            "line_total",
        ]
        read_only_fields = ["id", "product_name", "variant_description", "barcode", "line_total"]


class OrderPaymentSummarySerializer(serializers.ModelSerializer):
    """Payment summary for embedding in order responses (excludes raw provider response)."""

    class Meta:
        model = OrderPayment
        fields = [
            "id",
            "provider",
            "status",
            "amount",
            "currency",
            "checkout_url",
            "provider_payment_id",
            "provider_invoice_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "provider",
            "status",
            "amount",
            "currency",
            "checkout_url",
            "provider_payment_id",
            "provider_invoice_id",
            "created_at",
            "updated_at",
        ]


class OrderSerializer(serializers.ModelSerializer):
    shipping_address = ShippingAddressSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    shipment = ShipmentSerializer(read_only=True)
    payments = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "status",
            "shipping_address",
            "subtotal",
            "shipping_fee",
            "total",
            "is_fully_paid",
            "notes",
            "created_at",
            "updated_at",
            "items",
            "shipment",
            "payments",
        ]
        read_only_fields = ["id", "user", "subtotal", "total", "created_at", "updated_at"]

    def get_payments(self, obj):
        """Payments for this order (excludes soft-deleted)."""
        qs = obj.payments.filter(is_deleted=False).order_by("-created_at")
        return OrderPaymentSummarySerializer(qs, many=True, context=self.context).data


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    unit_price = serializers.SerializerMethodField()
    line_total = serializers.SerializerMethodField()
    variant_description = serializers.SerializerMethodField()
    barcode = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "variant",
            "quantity",
            "product_name",
            "variant_description",
            "barcode",
            "unit_price",
            "line_total",
        ]
        read_only_fields = [
            "id",
            "product_name",
            "variant_description",
            "barcode",
            "unit_price",
            "line_total",
        ]

    def _resolved_product(self, obj):
        return obj.variant.product if obj.variant else obj.product

    def _resolved_unit_price(self, obj):
        if obj.variant:
            if obj.variant.price is not None:
                return Decimal(obj.variant.price)
            return Decimal(obj.variant.product.price)
        return Decimal(obj.product.price)

    def get_product_name(self, obj):
        product = self._resolved_product(obj)
        return product.name if product else ""

    def get_unit_price(self, obj):
        return self._resolved_unit_price(obj)

    def get_line_total(self, obj):
        return (self._resolved_unit_price(obj) * obj.quantity).quantize(Decimal("0.01"))

    def get_variant_description(self, obj):
        if not obj.variant:
            return ""
        opts = list(obj.variant.options.select_related("attribute").all())
        if not opts:
            return ""
        return ", ".join([f"{o.attribute.name}: {o.value}" for o in opts])

    def get_barcode(self, obj):
        if obj.variant:
            return obj.variant.barcode or ""
        return obj.product.barcode or ""


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ["id", "user", "items", "subtotal", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "subtotal", "created_at", "updated_at"]

    def get_subtotal(self, obj):
        total = Decimal("0")
        for item in obj.items.select_related("product", "variant", "variant__product"):
            if item.variant:
                unit_price = item.variant.price if item.variant.price is not None else item.variant.product.price
            else:
                unit_price = item.product.price
            total += Decimal(unit_price) * item.quantity
        return total.quantize(Decimal("0.01"))


class SyncCartItemSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), required=False)
    variant = serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.all(), required=False)
    quantity = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        product = attrs.get("product")
        variant = attrs.get("variant")
        if not product and not variant:
            raise serializers.ValidationError("Either product or variant is required.")
        if product and variant:
            raise serializers.ValidationError("Provide either product or variant, not both.")
        return attrs


class SyncCartSerializer(serializers.Serializer):
    items = SyncCartItemSerializer(many=True)


class CreateOrderItemSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), required=False)
    variant = serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.all(), required=False)
    quantity = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        product = attrs.get("product")
        variant = attrs.get("variant")
        if not product and not variant:
            raise serializers.ValidationError("Either product or variant is required.")
        if product and variant:
            raise serializers.ValidationError("Provide either product or variant, not both.")
        return attrs


class CreateOrderSerializer(serializers.Serializer):
    """Place an order. Shipping address is required."""

    shipping_address = ShippingAddressSerializer()  # required
    items = CreateOrderItemSerializer(many=True)
    shipping_fee = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal("0"))
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    @staticmethod
    def _variant_description(variant: ProductVariant) -> str:
        opts = list(variant.options.select_related("attribute").all())
        if not opts:
            return ""
        return ", ".join([f"{o.attribute.name}: {o.value}" for o in opts])

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        addr_data = validated_data["shipping_address"]
        items_data = validated_data["items"]
        shipping_fee = validated_data.get("shipping_fee", Decimal("0"))
        notes = validated_data.get("notes", "")

        shipping_address = ShippingAddress.objects.create(user=user, **addr_data)

        order = Order.objects.create(
            user=user,
            shipping_address=shipping_address,
            shipping_fee=shipping_fee,
            notes=notes,
        )

        subtotal = Decimal("0")
        for item in items_data:
            product = item.get("product")
            variant = item.get("variant")
            qty = item["quantity"]

            if variant:
                product = variant.product
                unit_price = variant.price if variant.price is not None else product.price
                barcode = variant.barcode
                variant_desc = self._variant_description(variant)

                if variant.stock is not None:
                    if variant.stock < qty:
                        raise serializers.ValidationError("Insufficient variant stock.")
                    variant.stock -= qty
                    variant.save(update_fields=["stock", "updated_at"])
            else:
                unit_price = product.price
                barcode = ""
                variant_desc = ""

            # fall back to product stock if variant doesn't manage stock
            if not variant and product.stock < qty:
                raise serializers.ValidationError("Insufficient product stock.")
            if not variant:
                product.stock -= qty
                product.save(update_fields=["stock"])

            line_total = (Decimal(unit_price) * qty).quantize(Decimal("0.01"))
            subtotal += line_total

            OrderItem.objects.create(
                order=order,
                product=product,
                variant=variant,
                product_name=product.name,
                variant_description=variant_desc,
                barcode=barcode,
                quantity=qty,
                unit_price=unit_price,
                line_total=line_total,
            )

        order.subtotal = subtotal
        order.total = subtotal + Decimal(order.shipping_fee)
        order.save(update_fields=["subtotal", "total", "updated_at"])

        # Create a shipment + first event (order placed) so users see tracking immediately.
        shipment = Shipment.objects.create(order=order)
        ShipmentEvent.objects.create(shipment=shipment, status=shipment.status, message="Order placed")
        # Order has been placed; clear persisted cart state for this user.
        cart = Cart.objects.filter(user=user).first()
        if cart:
            cart.clear_items()

        return order


class OrderPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderPayment
        fields = [
            "id",
            "order",
            "provider",
            "status",
            "amount",
            "currency",
            "checkout_url",
            "provider_payment_id",
            "provider_invoice_id",
            "provider_state",
            "raw_provider_response",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "checkout_url",
            "provider_payment_id",
            "provider_invoice_id",
            "provider_state",
            "raw_provider_response",
            "created_at",
            "updated_at",
        ]


class CreateOrderPaymentSerializer(serializers.Serializer):
    """
    Create a payment linked to an order. Request must include order id; payment is created for that order.
    Amount defaults to order total. For IntaSend link, optional phone_number/email are passed to checkout.
    """

    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())
    provider = serializers.ChoiceField(choices=PaymentProvider.choices)
    method = serializers.ChoiceField(
        choices=[
            ("link", "Payment link"),
            ("stk", "STK Push"),
            ("checkout", "Checkout"),
            ("manual", "Manual (cash/other)"),
        ]
    )

    # Optional overrides (otherwise we default to order.total / order currency)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    currency = serializers.CharField(required=False)

    # For STK push
    phone_number = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    narrative = serializers.CharField(required=False, allow_blank=True)

    # For Stripe Checkout (optional redirect URLs; fallback to settings)
    success_url = serializers.URLField(required=False, allow_blank=True)
    cancel_url = serializers.URLField(required=False, allow_blank=True)

    def validate(self, attrs):
        provider = attrs.get("provider")
        method = attrs.get("method")
        order = attrs.get("order")
        request = self.context.get("request")

        # Non-staff can only use IntaSend or Stripe
        if request and not getattr(request.user, "is_staff", False):
            if provider not in (PaymentProvider.INTASEND, PaymentProvider.STRIPE):
                raise serializers.ValidationError(
                    {"provider": "Only IntaSend and Stripe are available. Use staff API for cash/other."}
                )

        manual_providers = {PaymentProvider.CASH, PaymentProvider.OTHER}
        if provider in manual_providers:
            if method != "manual":
                raise serializers.ValidationError("Cash/Other payments must use method='manual'.")
            return attrs

        # gateway providers
        if provider == PaymentProvider.INTASEND and method not in ("link", "stk"):
            raise serializers.ValidationError("IntaSend supports method='link' or method='stk'.")
        if provider == PaymentProvider.INTASEND and method == "stk":
            phone = (attrs.get("phone_number") or "").strip()
            order = attrs.get("order")
            if not phone and order:
                ship = getattr(order, "shipping_address", None)
                phone = (getattr(ship, "phone", None) or "").strip()
            if not phone:
                raise serializers.ValidationError("phone_number is required for IntaSend STK push.")
        if provider == PaymentProvider.STRIPE and method != "checkout":
            raise serializers.ValidationError("Stripe supports method='checkout'.")

        return attrs


class PaymentCredentialsSerializer(serializers.ModelSerializer):
    """
    Staff-facing serializer. The raw private key is never returned and is never
    written to the DB in plain text: it is encrypted via set_private_key() before save.
    Provide `private_key` in the request to set/rotate the secret (encrypted at rest).
    """

    private_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    has_private_key = serializers.SerializerMethodField()

    class Meta:
        model = PaymentCredentials
        fields = [
            "id",
            "provider",
            "environment",
            "api_key",
            "private_key",
            "has_private_key",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "has_private_key", "created_at", "updated_at"]

    def get_has_private_key(self, obj):
        return bool(obj.encrypted_private_key)

    def create(self, validated_data):
        raw = validated_data.pop("private_key", None)
        obj = super().create(validated_data)
        if raw is not None:
            obj.set_private_key(raw)  # encrypt only; never persist raw key
            obj.save(update_fields=["encrypted_private_key", "updated_at"])
        return obj

    def update(self, instance, validated_data):
        raw = validated_data.pop("private_key", None)
        obj = super().update(instance, validated_data)
        if raw is not None:
            obj.set_private_key(raw)  # encrypt only; never persist raw key
            obj.save(update_fields=["encrypted_private_key", "updated_at"])
        return obj


class StaffOrderPaymentUpdateSerializer(serializers.ModelSerializer):
    """
    Staff-facing serializer to manually update payment status / provider fields.
    """

    class Meta:
        model = OrderPayment
        fields = [
            "id",
            "order",
            "provider",
            "status",
            "amount",
            "currency",
            "checkout_url",
            "provider_payment_id",
            "provider_invoice_id",
            "provider_state",
            "raw_provider_response",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class StaffShipmentUpdateSerializer(serializers.ModelSerializer):
    """
    Staff-facing serializer to update shipment status + tracking info.
    """

    class Meta:
        model = Shipment
        fields = [
            "id",
            "order",
            "status",
            "carrier",
            "tracking_number",
            "tracking_url",
            "estimated_delivery_at",
            "delivered_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class StaffShipmentEventCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentEvent
        fields = ["id", "shipment", "status", "message", "location", "occurred_at"]
        read_only_fields = ["id"]


class BackgroundTaskSerializer(serializers.ModelSerializer):
    """
    django-background-tasks `Task` rows (queued / due / running / failed in-queue).
    """

    status = serializers.SerializerMethodField()
    seconds_until_run = serializers.SerializerMethodField()
    repeat_interval_label = serializers.SerializerMethodField()
    last_error_preview = serializers.SerializerMethodField()
    locked_by_pid_running = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "task_name",
            "verbose_name",
            "run_at",
            "repeat",
            "repeat_interval_label",
            "repeat_until",
            "queue",
            "attempts",
            "failed_at",
            "last_error_preview",
            "locked_at",
            "locked_by",
            "locked_by_pid_running",
            "status",
            "seconds_until_run",
        ]
        read_only_fields = fields

    def get_locked_by_pid_running(self, obj):
        return obj.locked_by_pid_running()

    def get_repeat_interval_label(self, obj):
        if obj.repeat == Task.NEVER:
            return "never"
        for val, label in Task.REPEAT_CHOICES:
            if val == obj.repeat:
                return label
        return f"every {obj.repeat} seconds"

    def get_status(self, obj):
        from django.utils import timezone

        if obj.failed_at:
            return "failed"
        if obj.locked_at and obj.locked_by and not obj.failed_at:
            return "running"
        if obj.run_at and obj.run_at > timezone.now():
            return "scheduled"
        return "due"

    def get_seconds_until_run(self, obj):
        from django.utils import timezone

        if self.get_status(obj) != "scheduled":
            return None
        delta = (obj.run_at - timezone.now()).total_seconds()
        return int(max(0, round(delta)))

    def get_last_error_preview(self, obj):
        err = (obj.last_error or "").strip()
        if len(err) > 2000:
            return err[:2000] + "…"
        return err


class CompletedBackgroundTaskSerializer(serializers.ModelSerializer):
    """
    django-background-tasks `CompletedTask` archive (recent finished runs).
    """

    status = serializers.SerializerMethodField()
    last_error_preview = serializers.SerializerMethodField()
    locked_by_pid_running = serializers.SerializerMethodField()
    repeat_interval_label = serializers.SerializerMethodField()

    class Meta:
        model = CompletedTask
        fields = [
            "id",
            "task_name",
            "verbose_name",
            "run_at",
            "repeat",
            "repeat_interval_label",
            "repeat_until",
            "queue",
            "attempts",
            "failed_at",
            "last_error_preview",
            "locked_at",
            "locked_by",
            "locked_by_pid_running",
            "status",
        ]
        read_only_fields = fields

    def get_locked_by_pid_running(self, obj):
        return obj.locked_by_pid_running()

    def get_repeat_interval_label(self, obj):
        if obj.repeat == Task.NEVER:
            return "never"
        for val, label in Task.REPEAT_CHOICES:
            if val == obj.repeat:
                return label
        return f"every {obj.repeat} seconds"

    def get_status(self, obj):
        return "failed" if obj.failed_at else "succeeded"

    def get_last_error_preview(self, obj):
        err = (obj.last_error or "").strip()
        if len(err) > 2000:
            return err[:2000] + "…"
        return err

