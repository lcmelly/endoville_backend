from django.db import migrations


def remove_default_warehouse(apps, schema_editor):
    Warehouse = apps.get_model("orders", "Warehouse")
    Order = apps.get_model("orders", "Order")
    default = Warehouse.objects.filter(code="US-IMAIL").first()
    if default is None:
        return
    Order.objects.filter(warehouse=default).update(warehouse=None)
    default.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0006_manager_group"),
    ]

    operations = [
        migrations.RunPython(remove_default_warehouse, migrations.RunPython.noop),
    ]
