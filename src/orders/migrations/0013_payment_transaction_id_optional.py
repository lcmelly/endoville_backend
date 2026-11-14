from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0012_payment_transaction_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="orderpayment",
            name="transaction_id",
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True, unique=True),
        ),
    ]
