from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0016_product_unit_weight"),
    ]

    operations = [
        migrations.AddField(
            model_name="currency",
            name="rate_synced_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When usd_rate was last written from a Stripe FX quote.",
                null=True,
            ),
        ),
    ]
