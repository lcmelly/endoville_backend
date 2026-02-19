"""
API views for products app.
"""

from rest_framework import viewsets

from .models import (
    Category,
    Currency,
    Product,
    ProductVariant,
    Subcategory,
    VariationAttribute,
    VariationOption,
)
from .permissions import StaffWriteReadOnly
from .serializers import (
    CategorySerializer,
    CurrencySerializer,
    ProductSerializer,
    ProductVariantSerializer,
    SubcategorySerializer,
    VariationAttributeSerializer,
    VariationOptionSerializer,
)


class CurrencyViewSet(viewsets.ModelViewSet):
    queryset = Currency.objects.all().order_by("code")
    serializer_class = CurrencySerializer
    permission_classes = [StaffWriteReadOnly]


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [StaffWriteReadOnly]


class SubcategoryViewSet(viewsets.ModelViewSet):
    queryset = Subcategory.objects.select_related("category").order_by("category__name", "name")
    serializer_class = SubcategorySerializer
    permission_classes = [StaffWriteReadOnly]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.prefetch_related("subcategories", "variants").order_by("-created_at")
    serializer_class = ProductSerializer
    permission_classes = [StaffWriteReadOnly]


class VariationAttributeViewSet(viewsets.ModelViewSet):
    queryset = VariationAttribute.objects.all().order_by("name")
    serializer_class = VariationAttributeSerializer
    permission_classes = [StaffWriteReadOnly]


class VariationOptionViewSet(viewsets.ModelViewSet):
    queryset = VariationOption.objects.select_related("attribute").order_by("attribute__name", "value")
    serializer_class = VariationOptionSerializer
    permission_classes = [StaffWriteReadOnly]


class ProductVariantViewSet(viewsets.ModelViewSet):
    queryset = ProductVariant.objects.select_related("product").prefetch_related("options").order_by("-created_at")
    serializer_class = ProductVariantSerializer
    permission_classes = [StaffWriteReadOnly]

