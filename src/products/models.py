from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Subcategory(models.Model):
    name = models.CharField(max_length=100, db_index=True)
    category = models.ForeignKey(
        Category, related_name='subcategories', on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ('name', 'category')

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()
    image_urls = models.JSONField(default=list, blank=True)
    subcategories = models.ManyToManyField(
        Subcategory, related_name='products', blank=True
    )

    # SEO fields
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    slug = models.SlugField(unique=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class VariationAttribute(models.Model):
    """
    A dimension of variation, e.g. Color, Size.
    """

    name = models.CharField(max_length=100, unique=True, db_index=True)

    def __str__(self):
        return self.name


class VariationOption(models.Model):
    """
    A concrete value for an attribute, e.g. Color=Red, Size=XL.
    """

    attribute = models.ForeignKey(
        VariationAttribute, related_name="options", on_delete=models.CASCADE
    )
    value = models.CharField(max_length=100, db_index=True)

    class Meta:
        unique_together = ("attribute", "value")

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class ProductVariant(models.Model):
    """
    A purchasable variant of a product, e.g. 'T-Shirt / Red / XL'.
    Variants carry their own stock/price and a unique barcode.
    """

    product = models.ForeignKey(Product, related_name="variants", on_delete=models.CASCADE)
    options = models.ManyToManyField(VariationOption, related_name="variants", blank=True)

    sku = models.CharField(max_length=64, blank=True, db_index=True)
    barcode = models.CharField(max_length=64, unique=True, db_index=True)

    # Optional overrides. If null, clients can fall back to product.price / product.stock.
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(null=True, blank=True)
    image_urls = models.JSONField(default=list, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["product", "sku"]),
        ]

    def __str__(self):
        return f"{self.product.name} ({self.barcode})"
