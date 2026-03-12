# One-time: encrypt any PaymentCredentials.encrypted_private_key that was stored in plain text

from django.db import migrations


def encrypt_plaintext_private_keys(apps, schema_editor):
    """Encrypt any private key that was stored in plain text (e.g. from admin before we excluded the field)."""
    from orders.models import PaymentCredentials

    for cred in PaymentCredentials.objects.exclude(encrypted_private_key=""):
        val = cred.encrypted_private_key or ""
        if val.strip() and not val.strip().startswith("gAAAAA"):
            cred.set_private_key(val)
            cred.save(update_fields=["encrypted_private_key", "updated_at"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_order_status_new_choices_and_default"),
    ]

    operations = [
        migrations.RunPython(encrypt_plaintext_private_keys, noop),
    ]
