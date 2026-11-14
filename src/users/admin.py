from django.contrib import admin
from .models import CustomUser, OTP, StaffChangeLog
from import_export.admin import ImportExportModelAdmin

@admin.register(CustomUser)
class CustomUserAdmin(ImportExportModelAdmin):
    list_display = ['email', 'phone', 'first_name', 'last_name', 'image_url', 'image_ref', 'is_active', 'is_staff', 'created_at']
    list_filter = ['is_active', 'is_staff', 'created_at']
    search_fields = ['email', 'phone', 'first_name', 'last_name', 'image_ref']
    ordering = ['-created_at']

@admin.register(StaffChangeLog)
class StaffChangeLogAdmin(ImportExportModelAdmin):
    list_display = ["created_at", "actor", "action", "target_type", "target_id", "order_id", "summary"]
    list_filter = ["action", "target_type", "created_at"]
    search_fields = ["summary", "target_id", "actor__email", "order_id"]
    ordering = ["-created_at"]
    readonly_fields = [
        "actor",
        "action",
        "target_type",
        "target_id",
        "order_id",
        "summary",
        "changes",
        "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OTP)
class OTPAdmin(ImportExportModelAdmin):
    list_display = ['email', 'phone', 'otp', 'is_used', 'created_at', 'expires_at']
    list_filter = ['is_used', 'created_at', 'expires_at']
    search_fields = ['email', 'phone', 'otp']
    ordering = ['-created_at']

