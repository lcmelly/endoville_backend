from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0013_product_is_cancelled"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="supplier_order_urls",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="URLs where staff can order this product from a supplier",
            ),
        ),
    ]
