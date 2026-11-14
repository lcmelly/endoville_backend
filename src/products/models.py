import contextvars
from contextlib import contextmanager

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

_track_stock_explicit = contextvars.ContextVar("product_track_stock_explicit", default=False)


@contextmanager
def explicit_track_stock():
    token = _track_stock_explicit.set(True)
    try:
        yield
    finally:
        _track_stock_explicit.reset(token)


def _align_track_stock(instance, update_fields):
    """A stock number turns tracking on. The checkbox, when sent, wins."""
    if getattr(instance, "_stock_movement", False) or _track_stock_explicit.get():
        return update_fields
    if instance._state.adding:
        if instance.stock is not None:
            instance.track_stock = True
        return update_fields
    if update_fields is not None and "stock" not in update_fields:
        return update_fields
    previous = type(instance).objects.filter(pk=instance.pk).values("stock", "track_stock").first()
    if previous is None:
        return update_fields
    if update_fields is None and instance.track_stock != previous["track_stock"]:
        return update_fields
    if instance.stock == previous["stock"]:
        return update_fields
    instance.track_stock = instance.stock is not None
    if update_fields is not None and "track_stock" not in update_fields:
        return [*update_fields, "track_stock"]
    return update_fields


def _audit_price_change(instance, target_type, update_fields):
    fields = ["price", "cost_price"]
    if update_fields is not None:
        fields = [field for field in fields if field in update_fields]
    if not fields or not instance.pk:
        return
    from users.audit import get_audit_user, log_staff_change, money

    if get_audit_user() is None:
        return
    previous = type(instance).objects.filter(pk=instance.pk).values(*fields).first()
    if previous is None:
        return
    changes = {}
    for field in fields:
        old = previous[field]
        new = getattr(instance, field)
        old_money = money(old)
        new_money = money(new)
        if old_money != new_money:
            changes[field] = {"from": old_money, "to": new_money}
    if not changes:
        return
    name = instance.name if target_type == "product" else f"{instance.product.name} variant"
    bits = ", ".join(f"{field} {values['from']} -> {values['to']}" for field, values in changes.items())
    log_staff_change(
        action=f"{target_type}.price_changed",
        target_type=target_type,
        target_id=instance.pk,
        summary=f"{name}: {bits}"[:255],
        changes=changes,
    )


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
    rate_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When usd_rate was last written from a Stripe FX quote.",
    )
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
    products_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Products currently linked to this brand.",
    )
    products_sold = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Units sold on orders that are not cancelled or refunded.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    products_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Products currently in this category, counted once even if they sit in several subcategories.",
    )
    products_sold = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Units sold on orders that are not cancelled or refunded.",
    )

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
    track_stock = models.BooleanField(
        default=False,
        help_text="Checkout reduces stock only when this is on. Setting a stock number turns it on.",
    )
    stock = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Units available to sell. Empty when stock is not tracked.",
    )
    unit_weight = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Weight of one unit, in grams.",
    )
    sku = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    barcode = models.CharField(max_length=64, unique=True, blank=True, null=True, db_index=True)
    image_urls = models.JSONField(default=list, blank=True)
    image_refs = models.JSONField(default=list, blank=True, help_text="Storage keys/paths for images, same order as image_urls")
    supplier_order_urls = models.JSONField(
        default=list,
        blank=True,
        help_text="URLs where staff can order this product from a supplier",
    )
    subcategories = models.ManyToManyField(
        Subcategory, related_name='products', blank=True
    )

    featured = models.BooleanField(default=False, db_index=True)
    is_cancelled = models.BooleanField(default=False, db_index=True)

    benefits = models.TextField(blank=True, help_text="Product benefits (marketing copy)")
    ingredients = models.TextField(blank=True, help_text="Ingredients or composition")
    how_to_use = models.TextField(blank=True, help_text="Usage instructions")

    # SEO fields
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    slug = models.SlugField(unique=True, db_index=True)

    # Denormalized from reviews for fast reads (updated on every review add/update/delete)
    avg_rating = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True, db_index=True
    )
    review_count = models.PositiveIntegerField(default=0, db_index=True)
    quantity_sold = models.PositiveIntegerField(
        default=0,
        editable=False,
        help_text="Units sold on orders that are not cancelled or refunded.",
    )
    revenue = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        editable=False,
        help_text="Sum of those order line totals, in the primary currency.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        update_fields = _align_track_stock(self, kwargs.get("update_fields"))
        if "update_fields" in kwargs:
            if update_fields is None:
                kwargs.pop("update_fields")
            else:
                kwargs["update_fields"] = update_fields
        _audit_price_change(self, "product", kwargs.get("update_fields"))
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
    Variants carry their own price and stock. SKU and barcode are optional; when set, barcode must be unique.
    Price falls back to the product when empty. Stock never does.
    """

    product = models.ForeignKey(Product, related_name="variants", on_delete=models.CASCADE)
    options = models.ManyToManyField(VariationOption, related_name="variants", blank=True)

    sku = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    barcode = models.CharField(max_length=64, unique=True, blank=True, null=True, db_index=True)

    # Price falls back to the product when empty. Stock is this variant's own shelf.
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    track_stock = models.BooleanField(
        default=False,
        help_text="Checkout reduces this variant's stock only when this is on. It never changes the product.",
    )
    stock = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Units available on this variant. Empty when this variant's stock is not tracked.",
    )
    image_urls = models.JSONField(default=list, blank=True)
    image_refs = models.JSONField(default=list, blank=True, help_text="Storage keys/paths for images, same order as image_urls")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["product", "sku"]),
        ]

    def save(self, *args, **kwargs):
        update_fields = _align_track_stock(self, kwargs.get("update_fields"))
        if "update_fields" in kwargs:
            if update_fields is None:
                kwargs.pop("update_fields")
            else:
                kwargs["update_fields"] = update_fields
        _audit_price_change(self, "variant", kwargs.get("update_fields"))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} ({self.barcode or '—'})"


class ReviewFlagReason(models.TextChoices):
    PROFANITY = "PROFANITY", "Profanity"
    MALICIOUS = "MALICIOUS", "Malicious"
    OTHER = "OTHER", "Another issue"


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
        on_delete=models.PROTECT,
        help_text="Completed order that contained this product. Required.",
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
    flag_reason = models.CharField(
        max_length=20,
        choices=ReviewFlagReason.choices,
        blank=True,
        default="",
        db_index=True,
        help_text="Staff flag. A flagged review is hidden and excluded from the product rating.",
    )
    flag_note = models.TextField(
        blank=True,
        help_text="Required when the flag reason is another issue.",
    )
    flagged_at = models.DateTimeField(null=True, blank=True)
    flagged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="flagged_product_reviews",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_hidden(self):
        return bool(self.flag_reason)

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
