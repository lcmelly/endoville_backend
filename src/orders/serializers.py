"""
Serializers for orders app.
"""

from decimal import Decimal

from background_task.models import CompletedTask, Task
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from products.models import Product, ProductVariant, VariationOption
from users.models import CustomUser
from users.roles import has_staff_role

from .currency_utils import order_total_in_currency
from .shipping_fees import cart_shipping, quote_shipping, weight_grams
from .models import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderPayment,
    OrderRefund,
    OrderStatus,
    PaymentProvider,
    ShippingStatus,
    PaymentCredentials,
    PaymentStatus,
    RefundStatus,
    Shipment,
    ShipmentEvent,
    ShippingAddress,
    ShippingCountryRate,
    Warehouse,
)


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = [
            "id",
            "code",
            "name",
            "phone",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "country",
        ]
        read_only_fields = fields


class WarehouseUpdateSerializer(serializers.ModelSerializer):
    """Staff can read a warehouse. Only managers and admins can add or change the address."""

    class Meta:
        model = Warehouse
        fields = [
            "id",
            "code",
            "name",
            "phone",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "country",
            "is_active",
        ]
        read_only_fields = ["id", "is_active"]

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:
            fields["code"].read_only = True
        return fields

    def validate(self, attrs):
        required = ("name", "address_line_1", "city", "state", "postal_code", "country")
        if self.instance is None:
            required = ("code",) + required
        errors = {}
        for field in required:
            if self.instance is not None and field not in attrs:
                continue
            if not str(attrs.get(field, "")).strip():
                errors[field] = "This field is required."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


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
    replacement = serializers.SerializerMethodField()

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
            "availability",
            "availability_note",
            "replaces",
            "replacement",
        ]
        read_only_fields = [
            "id",
            "product_name",
            "variant_description",
            "barcode",
            "line_total",
            "availability",
            "availability_note",
            "replaces",
            "replacement",
        ]

    def get_replacement(self, obj):
        try:
            return obj.replacement.pk
        except OrderItem.DoesNotExist:
            return None


def _reject_until_lines_are_ready(order):
    try:
        order.assert_ready_to_ship()
    except DjangoValidationError as exc:
        message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
        raise serializers.ValidationError(message) from exc


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
            "transaction_id",
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
            "transaction_id",
            "provider_payment_id",
            "provider_invoice_id",
            "created_at",
            "updated_at",
        ]


class OrderRefundSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)

    def validate_reason(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("A reason is required.")
        return cleaned

    def validate_transaction_id(self, value):
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("A transaction id is required.")
        taken = OrderRefund.objects.filter(transaction_id=cleaned)
        if self.instance is not None:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError("This transaction id is already used.")
        return cleaned

    class Meta:
        model = OrderRefund
        fields = [
            "id",
            "order",
            "payment",
            "status",
            "amount",
            "currency",
            "reason",
            "transaction_id",
            "provider_refund_id",
            "initiated_by",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "order",
            "currency",
            "initiated_by",
            "completed_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        payment = attrs.get("payment") or getattr(self.instance, "payment", None)
        if payment is None:
            raise serializers.ValidationError({"payment": "This field is required."})
        if self.instance and attrs.get("payment") and attrs["payment"].pk != self.instance.payment_id:
            raise serializers.ValidationError({"payment": "Payment cannot be changed."})
        if payment.is_deleted:
            raise serializers.ValidationError({"payment": "Deleted payments cannot be refunded."})
        if payment.order.status not in (OrderStatus.CANCELLED, OrderStatus.REFUNDED):
            raise serializers.ValidationError({"payment": "Refunds are recorded for cancelled orders."})
        if self.instance is None and payment.status not in (
            PaymentStatus.COMPLETED,
            PaymentStatus.REFUND_INITIATED,
        ):
            raise serializers.ValidationError({"payment": "Only a completed payment can be refunded."})

        available = payment.refundable_amount()
        if self.instance is not None:
            available += Decimal(self.instance.amount)
        amount = attrs.get("amount", None)
        if amount is None and self.instance is None:
            if available <= 0:
                raise serializers.ValidationError({"amount": "This payment has already been refunded."})
            attrs["amount"] = available
        elif amount is not None and (amount <= 0 or amount > available):
            raise serializers.ValidationError(
                {"amount": "Amount cannot exceed the payment balance still held."}
            )

        status_value = attrs.get("status")
        if status_value is not None and status_value not in RefundStatus.values:
            raise serializers.ValidationError({"status": "Status must be initiated or completed."})
        return attrs

    def create(self, validated_data):
        payment = validated_data["payment"]
        validated_data["order"] = payment.order
        validated_data["currency"] = payment.currency
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            validated_data["initiated_by"] = request.user
        return super().create(validated_data)


class OrderSerializer(serializers.ModelSerializer):
    shipping_address = ShippingAddressSerializer(read_only=True)
    warehouse = WarehouseSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    shipment = ShipmentSerializer(read_only=True)
    payments = serializers.SerializerMethodField()
    refunds = OrderRefundSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "status",
            "shipping_address",
            "warehouse",
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
            "refunds",
        ]
        read_only_fields = ["id", "user", "subtotal", "total", "is_fully_paid", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        fee_changed = "shipping_fee" in validated_data
        order = super().update(instance, validated_data)
        if fee_changed:
            order.recalculate_totals()
        return order

    def validate(self, attrs):
        new_status = attrs.get("status")
        if (
            self.instance is not None
            and new_status in (OrderStatus.SHIPPING, OrderStatus.COMPLETE)
            and self.instance.status not in (OrderStatus.SHIPPING, OrderStatus.COMPLETE)
        ):
            _reject_until_lines_are_ready(self.instance)
        return attrs

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
    weight_grams = serializers.SerializerMethodField()
    shipping_fee = serializers.SerializerMethodField()
    shipping_fees = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "user",
            "items",
            "subtotal",
            "weight_grams",
            "shipping_fee",
            "shipping_fees",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "subtotal",
            "weight_grams",
            "shipping_fee",
            "shipping_fees",
            "created_at",
            "updated_at",
        ]

    def _lines(self, obj):
        return obj.items.select_related("product", "variant", "variant__product")

    def _shipping(self, obj):
        cached = getattr(self, "_shipping_for", None)
        if cached is not None and cached[0] == obj.pk:
            return cached[1]
        grams = sum(weight_grams(item.product, item.variant, item.quantity) for item in self._lines(obj))
        country = self.context.get("country") or ""
        request = self.context.get("request")
        if not country and request is not None:
            country = request.query_params.get("country") or ""
        payload = cart_shipping(country, grams)
        self._shipping_for = (obj.pk, payload)
        return payload

    def get_subtotal(self, obj):
        total = Decimal("0")
        for item in self._lines(obj):
            if item.variant:
                unit_price = item.variant.price if item.variant.price is not None else item.variant.product.price
            else:
                unit_price = item.product.price
            total += Decimal(unit_price) * item.quantity
        return total.quantize(Decimal("0.01"))

    def get_weight_grams(self, obj):
        return self._shipping(obj)["weight_grams"]

    def get_shipping_fee(self, obj):
        return self._shipping(obj)["shipping_fee"]

    def get_shipping_fees(self, obj):
        return self._shipping(obj)["shipping_fees"]


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
    country = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


class ReplaceOrderItemSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), required=False)
    variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.select_related("product"), required=False
    )
    quantity = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        product = attrs.get("product")
        variant = attrs.get("variant")
        if not product and not variant:
            raise serializers.ValidationError("Either product or variant is required.")
        if product and variant:
            raise serializers.ValidationError("Provide either product or variant, not both.")
        return attrs


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


class ShippingCountryInputSerializer(serializers.Serializer):
    country = serializers.CharField(max_length=100)
    unit_weight = serializers.IntegerField(min_value=1)
    fee = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))

    def validate_country(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Enter a country.")
        return name


class ShippingRatesSerializer(serializers.Serializer):
    countries = ShippingCountryInputSerializer(many=True)

    def validate_countries(self, rows):
        seen = set()
        for row in rows:
            key = row["country"].casefold()
            if key in seen:
                raise serializers.ValidationError(f"{row['country']} is listed more than once.")
            seen.add(key)
        return rows

    def save(self):
        data = self.validated_data
        with transaction.atomic():
            ShippingCountryRate.objects.all().delete()
            ShippingCountryRate.objects.bulk_create(
                [
                    ShippingCountryRate(
                        country=row["country"],
                        unit_weight=row["unit_weight"],
                        fee=row["fee"],
                    )
                    for row in data["countries"]
                ]
            )
        return ShippingCountryRate.objects.all()


def shipping_rates_payload():
    return {
        "countries": [
            {
                "country": row.country,
                "unit_weight": row.unit_weight,
                "fee": f"{Decimal(row.fee):.2f}",
            }
            for row in ShippingCountryRate.objects.all()
        ],
    }


class ShippingQuoteSerializer(serializers.Serializer):
    country = serializers.CharField(max_length=100)
    items = CreateOrderItemSerializer(many=True)

    def validate_country(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Enter a country.")
        return name

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("Add at least one item.")
        return items

    def quote(self):
        data = self.validated_data
        grams = sum(
            weight_grams(item.get("product"), item.get("variant"), item["quantity"])
            for item in data["items"]
        )
        try:
            fee = quote_shipping(data["country"], grams)
        except DjangoValidationError as exc:
            message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            raise serializers.ValidationError({"country": message}) from exc
        return {
            "country": data["country"],
            "weight_grams": grams,
            "shipping_fee": f"{fee:.2f}",
        }


class CreateOrderSerializer(serializers.Serializer):
    """Place an order. Shipping address is required. Staff may set user to the customer."""

    user = serializers.PrimaryKeyRelatedField(queryset=CustomUser.objects.all(), required=False)
    shipping_address = ShippingAddressSerializer()  # required
    items = CreateOrderItemSerializer(many=True)
    shipping_fee = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal("0"))
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_user(self, customer):
        request = self.context["request"]
        if customer.pk != request.user.pk and not has_staff_role(request.user, "Orders"):
            raise serializers.ValidationError("You can only place an order for yourself.")
        return customer

    @staticmethod
    def _variant_description(variant: ProductVariant) -> str:
        opts = list(variant.options.select_related("attribute").all())
        if not opts:
            return ""
        return ", ".join([f"{o.attribute.name}: {o.value}" for o in opts])

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        user = validated_data.get("user") or request.user

        addr_data = validated_data["shipping_address"]
        items_data = validated_data["items"]
        notes = validated_data.get("notes", "")
        grams = sum(
            weight_grams(item.get("product"), item.get("variant"), item["quantity"])
            for item in items_data
        )
        try:
            shipping_fee = quote_shipping(addr_data.get("country", ""), grams)
        except DjangoValidationError as exc:
            message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            raise serializers.ValidationError({"shipping_address": {"country": message}}) from exc

        shipping_address = ShippingAddress.objects.create(user=user, **addr_data)
        warehouse = Warehouse.objects.filter(is_active=True).order_by("id").first()

        order = Order.objects.create(
            user=user,
            shipping_address=shipping_address,
            warehouse=warehouse,
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
                barcode = variant.barcode or ""
                variant_desc = self._variant_description(variant)
            else:
                unit_price = product.price
                barcode = ""
                variant_desc = ""

            try:
                stock_taken = Order._take_stock(product, variant, qty)
            except DjangoValidationError as exc:
                message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
                raise serializers.ValidationError(message) from exc

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
                stock_taken=stock_taken,
            )

        order.subtotal = subtotal
        order.total = subtotal + Decimal(order.shipping_fee)
        order.save(update_fields=["subtotal", "total", "updated_at"])
        order.apply_paid_state()

        from users.audit import log_staff_change, money

        log_staff_change(
            action="order.created",
            target_type="order",
            target_id=order.pk,
            order_id=order.pk,
            summary=f"Created order #{order.pk} for {user.email}",
            changes={
                "user_id": user.pk,
                "total": money(order.total),
                "item_count": len(items_data),
            },
        )

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
            "usd_rate",
            "checkout_url",
            "transaction_id",
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
            "usd_rate",
            "checkout_url",
            "transaction_id",
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
        if request and not has_staff_role(request.user, "Orders"):
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
    Staff record a payment. transaction_id is optional and is returned with the payment.
    """

    transaction_id = serializers.CharField(max_length=64, required=False, allow_blank=True, allow_null=True)

    def validate_transaction_id(self, value):
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        taken = OrderPayment.objects.filter(transaction_id=cleaned)
        if self.instance is not None:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError("This transaction id is already used.")
        return cleaned

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
            "transaction_id",
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

    def validate(self, attrs):
        status_value = attrs.get("status", getattr(self.instance, "status", None))
        forward = (
            ShippingStatus.DISPATCHED,
            ShippingStatus.OUT_FOR_DELIVERY,
            ShippingStatus.DELIVERED,
        )
        if status_value in forward and self.instance is not None:
            order = self.instance.order
            if order.status not in (OrderStatus.SHIPPING, OrderStatus.COMPLETE):
                _reject_until_lines_are_ready(order)
        return attrs


class StaffShipmentEventCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentEvent
        fields = ["id", "shipment", "status", "message", "location", "occurred_at"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        status_value = attrs.get("status", getattr(self.instance, "status", None))
        shipment = attrs.get("shipment") or getattr(self.instance, "shipment", None)
        forward = (
            ShippingStatus.DISPATCHED,
            ShippingStatus.OUT_FOR_DELIVERY,
            ShippingStatus.DELIVERED,
        )
        if shipment is not None and status_value in forward:
            order = shipment.order
            if order.status not in (OrderStatus.SHIPPING, OrderStatus.COMPLETE):
                _reject_until_lines_are_ready(order)
        return attrs


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

