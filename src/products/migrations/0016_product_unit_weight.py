import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0015_productreview_flag_and_required_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="unit_weight",
            field=models.PositiveIntegerField(
                default=1,
                help_text="Weight of one unit, in grams.",
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
    ]
