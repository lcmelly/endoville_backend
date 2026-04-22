"""
Jobs executed by django-background-tasks (`python manage.py process_tasks`).

Import this module from `orders.apps` so the @background registry is loaded when Django starts.
"""

from background_task import background

from .reminders import process_abandoned_cart_reminders


@background()
def run_abandoned_cart_reminders_task():
    """Process due abandoned-cart reminder emails (5h / 12h / 24h logic)."""
    process_abandoned_cart_reminders()
