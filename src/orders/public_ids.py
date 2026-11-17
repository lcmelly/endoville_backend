"""Unguessable public order ids."""

import secrets

from django.db import IntegrityError


def generate_order_public_id() -> str:
    """16-character URL-safe id. Callers still retry if the unique constraint trips."""
    return secrets.token_urlsafe(12)


def allocate_order_public_id() -> str:
    from .models import Order

    for _ in range(5):
        candidate = generate_order_public_id()
        if not Order.objects.filter(public_id=candidate).exists():
            return candidate
    raise IntegrityError("Could not allocate an order id.")
