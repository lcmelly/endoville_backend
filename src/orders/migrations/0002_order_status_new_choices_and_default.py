# Generated manually for order status flow: Payment Pending -> Processing -> Shipping -> Complete

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("PAYMENT_PENDING", "Payment Pending"),
                    ("PLACED", "Placed"),
                    ("PROCESSING", "Processing"),
                    ("SHIPPING", "Shipping"),
                    ("COMPLETE", "Complete"),
                    ("CANCELLED", "Cancelled"),
                    ("REFUNDED", "Refunded"),
                ],
                db_index=True,
                default="PAYMENT_PENDING",
                max_length=20,
            ),
        ),
    ]
