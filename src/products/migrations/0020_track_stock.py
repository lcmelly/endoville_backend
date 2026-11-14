from django.db import migrations, models


def track_rows_that_already_have_stock(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductVariant = apps.get_model("products", "ProductVariant")
    Product.objects.filter(stock__isnull=False).update(track_stock=True)
    ProductVariant.objects.filter(stock__isnull=False).update(track_stock=True)


def stop_tracking(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductVariant = apps.get_model("products", "ProductVariant")
    Product.objects.update(track_stock=False)
    ProductVariant.objects.update(track_stock=False)


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0019_product_quantity_sold_and_revenue"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="track_stock",
            field=models.BooleanField(
                default=False,
                help_text="Checkout reduces stock only when this is on. Setting a stock number turns it on.",
            ),
        ),
        migrations.AddField(
            model_name="productvariant",
            name="track_stock",
            field=models.BooleanField(
                default=False,
                help_text="Checkout reduces this variant's stock only when this is on. It never changes the product.",
            ),
        ),
        migrations.AlterField(
            model_name="product",
            name="stock",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Units available to sell. Empty when stock is not tracked.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="productvariant",
            name="stock",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Units available on this variant. Empty when this variant's stock is not tracked.",
                null=True,
            ),
        ),
        migrations.RunPython(track_rows_that_already_have_stock, stop_tracking),
    ]
