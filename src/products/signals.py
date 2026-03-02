"""
Signals to keep Product.avg_rating and Product.review_count in sync with ProductReview.
"""

from decimal import Decimal

from django.db.models import Avg, Count
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Product, ProductReview


def _update_product_rating(product_id):
    """Recalculate and update Product.avg_rating and review_count from its reviews."""
    agg = ProductReview.objects.filter(product_id=product_id).aggregate(
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
