from django.db import migrations

STAFF_ROLES = ("Orders", "Shipping", "Stock")


def create_staff_roles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("users", "CustomUser")
    groups = []
    for name in STAFF_ROLES:
        group, _created = Group.objects.get_or_create(name=name)
        groups.append(group)
    for user in User.objects.filter(is_staff=True):
        user.groups.add(*groups)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_staffchangelog"),
        ("orders", "0006_manager_group"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_staff_roles, migrations.RunPython.noop),
    ]
