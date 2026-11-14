import uuid

from django.db import migrations, models


def fill_refund_identity(apps, schema_editor):
    OrderRefund = apps.get_model("orders", "OrderRefund")
    for refund in OrderRefund.objects.all().iterator():
        reason = (refund.reason or "").strip() or "Not recorded"
        transaction_id = (refund.transaction_id or "").strip() or f"rf-{uuid.uuid4().hex}"
        OrderRefund.objects.filter(pk=refund.pk).update(reason=reason, transaction_id=transaction_id)


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0010_refund_partial_and_line_changes"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderrefund",
            name="transaction_id",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.RunPython(fill_refund_identity, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="orderrefund",
            name="reason",
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name="orderrefund",
            name="transaction_id",
            field=models.CharField(db_index=True, max_length=64, unique=True),
        ),
    ]
