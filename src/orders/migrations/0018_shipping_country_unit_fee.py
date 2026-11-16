import django.core.validators
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0017_shipping_rates"),
    ]

    operations = [
        migrations.AddField(
            model_name="shippingcountryrate",
            name="unit_weight",
            field=models.PositiveIntegerField(
                default=1000,
                help_text="Grams in one shipping unit. A lighter shipment is charged as one unit.",
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
        migrations.RenameField(
            model_name="shippingcountryrate",
            old_name="per_kg",
            new_name="fee",
        ),
        migrations.AlterField(
            model_name="shippingcountryrate",
            name="fee",
            field=models.DecimalField(
                decimal_places=2,
                help_text="USD for one unit of weight. Heavier shipments multiply this by weight ÷ unit weight.",
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
            ),
        ),
        migrations.DeleteModel(
            name="ShippingFee",
        ),
    ]
