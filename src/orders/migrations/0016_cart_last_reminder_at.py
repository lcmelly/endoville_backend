from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0015_orderitem_stock_taken"),
    ]

    operations = [
        migrations.AddField(
            model_name="cart",
            name="last_reminder_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Activity time plus the last reminder step that succeeded: 12, 24, or 48 hours.",
                null=True,
            ),
        ),
        migrations.RemoveField(
            model_name="cart",
            name="reminder_12_sent_at",
        ),
        migrations.RemoveField(
            model_name="cart",
            name="reminder_24_sent_at",
        ),
        migrations.RemoveField(
            model_name="cart",
            name="reminder_48_sent_at",
        ),
    ]
