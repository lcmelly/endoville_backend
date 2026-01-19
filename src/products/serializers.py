"""
Serializers for products app.
"""

from rest_framework import serializers

from .models import (
    Category,
    Product,
    ProductVariant,
    Subcategory,
    VariationAttribute,
    VariationOption,
)


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
            "stock",
            "image_urls",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductSerializer(serializers.ModelSerializer):
    subcategories = serializers.PrimaryKeyRelatedField(
        queryset=Subcategory.objects.all(), many=True, required=False
    )
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "price",
            "stock",
            "image_urls",
            "subcategories",
            "meta_title",
            "meta_description",
            "slug",
            "created_at",
            "updated_at",
            "variants",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]
