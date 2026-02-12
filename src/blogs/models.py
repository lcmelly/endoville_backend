from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Subcategory(models.Model):
    name = models.CharField(max_length=100, db_index=True)
    category = models.ForeignKey(Category, related_name="subcategories", on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("name", "category")

    def __str__(self):
        return f"{self.category.name} / {self.name}"


class Author(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    title = models.CharField(max_length=200, blank=True)
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True)
    image_url = models.URLField(max_length=255, blank=True)
    image_ref = models.CharField(max_length=255, blank=True)
    image_alt = models.CharField(max_length=255, blank=True)
    image_title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True, db_index=True)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='posts')
    subcategories = models.ManyToManyField(Subcategory, related_name="posts", blank=True)
    content = models.TextField()
    excerpt = models.CharField(max_length=160, help_text="SEO Meta Description")
    featured_image_ref = models.CharField(max_length=255, blank=True)
    featured_image_alt = models.CharField(max_length=255, blank=True)
    featured_image_title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # SEO Specific Fields
    meta_keywords = models.CharField(max_length=255, blank=True)
    is_published = models.BooleanField(default=False)
    views = models.PositiveIntegerField(default=0, db_index=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.content