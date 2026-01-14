from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from .models import Author, Comment, Post


@admin.register(Author)
class AuthorAdmin(ImportExportModelAdmin):
    list_display = ["name", "title", "email", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["name", "title", "email"]
    ordering = ["-created_at"]


@admin.register(Post)
class PostAdmin(ImportExportModelAdmin):
    list_display = [
        "title",
        "slug",
        "author",
        "is_published",
        "created_at",
        "updated_at",
    ]
    list_filter = ["is_published", "created_at", "updated_at"]
    search_fields = ["title", "slug", "author__name", "author__email", "content", "excerpt"]
    ordering = ["-created_at"]
    prepopulated_fields = {"slug": ("title",)}
    raw_id_fields = ["author"]
    list_select_related = ["author"]


@admin.register(Comment)
class CommentAdmin(ImportExportModelAdmin):
    list_display = ["post", "author", "content", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["content", "post__title", "author__email", "author__phone", "author__first_name", "author__last_name"]
    ordering = ["-created_at"]
    raw_id_fields = ["post", "author"]
    list_select_related = ["post", "author"]
