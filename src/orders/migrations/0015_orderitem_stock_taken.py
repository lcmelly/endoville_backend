from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0014_orderitem_availability"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="stock_taken",
            field=models.BooleanField(
                default=True,
                help_text="True when checkout reduced a stock number for this line.",
            ),
        ),
    ]
