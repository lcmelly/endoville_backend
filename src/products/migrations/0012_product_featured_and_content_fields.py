# Product featured flag and content fields (benefits, ingredients, how_to_use)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0011_brand_and_product_brand"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="featured",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="product",
            name="benefits",
            field=models.TextField(blank=True, help_text="Product benefits (marketing copy)"),
        ),
        migrations.AddField(
            model_name="product",
            name="ingredients",
            field=models.TextField(blank=True, help_text="Ingredients or composition"),
        ),
        migrations.AddField(
            model_name="product",
            name="how_to_use",
            field=models.TextField(blank=True, help_text="Usage instructions"),
        ),
    ]
