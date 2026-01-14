"""
URL configuration for blogs app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AuthorViewSet, CommentViewSet, PostViewSet

app_name = "blogs"

router = DefaultRouter()
router.register(r"authors", AuthorViewSet, basename="author")
router.register(r"posts", PostViewSet, basename="post")
router.register(r"comments", CommentViewSet, basename="comment")

urlpatterns = [
    path("", include(router.urls)),
]
