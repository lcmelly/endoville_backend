"""
API views for products app.
"""

from rest_framework import viewsets
from rest_framework.permissions import AllowAny

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
from .permissions import ProductReviewPermission, StaffWriteReadOnly
from .serializers import (
    CategorySerializer,
    CurrencySerializer,
    ProductReviewSerializer,
    ProductSerializer,
    ProductVariantSerializer,
    SubcategorySerializer,
    VariationAttributeSerializer,
    VariationOptionSerializer,
)


class CurrencyViewSet(viewsets.ModelViewSet):
    queryset = Currency.objects.all().order_by("code")
    serializer_class = CurrencySerializer
    permission_classes = [AllowAny]  # public read; write restricted in get_permissions if needed
    read_only_actions = {"list", "retrieve"}

    def get_permissions(self):
        if self.action in self.read_only_actions:
            return [AllowAny()]
        return [StaffWriteReadOnly()]


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    read_only_actions = {"list", "retrieve"}

    def get_permissions(self):
        if self.action in self.read_only_actions:
            return [AllowAny()]
        return [StaffWriteReadOnly()]


class SubcategoryViewSet(viewsets.ModelViewSet):
    queryset = Subcategory.objects.select_related("category").order_by("category__name", "name")
    serializer_class = SubcategorySerializer
    permission_classes = [AllowAny]
    read_only_actions = {"list", "retrieve"}

    def get_permissions(self):
        if self.action in self.read_only_actions:
            return [AllowAny()]
        return [StaffWriteReadOnly()]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = (
        Product.objects.prefetch_related(
            "subcategories",
            "variants",
            "reviews",
        )
        .order_by("-created_at")
    )
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    read_only_actions = {"list", "retrieve"}

    def get_permissions(self):
        if self.action in self.read_only_actions:
            return [AllowAny()]
        return [StaffWriteReadOnly()]


class VariationAttributeViewSet(viewsets.ModelViewSet):
    queryset = VariationAttribute.objects.all().order_by("name")
    serializer_class = VariationAttributeSerializer
    permission_classes = [AllowAny]
    read_only_actions = {"list", "retrieve"}

    def get_permissions(self):
        if self.action in self.read_only_actions:
            return [AllowAny()]
        return [StaffWriteReadOnly()]


class VariationOptionViewSet(viewsets.ModelViewSet):
    queryset = VariationOption.objects.select_related("attribute").order_by("attribute__name", "value")
    serializer_class = VariationOptionSerializer
    permission_classes = [AllowAny]
    read_only_actions = {"list", "retrieve"}

    def get_permissions(self):
        if self.action in self.read_only_actions:
            return [AllowAny()]
        return [StaffWriteReadOnly()]


class ProductVariantViewSet(viewsets.ModelViewSet):
    queryset = (
        ProductVariant.objects.select_related("product")
        .prefetch_related("options", "product__reviews")
        .order_by("-created_at")
    )
    serializer_class = ProductVariantSerializer
    permission_classes = [AllowAny]
    read_only_actions = {"list", "retrieve"}

    def get_permissions(self):
        if self.action in self.read_only_actions:
            return [AllowAny()]
        return [StaffWriteReadOnly()]


class ProductReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ProductReviewSerializer
    permission_classes = [ProductReviewPermission]

    def get_queryset(self):
        qs = ProductReview.objects.select_related("product", "order", "user").order_by("-created_at")
        product_id = self.request.query_params.get("product")
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)



