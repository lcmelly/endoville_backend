from django.db import migrations, models
from django.db.models import Sum


def backfill_product_sales(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    OrderItem = apps.get_model("orders", "OrderItem")
    rows = (
        OrderItem.objects.exclude(product_id=None)
        .exclude(order__status__in=["CANCELLED", "REFUNDED"])
        .values("product_id")
        .annotate(qty=Sum("quantity"), revenue=Sum("line_total"))
    )
    for row in rows:
        Product.objects.filter(pk=row["product_id"]).update(
            quantity_sold=row["qty"] or 0,
            revenue=row["revenue"] or 0,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0018_brand_category_product_counts"),
        ("orders", "0010_refund_partial_and_line_changes"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="quantity_sold",
            field=models.PositiveIntegerField(
                default=0,
                editable=False,
                help_text="Units sold on orders that are not cancelled or refunded.",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="revenue",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                editable=False,
                help_text="Sum of those order line totals, in the primary currency.",
                max_digits=14,
            ),
        ),
        migrations.RunPython(backfill_product_sales, migrations.RunPython.noop),
    ]
