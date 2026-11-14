import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_cart_cartitem"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("products", "0014_product_supplier_order_urls"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productreview",
            name="order",
            field=models.ForeignKey(
                help_text="Completed order that contained this product. Required.",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="product_reviews",
                to="orders.order",
            ),
        ),
        migrations.AddField(
            model_name="productreview",
            name="flag_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PROFANITY", "Profanity"),
                    ("MALICIOUS", "Malicious"),
                    ("OTHER", "Another issue"),
                ],
                db_index=True,
                default="",
                help_text="Staff flag. A flagged review is hidden and excluded from the product rating.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="productreview",
            name="flag_note",
            field=models.TextField(
                blank=True,
                help_text="Required when the flag reason is another issue.",
            ),
        ),
        migrations.AddField(
            model_name="productreview",
            name="flagged_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="productreview",
            name="flagged_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="flagged_product_reviews",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
