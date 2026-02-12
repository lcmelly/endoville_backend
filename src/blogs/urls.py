"""
URL configuration for blogs app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AuthorViewSet, CategoryViewSet, CommentViewSet, PostViewSet, SubcategoryViewSet

app_name = "blogs"

router = DefaultRouter()
router.register(r"authors", AuthorViewSet, basename="author")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"subcategories", SubcategoryViewSet, basename="subcategory")
router.register(r"posts", PostViewSet, basename="post")
router.register(r"comments", CommentViewSet, basename="comment")

urlpatterns = [
    path("", include(router.urls)),
]
