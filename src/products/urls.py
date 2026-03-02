"""
URL configuration for products app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CategoryViewSet,
    CurrencyViewSet,
    ProductReviewViewSet,
    ProductVariantViewSet,
    ProductViewSet,
    SubcategoryViewSet,
    VariationAttributeViewSet,
    VariationOptionViewSet,
)

app_name = "products"

router = DefaultRouter()
router.register(r"currencies", CurrencyViewSet, basename="currency")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"subcategories", SubcategoryViewSet, basename="subcategory")
router.register(r"products", ProductViewSet, basename="product")
router.register(r"variants", ProductVariantViewSet, basename="variant")
router.register(r"product-reviews", ProductReviewViewSet, basename="product-review")
router.register(r"variation-attributes", VariationAttributeViewSet, basename="variation-attribute")
router.register(r"variation-options", VariationOptionViewSet, basename="variation-option")

urlpatterns = [
    path("", include(router.urls)),
]
