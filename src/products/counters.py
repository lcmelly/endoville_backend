"""
Stored product and sales totals for brands, categories, and products.

These change when a product is linked or unlinked, and when units are sold,
removed from an open order, or dropped because the order is cancelled or refunded.
"""

from decimal import Decimal

from django.db.models import F, Value
from django.db.models.functions import Greatest

from products.models import Brand, Category, Product, Subcategory


def adjust_counts(*, brand_ids=(), category_ids=(), products_count=0, products_sold=0):
    _apply(Brand, brand_ids, products_count, products_sold)
    _apply(Category, category_ids, products_count, products_sold)


def _apply(model, pks, products_count, products_sold):
    pks = [pk for pk in dict.fromkeys(pks) if pk]
    if not pks:
        return
    updates = {}
    if products_count:
        updates["products_count"] = Greatest(F("products_count") + products_count, Value(0))
    if products_sold:
        updates["products_sold"] = Greatest(F("products_sold") + products_sold, Value(0))
    if updates:
        model.objects.filter(pk__in=pks).update(**updates)


def category_ids_for_product(product_id):
    if not product_id:
        return set()
    return set(
        Subcategory.objects.filter(products__id=product_id).values_list("category_id", flat=True).distinct()
    )


def quantity_sold_for(product_ids):
    ids = [pk for pk in dict.fromkeys(product_ids) if pk]
    if not ids:
        return {}
    return {
        pk: int(qty or 0)
        for pk, qty in Product.objects.filter(pk__in=ids).values_list("pk", "quantity_sold")
    }


def adjust_products_sold(product_id, quantity_delta=0, revenue_delta=0):
    quantity_delta = int(quantity_delta or 0)
    revenue_delta = Decimal(str(revenue_delta or 0)).quantize(Decimal("0.01"))
    if not product_id or (quantity_delta == 0 and revenue_delta == 0):
        return
    if quantity_delta:
        brand_id = Product.objects.filter(pk=product_id).values_list("brand_id", flat=True).first()
        adjust_counts(
            brand_ids=[brand_id] if brand_id else [],
            category_ids=category_ids_for_product(product_id),
            products_sold=quantity_delta,
        )
    updates = {}
    if quantity_delta:
        updates["quantity_sold"] = Greatest(F("quantity_sold") + quantity_delta, Value(0))
    if revenue_delta:
        updates["revenue"] = Greatest(F("revenue") + revenue_delta, Value(Decimal("0.00")))
    if updates:
        Product.objects.filter(pk=product_id).update(**updates)


def move_subcategory_products(subcategory_id, product_ids, old_category_id, new_category_id):
    if old_category_id == new_category_id:
        return
    sold = quantity_sold_for(product_ids)
    for product_id in product_ids:
        units = sold.get(product_id, 0)
        if old_category_id:
            still_old = (
                Subcategory.objects.filter(products__id=product_id, category_id=old_category_id)
                .exclude(pk=subcategory_id)
                .exists()
            )
            if not still_old:
                adjust_counts(category_ids=[old_category_id], products_count=-1, products_sold=-units)
        if new_category_id:
            already_new = (
                Subcategory.objects.filter(products__id=product_id, category_id=new_category_id)
                .exclude(pk=subcategory_id)
                .exists()
            )
            if not already_new:
                adjust_counts(category_ids=[new_category_id], products_count=1, products_sold=units)
