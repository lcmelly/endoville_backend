"""
API views for blogs app (authors, posts, comments).
"""

from rest_framework import viewsets

from .models import Author, Comment, Post
from .permissions import AuthorPermission, CommentPermission, PostPermission
from .serializers import AuthorSerializer, CommentSerializer, PostSerializer


class AuthorViewSet(viewsets.ModelViewSet):
    """
    Anyone can read authors; only staff can create, update, delete.
    """

    queryset = Author.objects.all().order_by("-created_at")
    serializer_class = AuthorSerializer
    permission_classes = [AuthorPermission]


class PostViewSet(viewsets.ModelViewSet):
    """
    Anyone can read posts; only staff can create, update, delete.
    """

    queryset = Post.objects.select_related("author").order_by("-created_at")
    serializer_class = PostSerializer
    permission_classes = [PostPermission]


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
