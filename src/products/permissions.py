"""
Permission classes for products app.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS

from users.roles import has_staff_role


class AdminWritePublicRead(BasePermission):
    """
    No auth required for reads. Only a superuser can create, update, or delete.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class StaffWriteReadOnly(BasePermission):
    """
    No auth required for reads (GET, HEAD, OPTIONS). Only staff can create/update/delete.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True  # allow unauthenticated for list/retrieve
        return bool(request.user and request.user.is_staff)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class StockWritePublicRead(StaffWriteReadOnly):
    """
    Public read. Creating or editing a product or variant requires the Stock role or an admin.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return has_staff_role(request.user, "Stock")

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class ProductReviewPermission(BasePermission):
    """
    Anyone can read visible reviews. Authenticated purchasers can create a review
    for a completed order (enforced in the serializer). The author can update or
    delete their own review. Staff cannot delete reviews; they flag them instead.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        if request.method == "POST":
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if getattr(view, "action", None) in ("flag", "unflag"):
            return bool(request.user and request.user.is_authenticated and request.user.is_staff)
        if request.method == "DELETE" and request.user.is_staff:
            # The view rejects the delete and tells staff to flag the review.
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and obj.user_id == request.user.pk
        )
