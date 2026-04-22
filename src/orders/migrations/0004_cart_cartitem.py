from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0001_initial"),
        ("orders", "0003_encrypt_plaintext_payment_private_keys"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Cart",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reminder_12_sent_at", models.DateTimeField(blank=True, null=True)),
                ("reminder_24_sent_at", models.DateTimeField(blank=True, null=True)),
                ("reminder_48_sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cart",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CartItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "cart",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="orders.cart",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="products.product",
                    ),
                ),
                (
                    "variant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="products.productvariant",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=(
                            (models.Q(product__isnull=False, variant__isnull=True))
                            | (models.Q(product__isnull=True, variant__isnull=False))
                        ),
                        name="orders_cartitem_product_xor_variant",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(product__isnull=False),
                        fields=("cart", "product"),
                        name="orders_cartitem_unique_product_per_cart",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(variant__isnull=False),
                        fields=("cart", "variant"),
                        name="orders_cartitem_unique_variant_per_cart",
                    ),
                ]
            },
        ),
    ]
