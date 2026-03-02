"""
Serializers for products app.
"""

from decimal import Decimal

from rest_framework import serializers

from .models import (
    Category,
    Currency,
    Product,
    ProductReview,
    ProductVariant,
    Subcategory,
    VariationAttribute,
    VariationOption,
)


def _get_display_currency(request):
    """
    Return display Currency for non-staff product/variant responses.
    Uses ?currency=CODE if present and valid; otherwise defaults to primary currency (e.g. USD).
    Invalid or missing code falls back to primary.
    """
    if not request or not getattr(request, "query_params", None):
        code = None
    else:
        code = request.query_params.get("currency", "").strip().upper() or None
    if code:
        currency = Currency.objects.filter(code=code, is_active=True).first()
        if currency:
            return currency
    # Default to primary currency (typically USD), else fallback to USD by code
    return (
        Currency.objects.filter(is_primary=True, is_active=True).first()
        or Currency.objects.filter(code="USD", is_active=True).first()
    )


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = [
            "id",
            "code",
            "name",
            "symbol",
            "usd_rate",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


def _convert_price(price_value, currency):
    """Convert price (stored in primary/USD) to display currency. Returns Decimal."""
    if price_value is None:
        return None
    return (Decimal(str(price_value)) * currency.usd_rate).quantize(Decimal("0.01"))


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description"]


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


class ProductReviewSerializer(serializers.ModelSerializer):
    user_display = serializers.SerializerMethodField()

    class Meta:
        model = ProductReview
        fields = [
            "id",
            "product",
            "user",
            "user_display",
            "rating",
            "body",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]

    def get_user_display(self, obj):
        if not obj.user:
            return None
        return getattr(obj.user, "email", None) or getattr(obj.user, "phone", None) or str(obj.user)

    def validate_rating(self, value):
        if value < 0 or value > 5:
            raise serializers.ValidationError("Rating must be between 0 and 5.")
        return value


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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        is_staff = request and getattr(request, "user", None) and request.user.is_staff
        if is_staff:
            display_currency = _get_display_currency(request)
            if display_currency:
                data["display_currency"] = display_currency.code
                data["currency_symbol"] = display_currency.symbol or ""
        else:
            data.pop("cost_price", None)
            display_currency = _get_display_currency(request)
            effective_price = instance.price if instance.price is not None else instance.product.price
            if display_currency and effective_price is not None:
                data["price"] = str(_convert_price(effective_price, display_currency))
                data["display_currency"] = display_currency.code
                data["currency_symbol"] = display_currency.symbol or ""
        return data

    def get_avg_rating(self, obj):
        return str(obj.product.avg_rating) if obj.product.avg_rating is not None else None

    def get_review_count(self, obj):
        return obj.product.review_count

    def get_reviews(self, obj):
        qs = obj.product.reviews.select_related("user").order_by("-created_at")[:10]
        return ProductReviewSerializer(qs, many=True, context=self.context).data


class ProductSerializer(serializers.ModelSerializer):
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
            "price",
            "cost_price",
            "stock",
            "image_urls",
            "image_refs",
            "subcategories",
            "meta_title",
            "meta_description",
            "slug",
            "avg_rating",
            "review_count",
            "created_at",
            "updated_at",
            "variants",
            "reviews",
        ]
        read_only_fields = ["id", "slug", "avg_rating", "review_count", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        is_staff = request and getattr(request, "user", None) and request.user.is_staff
        if is_staff:
            display_currency = _get_display_currency(request)
            if display_currency:
                data["display_currency"] = display_currency.code
                data["currency_symbol"] = display_currency.symbol or ""
        else:
            data.pop("cost_price", None)
            display_currency = _get_display_currency(request)
            if display_currency and instance.price is not None:
                data["price"] = str(_convert_price(instance.price, display_currency))
                data["display_currency"] = display_currency.code
                data["currency_symbol"] = display_currency.symbol or ""
        return data

    def get_variants(self, obj):
        qs = obj.variants.all()
        return ProductVariantSerializer(qs, many=True, context=self.context).data

    def get_reviews(self, obj):
        qs = obj.reviews.select_related("user").order_by("-created_at")[:10]
        return ProductReviewSerializer(qs, many=True, context=self.context).data
