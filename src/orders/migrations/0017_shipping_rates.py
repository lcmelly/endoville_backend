from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0016_cart_last_reminder_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShippingFee",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                (
                    "base_fee",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        help_text="USD charged on every shipment, before the country weight rate.",
                        max_digits=12,
                    ),
                ),
            ],
            options={
                "verbose_name": "Shipping base fee",
            },
        ),
        migrations.CreateModel(
            name="ShippingCountryRate",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("country", models.CharField(max_length=100, unique=True)),
                (
                    "per_kg",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="USD per kilogram shipped to this country.",
                        max_digits=12,
                    ),
                ),
            ],
            options={
                "ordering": ["country"],
            },
        ),
    ]
