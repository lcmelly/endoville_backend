"""
Permission classes for orders app.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsStaffOrOwner(BasePermission):
    """
    Staff can access all orders/shipments; users can access only their own.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True

        # Order-like objects
        if hasattr(obj, "user_id"):
            return obj.user_id == request.user.id

        # Shipment-like objects
        if hasattr(obj, "order_id") and hasattr(obj, "order"):
            return obj.order.user_id == request.user.id

        return False


class IsStaffOnly(BasePermission):
    """
    Staff-only access.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)

    def has_object_permission(self, request, view, obj):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
