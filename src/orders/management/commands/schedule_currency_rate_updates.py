from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Schedule a repeating django-background-tasks job that refreshes currency "
        "rates from Stripe (see STRIPE_FX_MAX_AGE_SECONDS). "
        "Run once after deploy if you use this pattern; keep `process_tasks` running."
    )

    def handle(self, *args, **options):
        from orders.background_tasks import run_currency_rate_sync_task

        interval = getattr(settings, "STRIPE_FX_MAX_AGE_SECONDS", 3600)
        run_currency_rate_sync_task(schedule=timezone.now(), repeat=interval)
        self.stdout.write(
            self.style.SUCCESS(
                f"Queued repeating Stripe FX rate sync (every {interval}s). "
                "Ensure a worker is running: python manage.py process_tasks"
            )
        )
