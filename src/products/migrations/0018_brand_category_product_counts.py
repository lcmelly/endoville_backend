from django.db import migrations, models
from django.db.models import Sum


def backfill_catalog_counts(apps, schema_editor):
    Brand = apps.get_model("products", "Brand")
    Category = apps.get_model("products", "Category")
    Product = apps.get_model("products", "Product")
    OrderItem = apps.get_model("orders", "OrderItem")
    closed = ["CANCELLED", "REFUNDED"]

    for brand in Brand.objects.all().iterator():
        sold = (
            OrderItem.objects.filter(product__brand_id=brand.pk)
            .exclude(order__status__in=closed)
            .aggregate(total=Sum("quantity"))["total"]
            or 0
        )
        Brand.objects.filter(pk=brand.pk).update(
            products_count=Product.objects.filter(brand_id=brand.pk).count(),
            products_sold=sold,
        )

    for category in Category.objects.all().iterator():
        product_ids = Product.objects.filter(subcategories__category_id=category.pk).values("pk")
        sold = (
            OrderItem.objects.filter(product_id__in=product_ids)
            .exclude(order__status__in=closed)
            .aggregate(total=Sum("quantity"))["total"]
            or 0
        )
        Category.objects.filter(pk=category.pk).update(
            products_count=Product.objects.filter(subcategories__category_id=category.pk).distinct().count(),
            products_sold=sold,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0017_currency_rate_synced_at"),
        ("orders", "0010_refund_partial_and_line_changes"),
    ]

    operations = [
        migrations.AddField(
            model_name="brand",
            name="products_count",
            field=models.PositiveIntegerField(
                default=0,
                editable=False,
                help_text="Products currently linked to this brand.",
            ),
        ),
        migrations.AddField(
            model_name="brand",
            name="products_sold",
            field=models.PositiveIntegerField(
                default=0,
                editable=False,
                help_text="Units sold on orders that are not cancelled or refunded.",
            ),
        ),
        migrations.AddField(
            model_name="category",
            name="products_count",
            field=models.PositiveIntegerField(
                default=0,
                editable=False,
                help_text="Products currently in this category, counted once even if they sit in several subcategories.",
            ),
        ),
        migrations.AddField(
            model_name="category",
            name="products_sold",
            field=models.PositiveIntegerField(
                default=0,
                editable=False,
                help_text="Units sold on orders that are not cancelled or refunded.",
            ),
        ),
        migrations.RunPython(backfill_catalog_counts, migrations.RunPython.noop),
    ]
