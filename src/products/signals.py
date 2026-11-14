"""
Signals to keep Product.avg_rating and Product.review_count in sync with ProductReview.
"""

from decimal import Decimal

from django.db.models import Avg, Count
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from products.counters import (
    adjust_counts,
    category_ids_for_product,
    move_subcategory_products,
    quantity_sold_for,
)

from .models import Product, ProductReview, Subcategory


def _update_product_rating(product_id):
    """Recalculate and update Product.avg_rating and review_count from its reviews."""
    agg = ProductReview.objects.filter(product_id=product_id, flag_reason="").aggregate(
        avg=Avg("rating"),
        count=Count("id"),
    )
    count = agg["count"] or 0
    avg = agg["avg"]
    Product.objects.filter(pk=product_id).update(
        avg_rating=round(Decimal(str(avg)), 2) if avg is not None else None,
        review_count=count,
    )


@receiver(post_save, sender=ProductReview)
def product_review_saved(sender, instance, **kwargs):
    _update_product_rating(instance.product_id)


@receiver(post_delete, sender=ProductReview)
def product_review_deleted(sender, instance, **kwargs):
    _update_product_rating(instance.product_id)


@receiver(pre_save, sender=Product)
def remember_product_brand(sender, instance, update_fields=None, **kwargs):
    if update_fields is not None and "brand" not in update_fields and "brand_id" not in update_fields:
        instance._skip_brand_count = True
        return
    instance._skip_brand_count = False
    if not instance.pk:
        instance._previous_brand_id = None
        return
    instance._previous_brand_id = (
        Product.objects.filter(pk=instance.pk).values_list("brand_id", flat=True).first()
    )


@receiver(post_save, sender=Product)
def sync_brand_product_count(sender, instance, created, **kwargs):
    if getattr(instance, "_skip_brand_count", False):
        return
    previous = getattr(instance, "_previous_brand_id", None)
    current = instance.brand_id
    if created:
        if current:
            adjust_counts(brand_ids=[current], products_count=1)
        return
    if previous == current:
        return
    sold = quantity_sold_for([instance.pk]).get(instance.pk, 0)
    if previous:
        adjust_counts(brand_ids=[previous], products_count=-1, products_sold=-sold)
    if current:
        adjust_counts(brand_ids=[current], products_count=1, products_sold=sold)


@receiver(pre_delete, sender=Product)
def release_product_counts(sender, instance, **kwargs):
    sold = quantity_sold_for([instance.pk]).get(instance.pk, 0)
    if instance.brand_id:
        adjust_counts(brand_ids=[instance.brand_id], products_count=-1, products_sold=-sold)
    adjust_counts(
        category_ids=category_ids_for_product(instance.pk),
        products_count=-1,
        products_sold=-sold,
    )


@receiver(m2m_changed, sender=Product.subcategories.through)
def sync_category_product_count(sender, instance, action, reverse, pk_set, **kwargs):
    if action not in {"pre_add", "pre_remove", "pre_clear"}:
        return
    if not reverse:
        _sync_product_categories(instance, action, pk_set)
        return
    _sync_subcategory_products(instance, action, pk_set)


def _sync_product_categories(product, action, pk_set):
    before = category_ids_for_product(product.pk)
    sold = quantity_sold_for([product.pk]).get(product.pk, 0)
    if action == "pre_clear":
        adjust_counts(category_ids=before, products_count=-1, products_sold=-sold)
        return
    subcategory_ids = pk_set or set()
    if action == "pre_add":
        adding = set(
            Subcategory.objects.filter(pk__in=subcategory_ids).values_list("category_id", flat=True)
        )
        adjust_counts(category_ids=adding - before, products_count=1, products_sold=sold)
        return
    remaining = set(
        Subcategory.objects.filter(products__id=product.pk)
        .exclude(pk__in=subcategory_ids)
        .values_list("category_id", flat=True)
    )
    adjust_counts(category_ids=before - remaining, products_count=-1, products_sold=-sold)


def _sync_subcategory_products(subcategory, action, pk_set):
    if action == "pre_clear":
        product_ids = list(subcategory.products.values_list("pk", flat=True))
    else:
        product_ids = list(pk_set or [])
    sold = quantity_sold_for(product_ids)
    for product_id in product_ids:
        units = sold.get(product_id, 0)
        before = category_ids_for_product(product_id)
        if action == "pre_add":
            if subcategory.category_id not in before:
                adjust_counts(
                    category_ids=[subcategory.category_id],
                    products_count=1,
                    products_sold=units,
                )
            continue
        remaining = set(
            Subcategory.objects.filter(products__id=product_id)
            .exclude(pk=subcategory.pk)
            .values_list("category_id", flat=True)
        )
        if subcategory.category_id in before and subcategory.category_id not in remaining:
            adjust_counts(
                category_ids=[subcategory.category_id],
                products_count=-1,
                products_sold=-units,
            )


@receiver(pre_save, sender=Subcategory)
def remember_subcategory_category(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_category_id = None
        return
    instance._previous_category_id = (
        Subcategory.objects.filter(pk=instance.pk).values_list("category_id", flat=True).first()
    )


@receiver(post_save, sender=Subcategory)
def sync_subcategory_category_move(sender, instance, created, **kwargs):
    if created:
        return
    previous = getattr(instance, "_previous_category_id", None)
    if previous == instance.category_id:
        return
    product_ids = list(instance.products.values_list("pk", flat=True))
    move_subcategory_products(instance.pk, product_ids, previous, instance.category_id)


@receiver(pre_delete, sender=Subcategory)
def release_subcategory_products(sender, instance, **kwargs):
    product_ids = list(instance.products.values_list("pk", flat=True))
    move_subcategory_products(instance.pk, product_ids, instance.category_id, None)
