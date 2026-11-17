import secrets

from django.db import migrations, models


def fill_public_ids(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    seen = set(Order.objects.exclude(public_id__isnull=True).values_list("public_id", flat=True))
    for order in Order.objects.filter(public_id__isnull=True).iterator():
        while True:
            candidate = secrets.token_urlsafe(12)
            if candidate not in seen:
                seen.add(candidate)
                order.public_id = candidate
                order.save(update_fields=["public_id"])
                break


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0019_shipping_rate_validators"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="public_id",
            field=models.CharField(editable=False, max_length=32, null=True, unique=True),
        ),
        migrations.RunPython(fill_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="order",
            name="public_id",
            field=models.CharField(
                editable=False,
                help_text="Unguessable id used in the API. Not a counter.",
                max_length=32,
                unique=True,
            ),
        ),
        migrations.CreateModel(
            name="CustomerMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=16)),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="customer_messages",
                        to="orders.order",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "verbose_name": "Customer message",
            },
        ),
    ]
