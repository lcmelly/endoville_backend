from rest_framework import serializers

from .models import Author, Comment, Post


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = [
            "id",
            "name",
            "title",
            "email",
            "bio",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class PostSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.name", read_only=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "slug",
            "author",
            "author_name",
            "content",
            "excerpt",
            "featured_image_ref",
            "featured_image_alt",
            "featured_image_title",
            "meta_keywords",
            "is_published",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.PrimaryKeyRelatedField(read_only=True)
    author_display = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "post",
            "author",
            "author_display",
            "content",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "author", "created_at", "updated_at"]

    def get_author_display(self, obj):
        user = obj.author
        # Prefer full name, else fall back to identifier (email or phone)
        full_name = user.get_full_name()
        return full_name if full_name else getattr(user, "identifier", None) or user.email or user.phone
