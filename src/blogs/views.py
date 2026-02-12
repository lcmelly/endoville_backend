"""
API views for blogs app (authors, posts, comments).
"""

from rest_framework import viewsets
from rest_framework.response import Response
from django.db.models import F

from .models import Author, Category, Comment, Post, Subcategory
from .permissions import AuthorPermission, CommentPermission, PostPermission
from .serializers import (
    AuthorDetailSerializer,
    AuthorSerializer,
    CategorySerializer,
    CategoryWithSubcategoriesSerializer,
    CommentSerializer,
    PostSerializer,
    SubcategorySerializer,
)


class AuthorViewSet(viewsets.ModelViewSet):
    """
    Anyone can read authors; only staff can create, update, delete.
    """

    queryset = Author.objects.all().order_by("-created_at")
    permission_classes = [AuthorPermission]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AuthorDetailSerializer
        return AuthorSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.prefetch_related("subcategories").order_by("name")
    permission_classes = [PostPermission]  # staff write, public read

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return CategoryWithSubcategoriesSerializer
        return CategorySerializer


class SubcategoryViewSet(viewsets.ModelViewSet):
    queryset = Subcategory.objects.select_related("category").order_by("category__name", "name")
    serializer_class = SubcategorySerializer
    permission_classes = [PostPermission]  # staff write, public read


class PostViewSet(viewsets.ModelViewSet):
    """
    Anyone can read posts; only staff can create, update, delete.
    """

    queryset = Post.objects.select_related("author").prefetch_related("subcategories", "subcategories__category").order_by("-created_at")
    serializer_class = PostSerializer
    permission_classes = [PostPermission]

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        # Track views (count requests) for non-staff users only
        user = request.user
        if user:
            if user.is_staff:
                return Response(self.get_serializer(instance).data)
            else:
                Post.objects.filter(pk=instance.pk).update(views=F("views") + 1)
                instance.views += 1
                return Response(self.get_serializer(instance).data)
        
        Post.objects.filter(pk=instance.pk).update(views=F("views") + 1)
        instance.views += 1
        return Response(self.get_serializer(instance).data)

class CommentViewSet(viewsets.ModelViewSet):
    """
    Anyone can read comments.
    Authenticated users can create; staff or owner can delete; only staff can edit.
    """

    queryset = Comment.objects.select_related("post", "author").order_by("-created_at")
    serializer_class = CommentSerializer
    permission_classes = [CommentPermission]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
