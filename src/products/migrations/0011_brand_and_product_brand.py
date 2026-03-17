# Brand model and Product.brand

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0010_product_sku_barcode"),
    ]

    operations = [
        migrations.CreateModel(
            name="Brand",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(db_index=True, max_length=200)),
                ("description", models.TextField(blank=True)),
                ("image_urls", models.JSONField(blank=True, default=list)),
                ("image_refs", models.JSONField(blank=True, default=list, help_text="Storage keys/paths for brand images, same order as image_urls")),
                ("image_labels", models.JSONField(blank=True, default=list, help_text="Labels for brand images, same order as image_urls, e.g. logo, banner")),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="product",
            name="brand",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="products",
                to="products.brand",
            ),
        ),
    ]
