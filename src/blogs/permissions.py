"""
Permission classes for blogs app.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


class AuthorPermission(BasePermission):
    """
    Allow anyone to read authors.
    Only staff can create/update/delete.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class PostPermission(BasePermission):
    """
    Allow anyone to read posts.
    Only staff can create/update/delete.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class CommentPermission(BasePermission):
    """
    Allow anyone to read comments.
    Authenticated users can create.
    Only staff can edit; staff or owner can delete.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        if view.action == "create":
            return request.user and request.user.is_authenticated

        # update/partial_update/destroy require auth (object check handles role)
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        if request.user and request.user.is_staff:
            return True

        if view.action in ["update", "partial_update"]:
            return False

        if view.action == "destroy":
            return obj.author_id == request.user.id

        return False
