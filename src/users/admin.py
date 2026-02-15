from django.contrib import admin
from .models import *
from import_export.admin import ImportExportModelAdmin

@admin.register(CustomUser)
class CustomUserAdmin(ImportExportModelAdmin):
    list_display = ['email', 'phone', 'first_name', 'last_name', 'image_url', 'image_ref', 'is_active', 'is_staff', 'created_at']
    list_filter = ['is_active', 'is_staff', 'created_at']
    search_fields = ['email', 'phone', 'first_name', 'last_name', 'image_ref']
    ordering = ['-created_at']

@admin.register(OTP)
class OTPAdmin(ImportExportModelAdmin):
    list_display = ['email', 'phone', 'otp', 'is_used', 'created_at', 'expires_at']
    list_filter = ['is_used', 'created_at', 'expires_at']
    search_fields = ['email', 'phone', 'otp']
    ordering = ['-created_at']

