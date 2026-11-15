"""
API views for products app.
"""

from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from .models import (
    Brand,
    Category,
    Currency,
    Product,
    ProductReview,
    ProductVariant,
    ReviewFlagReason,
    Subcategory,
    VariationAttribute,
    VariationOption,
)
from .permissions import AdminWritePublicRead, ProductReviewPermission, StaffWriteReadOnly, StockWritePublicRead
from .serializers import (
    BrandSerializer,
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
        return [AdminWritePublicRead()]


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by("name")
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    read_only_actions = {"list", "retrieve"}

    def get_permissions(self):
        if self.action in self.read_only_actions:
            return [AllowAny()]
        return [StaffWriteReadOnly()]


class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all().order_by("name")
    serializer_class = BrandSerializer
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
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    read_only_actions = {"list", "retrieve"}

    def get_queryset(self):
        prefetches = [
            "subcategories",
            Prefetch(
                "variants",
                queryset=ProductVariant.objects.prefetch_related(
                    Prefetch(
                        "options",
                        queryset=VariationOption.objects.select_related("attribute"),
                    )
                ),
            ),
        ]
        if self.action == "retrieve":
            reviews = ProductReview.objects.select_related("user").order_by("-created_at")
            user = self.request.user
            if not (user.is_authenticated and user.is_staff):
                visible = Q(flag_reason="")
                if user.is_authenticated:
                    visible |= Q(user=user)
                reviews = reviews.filter(visible)
            prefetches.append(Prefetch("reviews", queryset=reviews))
        return (
            Product.objects.select_related("brand")
            .prefetch_related(*prefetches)
            .order_by("-created_at")
        )

    def get_permissions(self):
        if self.action in self.read_only_actions:
            return [AllowAny()]
        return [StockWritePublicRead()]


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
        .prefetch_related(
            Prefetch(
                "options",
                queryset=VariationOption.objects.select_related("attribute"),
            ),
        )
        .order_by("-created_at")
    )
    serializer_class = ProductVariantSerializer
    permission_classes = [AllowAny]
    read_only_actions = {"list", "retrieve"}

    def get_permissions(self):
        if self.action in self.read_only_actions:
            return [AllowAny()]
        return [StockWritePublicRead()]


class ProductReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ProductReviewSerializer
    permission_classes = [ProductReviewPermission]

    def get_permissions(self):
        if self.action in ("flag", "unflag"):
            return [IsAdminUser()]
        return super().get_permissions()

    def get_queryset(self):
        qs = ProductReview.objects.select_related("product", "order", "user").order_by("-created_at")
        product_id = self.request.query_params.get("product")
        if product_id:
            qs = qs.filter(product_id=product_id)
        user = self.request.user
        if not (user.is_authenticated and user.is_staff):
            visible = Q(flag_reason="")
            if user.is_authenticated:
                visible |= Q(user=user)
            qs = qs.filter(visible)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        if request.user.is_staff:
            return Response(
                {"detail": "Staff cannot delete reviews. Flag the review instead."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        review = self.get_object()
        if request.user.is_staff and review.user_id != request.user.pk:
            return Response(
                {"detail": "Staff cannot edit reviews. Flag the review instead."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        review = self.get_object()
        if request.user.is_staff and review.user_id != request.user.pk:
            return Response(
                {"detail": "Staff cannot edit reviews. Flag the review instead."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="flag")
    def flag(self, request, pk=None):
        review = self.get_object()
        reason = request.data.get("reason") or ""
        note = (request.data.get("note") or "").strip()
        if reason not in ReviewFlagReason.values:
            return Response(
                {"reason": "Choose PROFANITY, MALICIOUS, or OTHER."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if reason == ReviewFlagReason.OTHER and not note:
            return Response(
                {"note": "Describe the issue."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        review.flag_reason = reason
        review.flag_note = note
        review.flagged_by = request.user
        review.flagged_at = timezone.now()
        review.save(
            update_fields=["flag_reason", "flag_note", "flagged_by", "flagged_at", "updated_at"]
        )
        return Response(self.get_serializer(review).data)

    @action(detail=True, methods=["post"], url_path="unflag")
    def unflag(self, request, pk=None):
        review = self.get_object()
        review.flag_reason = ""
        review.flag_note = ""
        review.flagged_by = None
        review.flagged_at = None
        review.save(
            update_fields=["flag_reason", "flag_note", "flagged_by", "flagged_at", "updated_at"]
        )
        return Response(self.get_serializer(review).data)



