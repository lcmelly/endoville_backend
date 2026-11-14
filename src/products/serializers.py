"""
Serializers for products app.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.db.models import Q
from rest_framework import serializers

from .models import (
    Brand,
    Category,
    Currency,
    Product,
    ProductReview,
    ProductVariant,
    Subcategory,
    VariationAttribute,
    VariationOption,
    explicit_track_stock,
)


def _require_stock_quantity_when_tracking(serializer, attrs):
    data = serializer.initial_data if isinstance(getattr(serializer, "initial_data", None), dict) else {}
    if "track_stock" not in data or not attrs.get("track_stock", False):
        return
    if "stock" in attrs:
        stock = attrs["stock"]
    elif serializer.instance is not None:
        stock = serializer.instance.stock
    else:
        stock = None
    if stock is None:
        raise serializers.ValidationError({"stock": "Enter a stock quantity to track it."})


def _save_stock_choice(serializer, method, *args):
    data = serializer.initial_data if isinstance(getattr(serializer, "initial_data", None), dict) else {}
    if "track_stock" not in data:
        return method(*args)
    with explicit_track_stock():
        return method(*args)


def _get_display_currency(request):
    """
    Return display Currency for non-staff product/variant responses.
    Uses ?currency=CODE if present and valid; otherwise defaults to primary currency (e.g. USD).
    Invalid or missing code falls back to primary. Returns None if no Currency exists in DB.
    """
    try:
        from orders.payments.stripe_rates import ensure_stripe_rates_fresh

        ensure_stripe_rates_fresh()
    except Exception:
        pass
    try:
        if not request or not getattr(request, "query_params", None):
            code = None
        else:
            code = request.query_params.get("currency", "").strip().upper() or None
        if code:
            currency = Currency.objects.filter(code=code, is_active=True).first()
            if currency:
                return currency
        return (
            Currency.objects.filter(is_primary=True, is_active=True).first()
            or Currency.objects.filter(code="USD", is_active=True).first()
        )
    except Exception:
        return None


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = [
            "id",
            "code",
            "name",
            "symbol",
            "usd_rate",
            "rate_synced_at",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "rate_synced_at", "created_at", "updated_at"]


def _convert_price(price_value, currency):
    """Convert price (stored in primary/USD) to display currency. Returns Decimal."""
    if price_value is None:
        return None
    return (Decimal(str(price_value)) * currency.usd_rate).quantize(Decimal("0.01"))


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description", "products_count", "products_sold"]


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = [
            "id",
            "name",
            "image_urls",
            "image_refs",
            "image_labels",
            "description",
            "products_count",
            "products_sold",
        ]


class SubcategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Subcategory
        fields = ["id", "name", "category"]


class VariationAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VariationAttribute
        fields = ["id", "name"]


class VariationOptionSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source="attribute.name", read_only=True)

    class Meta:
        model = VariationOption
        fields = ["id", "attribute", "attribute_name", "value"]


def reviews_for_viewer(product, request):
    qs = product.reviews.select_related("user").order_by("-created_at")
    user = getattr(request, "user", None) if request else None
    if user and user.is_authenticated and user.is_staff:
        return qs
    if user and user.is_authenticated:
        return qs.filter(Q(flag_reason="") | Q(user=user))
    return qs.filter(flag_reason="")


class ProductReviewSerializer(serializers.ModelSerializer):
    user_display = serializers.SerializerMethodField()
    is_flagged = serializers.SerializerMethodField()

    class Meta:
        model = ProductReview
        fields = [
            "id",
            "product",
            "order",
            "user",
            "user_display",
            "rating",
            "body",
            "is_anonymous",
            "is_flagged",
            "flag_reason",
            "flag_note",
            "flagged_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "is_flagged",
            "flag_reason",
            "flag_note",
            "flagged_at",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if getattr(self, "instance", None) is not None:
            self.fields["product"].read_only = True
            self.fields["order"].read_only = True

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        is_staff = bool(user and user.is_authenticated and user.is_staff)
        is_author = bool(user and user.is_authenticated and instance.user_id == user.pk)
        if not is_staff:
            data.pop("flag_note", None)
        if not is_staff and not is_author:
            data.pop("is_flagged", None)
            data.pop("flag_reason", None)
            data.pop("flagged_at", None)
        return data

    def get_is_flagged(self, obj):
        return bool(obj.flag_reason)

    def get_user_display(self, obj):
        if obj.is_anonymous:
            return "Anonymous"
        if not obj.user:
            return None
        first = (getattr(obj.user, "first_name", None) or "").strip()
        return first or "Customer"

    def validate_rating(self, value):
        if value < 0 or value > 5:
            raise serializers.ValidationError("Rating must be between 0 and 5.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                {"detail": "Authentication required to submit a review."}
            )
        if self.instance is not None:
            return attrs
        product = attrs.get("product")
        order = attrs.get("order")
        if not product:
            raise serializers.ValidationError({"product": "This field is required."})
        if not order:
            raise serializers.ValidationError(
                {"order": "Order is required. You can only review a product you purchased."}
            )
        from orders.models import SHIPPED_LINE_AVAILABILITY, OrderItem, OrderStatus

        if order.user_id != request.user.pk:
            raise serializers.ValidationError(
                {"order": "This order does not belong to you."}
            )
        if order.status != OrderStatus.COMPLETE:
            raise serializers.ValidationError(
                {"order": "Only completed orders can be used for reviews."}
            )
        if not order.is_fully_paid:
            raise serializers.ValidationError(
                {"order": "Order must be fully paid before you can review."}
            )
        shipped = OrderItem.objects.filter(
            order=order,
            availability__in=SHIPPED_LINE_AVAILABILITY,
        ).filter(Q(product_id=product.pk) | Q(variant__product_id=product.pk))
        if not shipped.exists():
            raise serializers.ValidationError(
                {"order": "You can only review a product that was shipped on this order."}
            )
        if ProductReview.objects.filter(product=product, user=request.user).exists():
            raise serializers.ValidationError(
                {"product": "You have already reviewed this product."}
            )
        return attrs


class ProductVariantSerializer(serializers.ModelSerializer):
    options = serializers.PrimaryKeyRelatedField(
        queryset=VariationOption.objects.all(), many=True, required=False
    )
    options_details = VariationOptionSerializer(source="options", many=True, read_only=True)
    avg_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "product",
            "options",
            "options_details",
            "sku",
            "barcode",
            "price",
            "cost_price",
            "track_stock",
            "stock",
            "image_urls",
            "image_refs",
            "is_active",
            "created_at",
            "updated_at",
            "avg_rating",
            "review_count",
            "reviews",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        _require_stock_quantity_when_tracking(self, attrs)
        return attrs

    def create(self, validated_data):
        return _save_stock_choice(self, super().create, validated_data)

    def update(self, instance, validated_data):
        return _save_stock_choice(self, super().update, instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        is_staff = request and getattr(request, "user", None) and request.user.is_staff
        if is_staff:
            display_currency = _get_display_currency(request)
            data["display_currency"] = getattr(display_currency, "code", None) or "USD"
            data["currency_symbol"] = getattr(display_currency, "symbol", None) or ""
        else:
            data.pop("cost_price", None)
            display_currency = _get_display_currency(request)
            effective_price = instance.price if instance.price is not None else getattr(instance.product, "price", None)
            if display_currency and effective_price is not None:
                data["price"] = str(_convert_price(effective_price, display_currency))
                data["display_currency"] = display_currency.code
                data["currency_symbol"] = display_currency.symbol or ""
            else:
                data["display_currency"] = getattr(display_currency, "code", None) or "USD"
                data["currency_symbol"] = getattr(display_currency, "symbol", None) or ""
        return data

    def get_avg_rating(self, obj):
        return str(obj.product.avg_rating) if obj.product.avg_rating is not None else None

    def get_review_count(self, obj):
        return obj.product.review_count

    def get_reviews(self, obj):
        request = self.context.get("request")
        qs = reviews_for_viewer(obj.product, request)[:10]
        return ProductReviewSerializer(qs, many=True, context=self.context).data


class ProductSerializer(serializers.ModelSerializer):
    brand = serializers.PrimaryKeyRelatedField(
        queryset=Brand.objects.all(), required=False, allow_null=True
    )
    brand_details = BrandSerializer(source="brand", read_only=True)
    subcategories = serializers.PrimaryKeyRelatedField(
        queryset=Subcategory.objects.all(), many=True, required=False
    )
    variants = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "brand",
            "brand_details",
            "price",
            "cost_price",
            "track_stock",
            "stock",
            "unit_weight",
            "sku",
            "barcode",
            "image_urls",
            "image_refs",
            "supplier_order_urls",
            "featured",
            "is_cancelled",
            "benefits",
            "ingredients",
            "how_to_use",
            "subcategories",
            "meta_title",
            "meta_description",
            "slug",
            "avg_rating",
            "review_count",
            "quantity_sold",
            "revenue",
            "created_at",
            "updated_at",
            "variants",
            "reviews",
        ]
        read_only_fields = ["id", "slug", "avg_rating", "review_count", "created_at", "updated_at"]

    def validate(self, attrs):
        _require_stock_quantity_when_tracking(self, attrs)
        return attrs

    def create(self, validated_data):
        return _save_stock_choice(self, super().create, validated_data)

    def update(self, instance, validated_data):
        return _save_stock_choice(self, super().update, instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        is_staff = request and getattr(request, "user", None) and request.user.is_staff
        if is_staff:
            display_currency = _get_display_currency(request)
            data["display_currency"] = getattr(display_currency, "code", None) or "USD"
            data["currency_symbol"] = getattr(display_currency, "symbol", None) or ""
        else:
            data.pop("cost_price", None)
            data.pop("supplier_order_urls", None)
            data.pop("revenue", None)
            display_currency = _get_display_currency(request)
            if display_currency and instance.price is not None:
                data["price"] = str(_convert_price(instance.price, display_currency))
                data["display_currency"] = display_currency.code
                data["currency_symbol"] = display_currency.symbol or ""
            else:
                data["display_currency"] = getattr(display_currency, "code", None) or "USD"
                data["currency_symbol"] = getattr(display_currency, "symbol", None) or ""
        return data

    def validate_supplier_order_urls(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Expected a list of URLs.")
        validator = URLValidator(schemes=["http", "https"])
        cleaned = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise serializers.ValidationError("Each supplier order URL must be a non-empty string.")
            url = item.strip()
            try:
                validator(url)
            except DjangoValidationError:
                raise serializers.ValidationError(f"Invalid URL: {url}")
            cleaned.append(url)
        return cleaned

    def get_variants(self, obj):
        qs = obj.variants.all()
        return ProductVariantSerializer(qs, many=True, context=self.context).data

    def get_reviews(self, obj):
        request = self.context.get("request")
        qs = reviews_for_viewer(obj, request)[:10]
        return ProductReviewSerializer(qs, many=True, context=self.context).data
