from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0007_remove_default_warehouse"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderpayment",
            name="usd_rate",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text="Units of this payment currency per 1 USD when the payment was created.",
                max_digits=18,
                null=True,
            ),
        ),
    ]
