from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def confirm_existing_lines(apps, schema_editor):
    OrderItem = apps.get_model("orders", "OrderItem")
    OrderItem.objects.update(availability="confirmed")


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0013_payment_transaction_id_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="availability",
            field=models.CharField(
                choices=[
                    ("pending", "Pending confirmation"),
                    ("confirmed", "Confirmed"),
                    ("unavailable", "Unavailable"),
                    ("replaced", "Replaced"),
                ],
                db_index=True,
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="availability_note",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="decided_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="decided_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="decided_order_items",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="replaces",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="replacement",
                to="orders.orderitem",
            ),
        ),
        migrations.AlterModelOptions(
            name="orderitem",
            options={"ordering": ["id"]},
        ),
        migrations.RunPython(confirm_existing_lines, migrations.RunPython.noop),
    ]
