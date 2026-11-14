from django.db import migrations


def create_manager_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Manager")


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0005_warehouse"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_manager_group, migrations.RunPython.noop),
    ]
