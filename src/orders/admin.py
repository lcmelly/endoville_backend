from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from .models import (
    Order,
    OrderItem,
    OrderPayment,
    PaymentCredentials,
    Shipment,
    ShipmentEvent,
    ShippingAddress,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["line_total"]


class ShipmentEventInline(admin.TabularInline):
    model = ShipmentEvent
    extra = 0


@admin.register(ShippingAddress)
class ShippingAddressAdmin(ImportExportModelAdmin):
    list_display = ["full_name", "city", "state", "country", "created_at"]
    search_fields = ["full_name", "phone", "email", "city", "state", "postal_code"]
    ordering = ["-created_at"]


@admin.register(Order)
class OrderAdmin(ImportExportModelAdmin):
    list_display = ["id", "user", "status", "total", "created_at", "updated_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["id", "user__email", "user__phone"]
    ordering = ["-created_at"]
    inlines = [OrderItemInline]
    raw_id_fields = ["user", "shipping_address"]
    list_select_related = ["user", "shipping_address"]


@admin.register(Shipment)
class ShipmentAdmin(ImportExportModelAdmin):
    list_display = ["order", "status", "carrier", "tracking_number", "updated_at"]
    list_filter = ["status", "carrier", "updated_at"]
    search_fields = ["order__id", "tracking_number", "carrier"]
    ordering = ["-created_at"]
    inlines = [ShipmentEventInline]
    raw_id_fields = ["order"]
    list_select_related = ["order"]


@admin.register(OrderItem)
class OrderItemAdmin(ImportExportModelAdmin):
    list_display = ["order", "product_name", "quantity", "unit_price", "line_total"]
    search_fields = ["order__id", "product_name", "barcode"]
    ordering = ["-id"]
    raw_id_fields = ["order", "product", "variant"]
    list_select_related = ["order", "product", "variant"]


@admin.register(ShipmentEvent)
class ShipmentEventAdmin(ImportExportModelAdmin):
    list_display = ["shipment", "status", "occurred_at", "location"]
    list_filter = ["status", "occurred_at"]
    search_fields = ["shipment__order__id", "message", "location"]
    ordering = ["-occurred_at"]
    raw_id_fields = ["shipment"]


@admin.register(PaymentCredentials)
class PaymentCredentialsAdmin(ImportExportModelAdmin):
    list_display = ["provider", "environment", "is_active", "created_at"]
    list_filter = ["provider", "environment", "is_active", "created_at"]
    search_fields = ["api_key"]
    ordering = ["-created_at"]


@admin.register(OrderPayment)
class OrderPaymentAdmin(ImportExportModelAdmin):
    list_display = ["order", "provider", "status", "amount", "currency", "updated_at"]
    list_filter = ["provider", "status", "created_at", "updated_at"]
    search_fields = ["order__id", "provider_payment_id", "provider_invoice_id"]
    ordering = ["-created_at"]
    raw_id_fields = ["order"]
    list_select_related = ["order"]
