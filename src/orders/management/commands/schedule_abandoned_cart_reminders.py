from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Schedule a repeating django-background-tasks job that runs abandoned cart "
        "reminder processing (see ABANDONED_CART_REMINDER_BG_INTERVAL_SECONDS). "
        "Run once after deploy if you use this pattern; keep `process_tasks` running."
    )

    def handle(self, *args, **options):
        from orders.background_tasks import run_abandoned_cart_reminders_task

        interval = getattr(settings, "ABANDONED_CART_REMINDER_BG_INTERVAL_SECONDS", 900)
        run_abandoned_cart_reminders_task(schedule=timezone.now(), repeat=interval)
        self.stdout.write(
            self.style.SUCCESS(
                f"Queued repeating abandoned-cart reminder task (every {interval}s). "
                "Ensure a worker is running: python manage.py process_tasks"
            )
        )
