from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .emails import send_abandoned_cart_reminder_email
from .models import Cart

REMINDER_STEPS = (12, 24, 48)


def _covered(cart):
    if cart.last_reminder_at is None or cart.last_reminder_at < cart.updated_at:
        return timedelta(0)
    return cart.last_reminder_at - cart.updated_at


def _next_step(cart, now):
    idle = now - cart.updated_at
    covered = _covered(cart)
    for hours in REMINDER_STEPS:
        if covered >= timedelta(hours=hours):
            continue
        if idle >= timedelta(hours=hours):
            return hours
        return None
    return None


def process_abandoned_cart_reminders(now=None):
    """
    Send staged abandoned-cart reminders at 12h, 24h, and 48h after
    cart inactivity. At most one reminder is sent per cart per run.
    """
    now = now or timezone.now()
    carts = (
        Cart.objects.select_related("user")
        .prefetch_related("items__product", "items__variant", "items__variant__product")
        .all()
    )

    sent = 0
    for cart in carts:
        if not cart.items.exists():
            continue
        target_hours = _next_step(cart, now)
        if target_hours is None:
            continue
        if not send_abandoned_cart_reminder_email(cart.id, reminder_hours=target_hours):
            continue

        with transaction.atomic():
            locked = Cart.objects.select_for_update().get(pk=cart.pk)
            if _next_step(locked, now) != target_hours:
                continue
            locked.last_reminder_at = locked.updated_at + timedelta(hours=target_hours)
            locked.save(update_fields=["last_reminder_at"])
            sent += 1

    return sent
