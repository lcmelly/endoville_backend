from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Schedule a repeating job that checks open Stripe checkout sessions "
        "(see STRIPE_PAYMENT_STATUS_INTERVAL_SECONDS, default 60). "
        "Keep `python manage.py process_tasks` running."
    )

    def handle(self, *args, **options):
        from orders.background_tasks import ensure_open_stripe_payment_status_schedule

        ensure_open_stripe_payment_status_schedule()
        interval = int(getattr(settings, "STRIPE_PAYMENT_STATUS_INTERVAL_SECONDS", 60))
        self.stdout.write(
            self.style.SUCCESS(
                f"Queued repeating Stripe payment status check (every {interval}s). "
                "Ensure a worker is running: python manage.py process_tasks"
            )
        )
