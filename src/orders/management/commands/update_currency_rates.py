from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Refresh active non-USD currency rates from Stripe FX quotes so shopper "
        "prices match the amount checkout will charge."
    )

    def handle(self, *args, **options):
        from orders.payments.stripe_rates import sync_currency_rates_from_stripe

        result = sync_currency_rates_from_stripe()
        if result.get("error"):
            self.stderr.write(self.style.ERROR(result["error"]))
            return
        updated = ", ".join(result.get("updated") or []) or "none"
        failed = ", ".join(result.get("failed") or []) or "none"
        self.stdout.write(self.style.SUCCESS(f"Updated: {updated}. Failed: {failed}."))
