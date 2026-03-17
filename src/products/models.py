from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Currency(models.Model):
    """
    Currency table with conversion rate relative to USD (base currency).

    `usd_rate` means: 1 USD = usd_rate * <currency>.
    Example: if 1 USD = 160.50 KES, then KES.usd_rate = 160.50.
    """

    code = models.CharField(max_length=10, unique=True, db_index=True)  # e.g. USD, KES
    name = models.CharField(max_length=100, blank=True)  # e.g. US Dollar, Kenyan Shilling
    symbol = models.CharField(max_length=10, blank=True)  # e.g. $, KSh

    usd_rate = models.DecimalField(max_digits=18, decimal_places=6, default=1)
    is_primary = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "currencies"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Ensure only one primary currency exists (typically USD).
        if self.is_primary:
            Currency.objects.filter(is_primary=True).exclude(pk=self.pk).update(is_primary=False)

    def __str__(self):
        return self.code


class Brand(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True)
    image_urls = models.JSONField(default=list, blank=True)
    image_refs = models.JSONField(
        default=list,
        blank=True,
        help_text="Storage keys/paths for brand images, same order as image_urls",
    )
    image_labels = models.JSONField(
        default=list,
        blank=True,
        help_text="Labels for brand images, same order as image_urls, e.g. logo, banner",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


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
    brand = models.ForeignKey(
        Brand, related_name="products", on_delete=models.SET_NULL, null=True, blank=True
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField()
    sku = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    barcode = models.CharField(max_length=64, unique=True, blank=True, null=True, db_index=True)
    image_urls = models.JSONField(default=list, blank=True)
    image_refs = models.JSONField(default=list, blank=True, help_text="Storage keys/paths for images, same order as image_urls")
    subcategories = models.ManyToManyField(
        Subcategory, related_name='products', blank=True
    )

    # SEO fields
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    slug = models.SlugField(unique=True, db_index=True)

    # Denormalized from reviews for fast reads (updated on every review add/update/delete)
    avg_rating = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True, db_index=True
    )
    review_count = models.PositiveIntegerField(default=0, db_index=True)

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
    Variants carry their own stock/price. SKU and barcode are optional; when set, barcode must be unique.
    """

    product = models.ForeignKey(Product, related_name="variants", on_delete=models.CASCADE)
    options = models.ManyToManyField(VariationOption, related_name="variants", blank=True)

    sku = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    barcode = models.CharField(max_length=64, unique=True, blank=True, null=True, db_index=True)

    # Optional overrides. If null, clients can fall back to product.price / product.stock.
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(null=True, blank=True)
    image_urls = models.JSONField(default=list, blank=True)
    image_refs = models.JSONField(default=list, blank=True, help_text="Storage keys/paths for images, same order as image_urls")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["product", "sku"]),
        ]

    def __str__(self):
        return f"{self.product.name} ({self.barcode or '—'})"


class ProductReview(models.Model):
    """
    Review for a product (rating 0-5 + optional text), linked to a completed order.
    Shared across all variants of the product. One review per user per product.
    Only users who purchased the product (via a completed order) can submit a review.
    """

    product = models.ForeignKey(
        Product, related_name="reviews", on_delete=models.CASCADE
    )
    order = models.ForeignKey(
        "orders.Order",
        related_name="product_reviews",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Completed order that contained this product (verified on create).",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="product_reviews",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    rating = models.PositiveSmallIntegerField()  # 0-5
    body = models.TextField(blank=True)
    is_anonymous = models.BooleanField(
        default=False,
        help_text="If true, user_display is redacted as 'Anonymous'.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "user"],
                condition=models.Q(user__isnull=False),
                name="products_productreview_unique_product_user",
            )
        ]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "-created_at"]),
        ]

    def __str__(self):
        return f"Review {self.rating} for {self.product.name}"
