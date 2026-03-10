"""
Permission classes for products app.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


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


class ProductReviewPermission(BasePermission):
    """
    Anyone can read. Authenticated users can create (if they have a completed
    order containing the product; enforced in serializer). Only the review
    owner or staff can update/delete.
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
        return bool(
            request.user
            and request.user.is_authenticated
            and (obj.user_id == request.user.pk or request.user.is_staff)
        )
