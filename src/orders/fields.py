from rest_framework import serializers

from .models import Order


class OrderPublicIdField(serializers.SlugRelatedField):
    """Accept and return the unguessable order id, never the database counter."""

    def __init__(self, **kwargs):
        kwargs["slug_field"] = "public_id"
        if not kwargs.get("read_only"):
            kwargs.setdefault("queryset", Order.objects.all())
        super().__init__(**kwargs)
