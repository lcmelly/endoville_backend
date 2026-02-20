"""
Serializers for orders app.
"""

from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from products.models import Product, ProductVariant, VariationOption

from .models import (
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
    shipping_address = ShippingAddressSerializer()
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

    def validate(self, attrs):
        provider = attrs.get("provider")
        method = attrs.get("method")

        manual_providers = {PaymentProvider.CASH, PaymentProvider.OTHER}
        if provider in manual_providers:
            if method != "manual":
                raise serializers.ValidationError("Cash/Other payments must use method='manual'.")
            return attrs

        # gateway providers
        if provider == PaymentProvider.INTASEND and method not in ["link", "stk"]:
            raise serializers.ValidationError("IntaSend supports method='link' or method='stk'.")
        if provider == PaymentProvider.STRIPE and method != "checkout":
            raise serializers.ValidationError("Stripe supports method='checkout'.")

        return attrs


class PaymentCredentialsSerializer(serializers.ModelSerializer):
    """
    Staff-facing serializer. The decrypted private key is never returned.
    Provide `private_key` to set/rotate the secret (stored encrypted).
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
            obj.set_private_key(raw)
            obj.save(update_fields=["encrypted_private_key", "updated_at"])
        return obj

    def update(self, instance, validated_data):
        raw = validated_data.pop("private_key", None)
        obj = super().update(instance, validated_data)
        if raw is not None:
            obj.set_private_key(raw)
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

