from django import forms
from django.contrib import admin
from django.utils import timezone
from import_export.admin import ImportExportModelAdmin

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


@admin.register(Currency)
class CurrencyAdmin(ImportExportModelAdmin):
    list_display = ["code", "name", "symbol", "usd_rate", "rate_synced_at", "is_primary", "is_active", "created_at", "updated_at"]
    list_filter = ["is_primary", "is_active"]
    search_fields = ["code", "name", "symbol"]
    ordering = ["code"]


@admin.register(Category)
class CategoryAdmin(ImportExportModelAdmin):
    list_display = ["name", "products_count", "products_sold"]
    search_fields = ["name", "description"]
    ordering = ["name"]


@admin.register(Brand)
class BrandAdmin(ImportExportModelAdmin):
    list_display = ["name", "products_count", "products_sold", "brand_images_count"]
    search_fields = ["name", "description"]
    ordering = ["name"]

    @admin.display(description="Brand images")
    def brand_images_count(self, obj):
        urls = obj.image_urls or []
        return len(urls) if urls else "-"


@admin.register(Subcategory)
class SubcategoryAdmin(ImportExportModelAdmin):
    list_display = ["name", "category"]
    list_filter = ["category"]
    search_fields = ["name", "category__name"]
    ordering = ["category__name", "name"]
    list_select_related = ["category"]


@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    list_display = ["name", "brand", "featured", "is_cancelled", "sku", "barcode", "price", "track_stock", "stock", "quantity_sold", "revenue", "unit_weight", "avg_rating", "review_count", "image_refs_count", "supplier_order_urls_count", "slug", "created_at", "updated_at"]
    list_filter = ["brand", "featured", "is_cancelled", "track_stock", "created_at", "updated_at"]
    search_fields = [
        "name",
        "brand__name",
        "slug",
        "sku",
        "barcode",
        "description",
        "benefits",
        "ingredients",
        "how_to_use",
        "meta_title",
        "meta_description",
    ]
    ordering = ["-created_at"]
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ["brand"]
    raw_id_fields = ["brand"]

    @admin.display(description="Image refs")
    def image_refs_count(self, obj):
        refs = obj.image_refs or []
        return len(refs) if refs else "-"

    @admin.display(description="Supplier links")
    def supplier_order_urls_count(self, obj):
        urls = obj.supplier_order_urls or []
        return len(urls) if urls else "-"


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
    list_display = ["product", "sku", "barcode", "price", "track_stock", "stock", "image_refs_count", "is_active", "updated_at"]
    list_filter = ["is_active", "track_stock", "created_at", "updated_at"]
    search_fields = ["barcode", "sku", "product__name"]
    ordering = ["-created_at"]
    list_select_related = ["product"]

    @admin.display(description="Image refs")
    def image_refs_count(self, obj):
        refs = obj.image_refs or []
        return len(refs) if refs else "-"


class ProductReviewAdminForm(forms.ModelForm):
    class Meta:
        model = ProductReview
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        reason = cleaned.get("flag_reason") or ""
        note = (cleaned.get("flag_note") or "").strip()
        if reason == ReviewFlagReason.OTHER and not note:
            raise forms.ValidationError("Describe the issue when flagging for another reason.")
        return cleaned


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    form = ProductReviewAdminForm
    list_display = ["product", "order", "user", "rating", "is_anonymous", "flag_reason", "created_at"]
    list_filter = ["rating", "is_anonymous", "flag_reason", "created_at"]
    search_fields = ["product__name", "body", "flag_note"]
    ordering = ["-created_at"]
    list_select_related = ["product", "order", "user", "flagged_by"]
    raw_id_fields = ["order", "user", "flagged_by"]
    readonly_fields = [
        "product",
        "order",
        "user",
        "rating",
        "body",
        "is_anonymous",
        "flagged_by",
        "flagged_at",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if obj.flag_reason:
            obj.flagged_by = request.user
            obj.flagged_at = timezone.now()
        else:
            obj.flag_note = ""
            obj.flagged_by = None
            obj.flagged_at = None
        super().save_model(request, obj, form, change)
