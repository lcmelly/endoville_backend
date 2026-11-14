"""
Jobs executed by django-background-tasks (`python manage.py process_tasks`).

Import this module from `orders.apps` so the @background registry is loaded when Django starts.
"""

from background_task import background

from .payments.stripe_rates import sync_currency_rates_from_stripe
from .reminders import process_abandoned_cart_reminders


@background()
def run_abandoned_cart_reminders_task():
    """Process due abandoned-cart reminder emails (12h, then 24h, then 48h)."""
    process_abandoned_cart_reminders()


@background()
def run_currency_rate_sync_task():
    """Refresh Currency.usd_rate from Stripe FX quotes."""
    sync_currency_rates_from_stripe()


@background()
def run_open_stripe_payment_status_task():
    """Ask Stripe whether each open checkout session has been paid."""
    from .payments.stripe import sync_all_open_stripe_payments

    sync_all_open_stripe_payments()


def ensure_open_stripe_payment_status_schedule():
    """Queue the Stripe status check once a minute when it is not already queued."""
    from background_task.models import Task
    from django.conf import settings
    from django.utils import timezone

    interval = int(getattr(settings, "STRIPE_PAYMENT_STATUS_INTERVAL_SECONDS", 60))
    name = "orders.background_tasks.run_open_stripe_payment_status_task"
    existing = Task.objects.filter(task_name=name)
    if existing.exists():
        existing.exclude(repeat=interval).update(repeat=interval)
        return
    run_open_stripe_payment_status_task(schedule=timezone.now(), repeat=interval)
