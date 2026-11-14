"""
Permission classes for orders app.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS

from users.roles import has_staff_role


class IsStaffOrOwner(BasePermission):
    """
    Staff can access all orders/shipments; users can access only their own.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if has_staff_role(request.user, "Orders"):
            return True
        kind = obj.__class__.__name__
        if kind in {"Order", "Shipment", "ShipmentEvent"} and has_staff_role(request.user, "Shipping"):
            return True

        if hasattr(obj, "user_id"):
            return obj.user_id == request.user.id

        if hasattr(obj, "order_id") and hasattr(obj, "order"):
            return obj.order.user_id == request.user.id

        return False


MANAGER_GROUP_NAME = "Manager"


class IsManagerOrAdmin(BasePermission):
    """
    Warehouse edits: Django admins (superuser) and members of the Manager group.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        return has_staff_role(user, MANAGER_GROUP_NAME)

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


def StaffRolePermission(*roles):
    """Staff route allowed for an admin or a ticked role."""

    class _Permission(BasePermission):
        def has_permission(self, request, view):
            return has_staff_role(request.user, *roles)

        def has_object_permission(self, request, view, obj):
            return self.has_permission(request, view)

    _Permission.__name__ = "StaffRolePermission"
    return _Permission


class IsAdmin(BasePermission):
    """Django admin. Staff roles do not grant this."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_superuser)

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsStaffOnly(BasePermission):
    """
    Staff-only access.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)

    def has_object_permission(self, request, view, obj):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
