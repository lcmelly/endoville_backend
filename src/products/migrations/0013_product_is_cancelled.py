from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0012_product_featured_and_content_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="is_cancelled",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
