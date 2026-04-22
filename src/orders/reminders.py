from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .emails import send_abandoned_cart_reminder_email
from .models import Cart


REMINDER_STEPS = (
    (5, "reminder_5_sent_at"),
    (12, "reminder_12_sent_at"),
    (24, "reminder_24_sent_at"),
    (48, "reminder_48_sent_at"),
)


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

        inactivity = now - cart.updated_at
        target_hours = None

        if inactivity >= timedelta(hours=5) and cart.reminder_5_sent_at is None:
            target_hours = 5
        elif inactivity >= timedelta(hours=12) and cart.reminder_12_sent_at is None:
            target_hours = 12
        elif (
            inactivity >= timedelta(hours=24)
            and cart.reminder_12_sent_at is not None
            and cart.reminder_24_sent_at is None
        ):
            target_hours = 24
        elif (
            inactivity >= timedelta(hours=48)
            and cart.reminder_24_sent_at is not None
            and cart.reminder_48_sent_at is None
        ):
            target_hours = 48

        if target_hours is None:
            continue

        if not send_abandoned_cart_reminder_email(cart.id, reminder_hours=target_hours):
            continue

        with transaction.atomic():
            locked = Cart.objects.select_for_update().get(pk=cart.pk)
            if target_hours == 5 and locked.reminder_5_sent_at is None:
                locked.reminder_5_sent_at = now if now is not None else timezone.now()
            elif target_hours == 12 and locked.reminder_12_sent_at is None:
                locked.reminder_12_sent_at = now if now is not None else timezone.now()
            elif target_hours == 24 and locked.reminder_24_sent_at is None:
                locked.reminder_24_sent_at = now if now is not None else timezone.now()
            elif target_hours == 48 and locked.reminder_48_sent_at is None:
                locked.reminder_48_sent_at = now if now is not None else timezone.now()
            else:
                continue
            locked.save(update_fields=[f"reminder_{target_hours}_sent_at"])
            sent += 1

    return sent
