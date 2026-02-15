from rest_framework import serializers

from products.models import Product

from .models import Author, Category, Comment, Post, Subcategory


class RelatedProductSerializer(serializers.ModelSerializer):
    """Lightweight product representation for related products in blog posts."""

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "price", "image_urls"]
        read_only_fields = fields


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = [
            "id",
            "name",
            "title",
            "email",
            "bio",
            "image_url",
            "image_ref",
            "image_alt",
            "image_title",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class SubcategorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Subcategory
        fields = ["id", "name", "category", "category_name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class CategoryWithSubcategoriesSerializer(CategorySerializer):
    """Category with nested subcategories."""

    subcategories = SubcategorySerializer(many=True, read_only=True)

    class Meta(CategorySerializer.Meta):
        fields = CategorySerializer.Meta.fields + ["subcategories"]


class PostListItemSerializer(serializers.ModelSerializer):
    """
    Lightweight post serializer for nesting under Author.
    """

    class Meta:
        model = Post
        fields = ["id", "title", "slug", "featured_image_url", "is_published", "views", "created_at", "updated_at"]
        read_only_fields = fields


class AuthorDetailSerializer(AuthorSerializer):
    posts = serializers.SerializerMethodField()

    def get_posts(self, obj):
        request = self.context.get("request")
        qs = obj.posts.all().order_by("-created_at")
        if not request or not getattr(request, "user", None) or not request.user.is_staff:
            qs = qs.filter(is_published=True)
        return PostListItemSerializer(qs, many=True).data

    class Meta(AuthorSerializer.Meta):
        fields = AuthorSerializer.Meta.fields + ["posts"]


class PostSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.name", read_only=True)
    views = serializers.IntegerField(read_only=True)
    subcategories = serializers.PrimaryKeyRelatedField(
        queryset=Subcategory.objects.all(), many=True, required=False
    )
    subcategories_details = SubcategorySerializer(source="subcategories", many=True, read_only=True)
    related_products = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), many=True, required=False
    )
    related_products_details = RelatedProductSerializer(
        source="related_products", many=True, read_only=True
    )

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "slug",
            "author",
            "author_name",
            "subcategories",
            "subcategories_details",
            "related_products",
            "related_products_details",
            "content",
            "excerpt",
            "featured_image_url",
            "featured_image_ref",
            "featured_image_alt",
            "featured_image_title",
            "meta_keywords",
            "is_published",
            "views",
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
