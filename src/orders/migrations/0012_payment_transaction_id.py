import uuid

from django.db import migrations, models


def fill_payment_transaction_id(apps, schema_editor):
    OrderPayment = apps.get_model("orders", "OrderPayment")
    for payment in OrderPayment.objects.all().iterator():
        transaction_id = (payment.transaction_id or "").strip() or f"pay-{uuid.uuid4().hex}"
        OrderPayment.objects.filter(pk=payment.pk).update(transaction_id=transaction_id)


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0011_refund_transaction_id_and_reason"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderpayment",
            name="transaction_id",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.RunPython(fill_payment_transaction_id, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="orderpayment",
            name="transaction_id",
            field=models.CharField(blank=True, db_index=True, max_length=64, unique=True),
        ),
    ]
