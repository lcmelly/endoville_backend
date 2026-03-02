from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

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


@admin.register(Currency)
class CurrencyAdmin(ImportExportModelAdmin):
    list_display = ["code", "name", "symbol", "usd_rate", "is_primary", "is_active", "created_at", "updated_at"]
    list_filter = ["is_primary", "is_active"]
    search_fields = ["code", "name", "symbol"]
    ordering = ["code"]


@admin.register(Category)
class CategoryAdmin(ImportExportModelAdmin):
    list_display = ["name"]
    search_fields = ["name", "description"]
    ordering = ["name"]


@admin.register(Subcategory)
class SubcategoryAdmin(ImportExportModelAdmin):
    list_display = ["name", "category"]
    list_filter = ["category"]
    search_fields = ["name", "category__name"]
    ordering = ["category__name", "name"]
    list_select_related = ["category"]


@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    list_display = ["name", "price", "stock", "avg_rating", "review_count", "image_refs_count", "slug", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = [
        "name",
        "slug",
        "description",
        "meta_title",
        "meta_description",
    ]
    ordering = ["-created_at"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Image refs")
    def image_refs_count(self, obj):
        refs = obj.image_refs or []
        return len(refs) if refs else "-"


@admin.register(VariationAttribute)
class VariationAttributeAdmin(ImportExportModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    ordering = ["name"]


@admin.register(VariationOption)
class VariationOptionAdmin(ImportExportModelAdmin):
    list_display = ["attribute", "value"]
    list_filter = ["attribute"]
    search_fields = ["value", "attribute__name"]
    ordering = ["attribute__name", "value"]
    list_select_related = ["attribute"]


@admin.register(ProductVariant)
class ProductVariantAdmin(ImportExportModelAdmin):
    list_display = ["product", "sku", "barcode", "price", "stock", "image_refs_count", "is_active", "updated_at"]
    list_filter = ["is_active", "created_at", "updated_at"]
    search_fields = ["barcode", "sku", "product__name"]
    ordering = ["-created_at"]
    list_select_related = ["product"]

    @admin.display(description="Image refs")
    def image_refs_count(self, obj):
        refs = obj.image_refs or []
        return len(refs) if refs else "-"


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "rating", "created_at"]
    list_filter = ["rating", "created_at"]
    search_fields = ["product__name", "body"]
    ordering = ["-created_at"]
    list_select_related = ["product", "user"]
    raw_id_fields = ["product", "user"]
