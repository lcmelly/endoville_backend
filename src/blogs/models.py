from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Author(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    title = models.CharField(max_length=200, blank=True)
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True, db_index=True)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='posts')
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