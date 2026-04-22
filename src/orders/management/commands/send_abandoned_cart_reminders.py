from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Queue a single django-background-tasks run of abandoned cart reminder processing. "
        "Requires a worker: python manage.py process_tasks"
    )

    def handle(self, *args, **options):
        from orders.background_tasks import run_abandoned_cart_reminders_task

        run_abandoned_cart_reminders_task()
        self.stdout.write(
            self.style.SUCCESS(
                "Queued abandoned cart reminder job (single run). "
                "Ensure `process_tasks` is running to execute it."
            )
        )
