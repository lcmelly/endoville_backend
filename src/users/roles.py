from django.contrib.auth.models import Group

STAFF_ROLES = ("Orders", "Shipping", "Stock", "Manager")
DEFAULT_STAFF_ROLES = ("Orders", "Shipping", "Stock")


def has_staff_role(user, *roles):
    if not user or not getattr(user, "is_authenticated", False) or not user.is_active:
        return False
    if user.is_superuser:
        return True
    if not user.is_staff:
        return False
    names = roles or STAFF_ROLES
    return user.groups.filter(name__in=names).exists()


def role_names(user):
    if not user or not getattr(user, "pk", None):
        return []
    if user.is_superuser:
        return list(STAFF_ROLES)
    if not user.is_staff:
        return []
    held = set(user.groups.filter(name__in=STAFF_ROLES).values_list("name", flat=True))
    return [name for name in STAFF_ROLES if name in held]


def ensure_default_staff_roles(user):
    """Staff created before a role was ticked keep every role."""
    if not user.is_staff or not user.pk:
        return
    if user.groups.filter(name__in=STAFF_ROLES).exists():
        return
    groups = [Group.objects.get_or_create(name=name)[0] for name in DEFAULT_STAFF_ROLES]
    user.groups.add(*groups)


def set_staff_roles(user, names):
    selected = [Group.objects.get_or_create(name=name)[0] for name in names]
    others = list(user.groups.exclude(name__in=STAFF_ROLES))
    user.groups.set([*others, *selected])
