"""
Serializers for products app.
"""

from decimal import Decimal

from rest_framework import serializers

from .models import (
    Category,
    Currency,
    Product,
    ProductVariant,
    Subcategory,
    VariationAttribute,
    VariationOption,
)


def _get_display_currency(request):
    """Return active Currency for request.query_params['currency'] or None."""
    if not request or not getattr(request, "query_params", None):
        return None
    code = request.query_params.get("currency", "").strip().upper()
    if not code:
        return None
    return Currency.objects.filter(code=code, is_active=True).first()


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


class ProductVariantSerializer(serializers.ModelSerializer):
    options = serializers.PrimaryKeyRelatedField(
        queryset=VariationOption.objects.all(), many=True, required=False
    )
    options_details = VariationOptionSerializer(source="options", many=True, read_only=True)

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
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        is_staff = request and getattr(request, "user", None) and request.user.is_staff
        if not is_staff:
            data.pop("cost_price", None)
            # Currency conversion for non-staff
            display_currency = _get_display_currency(request)
            effective_price = instance.price if instance.price is not None else instance.product.price
            if display_currency and effective_price is not None:
                data["price"] = str(_convert_price(effective_price, display_currency))
                data["display_currency"] = display_currency.code
        return data


class ProductSerializer(serializers.ModelSerializer):
    subcategories = serializers.PrimaryKeyRelatedField(
        queryset=Subcategory.objects.all(), many=True, required=False
    )
    variants = serializers.SerializerMethodField()

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
            "created_at",
            "updated_at",
            "variants",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        is_staff = request and getattr(request, "user", None) and request.user.is_staff
        if not is_staff:
            data.pop("cost_price", None)
            # Currency conversion for non-staff: ?currency=KES etc.
            display_currency = _get_display_currency(request)
            if display_currency and instance.price is not None:
                data["price"] = str(_convert_price(instance.price, display_currency))
                data["display_currency"] = display_currency.code
        return data

    def get_variants(self, obj):
        qs = obj.variants.all()
        return ProductVariantSerializer(qs, many=True, context=self.context).data
