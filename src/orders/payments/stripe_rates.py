"""
Keep Currency.usd_rate aligned with Stripe FX quotes.

`usd_rate` is how many units of that currency equal 1 USD. Shopper prices and
checkout amounts both multiply the stored USD price by this rate, so a Stripe
quote is the amount the client is charged.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

_FRESH_CACHE_KEY = "stripe_fx_rates_fresh"
_SKIP_CACHE_KEY = "stripe_fx_rates_skip"
_LOCK_CACHE_KEY = "stripe_fx_rates_lock"


def _max_age_seconds() -> int:
    return int(getattr(settings, "STRIPE_FX_MAX_AGE_SECONDS", 3600))


def _rates_are_stale() -> bool:
    from products.models import Currency

    cutoff = timezone.now() - timedelta(seconds=_max_age_seconds())
    return (
        Currency.objects.filter(is_active=True)
        .exclude(code__iexact="USD")
        .filter(Q(rate_synced_at__isnull=True) | Q(rate_synced_at__lt=cutoff))
        .exists()
    )


def ensure_stripe_rates_fresh() -> None:
    """
    Refresh active non-USD rates from Stripe when the last sync is older than
    STRIPE_FX_MAX_AGE_SECONDS. Missing credentials or a Stripe error leaves the
    stored rates in place.
    """
    if not getattr(settings, "STRIPE_FX_SYNC_ENABLED", True):
        return
    if cache.get(_FRESH_CACHE_KEY) or cache.get(_SKIP_CACHE_KEY):
        return
    if not _rates_are_stale():
        cache.set(_FRESH_CACHE_KEY, 1, timeout=_max_age_seconds())
        return
    if not cache.add(_LOCK_CACHE_KEY, 1, timeout=60):
        return
    try:
        result = sync_currency_rates_from_stripe()
        if result.get("error"):
            logger.warning("Stripe FX rate sync skipped: %s", result["error"])
            cache.set(_SKIP_CACHE_KEY, 1, timeout=60)
            return
        if _rates_are_stale():
            cache.set(_SKIP_CACHE_KEY, 1, timeout=60)
            return
        cache.set(_FRESH_CACHE_KEY, 1, timeout=_max_age_seconds())
    except Exception:
        logger.exception("Stripe FX rate sync failed")
        cache.set(_SKIP_CACHE_KEY, 1, timeout=60)
    finally:
        cache.delete(_LOCK_CACHE_KEY)


def sync_currency_rates_from_stripe() -> dict:
    """
    Write usd_rate for each active non-USD currency from a Stripe FX quote.

    The quote converts USD into that currency. `exchange_rate` is the multiplier
    Stripe uses, including its FX fee, so the shopper price matches checkout.
    USD is left at 1. Returns {"updated": [...], "failed": [...], "error": str|None}.
    """
    from orders.payments.stripe import StripeAPI
    from products.models import Currency

    try:
        api = StripeAPI()
    except (ValueError, ImportError) as exc:
        return {"updated": [], "failed": [], "error": str(exc)}

    currencies = list(Currency.objects.filter(is_active=True).exclude(code__iexact="USD"))
    if not currencies:
        return {"updated": [], "failed": [], "error": None}

    import stripe

    client = stripe.StripeClient(api.secret_key)
    updated = []
    failed = []
    now = timezone.now()
    for currency in currencies:
        try:
            rate = _usd_to_currency_rate(client, currency.code)
        except Exception as exc:
            logger.warning("Stripe FX quote failed for %s: %s", currency.code, exc)
            failed.append(currency.code)
            continue
        currency.usd_rate = rate
        currency.rate_synced_at = now
        currency.save(update_fields=["usd_rate", "rate_synced_at", "updated_at"])
        updated.append(currency.code)
    return {"updated": updated, "failed": failed, "error": None}


def _usd_to_currency_rate(client, code: str) -> Decimal:
    quote = client.raw_request(
        "post",
        "/v1/fx_quotes",
        to_currency=code.lower(),
        from_currencies=["usd"],
        lock_duration="hour",
    )
    rates = quote["rates"]
    row = rates["usd"]
    if isinstance(row, dict):
        raw = row["exchange_rate"]
    else:
        try:
            raw = row["exchange_rate"]
        except Exception:
            raw = row.exchange_rate
    rate = Decimal(str(raw))
    if rate <= 0:
        raise ValueError(f"Stripe returned a non-positive USD rate for {code}")
    return rate.quantize(Decimal("0.000001"))
