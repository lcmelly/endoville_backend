from datetime import timedelta
from decimal import Decimal

import pytest
from background_task.models import Task
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from orders.currency_utils import amount_to_primary, order_total_in_currency, snapshot_usd_rate
from orders.models import (
    Order,
    OrderPayment,
    PaymentCredentials,
    PaymentProvider,
    PaymentStatus,
    ShippingAddress,
)
from orders.payments.stripe_rates import ensure_stripe_rates_fresh, sync_currency_rates_from_stripe
from products.models import Currency, Product, ProductVariant
from users.models import CustomUser


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_fx_cache():
    cache.clear()
    yield
    cache.clear()


def _stripe_credentials():
    creds = PaymentCredentials(provider=PaymentProvider.STRIPE, environment="sandbox", is_active=True)
    creds.set_private_key("sk_test_fx")
    creds.save()
    return creds


def _quote(rate):
    return {"rates": {"usd": {"exchange_rate": rate}}}


class _CountingClient:
    def __init__(self, key, quotes):
        assert key == "sk_test_fx"
        self.quotes = quotes

    def raw_request(self, method, url, **params):
        assert method == "post"
        assert url == "/v1/fx_quotes"
        assert params["from_currencies"] == ["usd"]
        assert params["lock_duration"] == "hour"
        self.quotes["calls"] += 1
        code = params["to_currency"]
        handler = self.quotes["by_code"][code]
        if isinstance(handler, Exception):
            raise handler
        return handler


def _patch_client(monkeypatch, by_code):
    quotes = {"calls": 0, "by_code": by_code}

    class Client(_CountingClient):
        def __init__(self, key):
            super().__init__(key, quotes)

    monkeypatch.setattr("stripe.StripeClient", Client)
    return quotes


def _buyer_order(total="10.00"):
    user = CustomUser.objects.create_user(email="buyer@example.com", password="strongpass", is_active=True)
    address = ShippingAddress.objects.create(
        user=user,
        full_name="Jane Buyer",
        phone="0712345678",
        email="buyer@example.com",
        address_line_1="Street 1",
        city="Nairobi",
        country="Kenya",
    )
    order = Order.objects.create(user=user, shipping_address=address, total=Decimal(total))
    return user, order


def test_sync_writes_stripe_exchange_rate(monkeypatch):
    _stripe_credentials()
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    kes = Currency.objects.create(code="KES", name="Kenyan Shilling", symbol="KSh", usd_rate="100")

    class FakeClient:
        def __init__(self, key):
            assert key == "sk_test_fx"

        def raw_request(self, method, url, **params):
            assert method == "post"
            assert url == "/v1/fx_quotes"
            assert params["to_currency"] == "kes"
            assert params["from_currencies"] == ["usd"]
            assert params["lock_duration"] == "hour"
            return _quote("160.25")

    monkeypatch.setattr("stripe.StripeClient", FakeClient)
    result = sync_currency_rates_from_stripe()
    kes.refresh_from_db()
    assert result["updated"] == ["KES"]
    assert result["error"] is None
    assert kes.usd_rate == Decimal("160.250000")
    assert kes.rate_synced_at is not None
    assert Currency.objects.get(code="USD").usd_rate == Decimal("1.000000")


def test_sync_without_credentials_keeps_stored_rate():
    kes = Currency.objects.create(code="KES", name="Kenyan Shilling", symbol="KSh", usd_rate="100")
    result = sync_currency_rates_from_stripe()
    kes.refresh_from_db()
    assert result["updated"] == []
    assert "credentials" in result["error"].lower()
    assert kes.usd_rate == Decimal("100.000000")
    assert kes.rate_synced_at is None


def test_shopper_price_uses_stripe_rate(monkeypatch):
    _stripe_credentials()
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    Currency.objects.create(code="KES", name="Kenyan Shilling", symbol="KSh", usd_rate="100")
    product = Product.objects.create(name="Serum", description="d", price="10.00", stock=3, slug="serum")

    class FakeClient:
        def __init__(self, key):
            pass

        def raw_request(self, method, url, **params):
            return _quote("160.25")

    monkeypatch.setattr("stripe.StripeClient", FakeClient)
    resp = APIClient().get(f"/api/products/products/{product.id}/", {"currency": "KES"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_currency"] == "KES"
    assert data["price"] == "1602.50"
    kes = Currency.objects.get(code="KES")
    assert kes.usd_rate == Decimal("160.250000")


def test_payment_keeps_the_rate_used_at_checkout():
    """A later Stripe refresh must not change whether this payment covers the order."""
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    kes = Currency.objects.create(
        code="KES",
        name="Kenyan Shilling",
        symbol="KSh",
        usd_rate="160.25",
    )
    user = CustomUser.objects.create_user(email="buyer@example.com", password="strongpass", is_active=True)
    address = ShippingAddress.objects.create(
        user=user,
        full_name="Jane Buyer",
        phone="0712345678",
        email="buyer@example.com",
        address_line_1="Street 1",
        city="Nairobi",
        country="Kenya",
    )
    order = Order.objects.create(user=user, shipping_address=address, total=Decimal("10.00"))
    payment = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.STRIPE,
        status=PaymentStatus.COMPLETED,
        amount=Decimal("1602.50"),
        currency="KES",
        usd_rate=Decimal("160.25"),
    )
    kes.usd_rate = Decimal("200")
    kes.save(update_fields=["usd_rate"])
    assert amount_to_primary(payment.amount, payment.currency, usd_rate=payment.usd_rate) == Decimal("10.00")
    assert order.recalculate_is_fully_paid() is True


def test_update_currency_rates_command(monkeypatch, capsys):
    _stripe_credentials()
    Currency.objects.create(code="KES", name="Kenyan Shilling", symbol="KSh", usd_rate="100")

    monkeypatch.setattr(
        "orders.payments.stripe_rates.sync_currency_rates_from_stripe",
        lambda: {"updated": ["KES"], "failed": [], "error": None},
    )
    call_command("update_currency_rates")
    assert "Updated: KES" in capsys.readouterr().out


def test_failed_quote_is_reported(monkeypatch):
    _stripe_credentials()
    Currency.objects.create(code="XXX", name="Unknown", symbol="?", usd_rate="1")

    class FakeClient:
        def __init__(self, key):
            pass

        def raw_request(self, method, url, **params):
            raise RuntimeError("currency_not_supported")

    monkeypatch.setattr("stripe.StripeClient", FakeClient)
    result = sync_currency_rates_from_stripe()
    assert result["failed"] == ["XXX"]
    assert result["updated"] == []
    assert Currency.objects.get(code="XXX").rate_synced_at is None


def test_sync_skips_inactive_and_usd_and_rejects_non_positive_rate(monkeypatch):
    _stripe_credentials()
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    inactive = Currency.objects.create(
        code="NGN", name="Naira", symbol="₦", usd_rate="500", is_active=False
    )
    eur = Currency.objects.create(code="EUR", name="Euro", symbol="€", usd_rate="0.90")
    kes = Currency.objects.create(code="KES", name="Kenyan Shilling", symbol="KSh", usd_rate="100")

    class QuoteRow:
        exchange_rate = "160.250000"

    quotes = _patch_client(
        monkeypatch,
        {"kes": {"rates": {"usd": QuoteRow()}}, "eur": _quote("0")},
    )
    result = sync_currency_rates_from_stripe()
    kes.refresh_from_db()
    eur.refresh_from_db()
    inactive.refresh_from_db()
    assert result["updated"] == ["KES"]
    assert result["failed"] == ["EUR"]
    assert quotes["calls"] == 2
    assert kes.usd_rate == Decimal("160.250000")
    assert eur.usd_rate == Decimal("0.900000")
    assert eur.rate_synced_at is None
    assert inactive.usd_rate == Decimal("500.000000")
    assert inactive.rate_synced_at is None
    assert Currency.objects.get(code="USD").rate_synced_at is None


def test_fresh_rates_are_not_quoted_again(monkeypatch):
    _stripe_credentials()
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    kes = Currency.objects.create(
        code="KES",
        name="Kenyan Shilling",
        symbol="KSh",
        usd_rate="160.25",
        rate_synced_at=timezone.now(),
    )
    quotes = _patch_client(monkeypatch, {})
    ensure_stripe_rates_fresh()
    ensure_stripe_rates_fresh()
    kes.refresh_from_db()
    assert quotes["calls"] == 0
    assert kes.usd_rate == Decimal("160.250000")


def test_stale_rate_refreshes_once_per_window(monkeypatch):
    _stripe_credentials()
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    kes = Currency.objects.create(
        code="KES",
        name="Kenyan Shilling",
        symbol="KSh",
        usd_rate="100",
        rate_synced_at=timezone.now() - timedelta(seconds=3601),
    )
    quotes = _patch_client(monkeypatch, {"kes": _quote("160.25")})
    ensure_stripe_rates_fresh()
    ensure_stripe_rates_fresh()
    kes.refresh_from_db()
    assert quotes["calls"] == 1
    assert kes.usd_rate == Decimal("160.250000")
    assert order_total_in_currency(Decimal("10.00"), "KES") == Decimal("1602.50")
    assert quotes["calls"] == 1


@override_settings(STRIPE_FX_SYNC_ENABLED=False)
def test_sync_can_be_disabled(monkeypatch):
    _stripe_credentials()
    kes = Currency.objects.create(code="KES", name="Kenyan Shilling", symbol="KSh", usd_rate="100")
    quotes = _patch_client(monkeypatch, {"kes": _quote("160.25")})
    ensure_stripe_rates_fresh()
    kes.refresh_from_db()
    assert quotes["calls"] == 0
    assert kes.usd_rate == Decimal("100.000000")
    assert kes.rate_synced_at is None


def test_currency_api_returns_rate_synced_at_and_ignores_writes():
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    resp = APIClient().get("/api/products/currencies/")
    assert resp.status_code == 200
    assert resp.json()[0]["rate_synced_at"] is None

    admin = CustomUser.objects.create_superuser(
        email="admin@example.com", password="strongpass"
    )
    client = APIClient()
    client.force_authenticate(user=admin)
    created = client.post(
        "/api/products/currencies/",
        {
            "code": "KES",
            "name": "Kenyan Shilling",
            "symbol": "KSh",
            "usd_rate": "160.50",
            "rate_synced_at": "2020-01-01T00:00:00Z",
        },
        format="json",
    )
    assert created.status_code == 201
    assert created.json()["rate_synced_at"] is None
    assert Currency.objects.get(code="KES").rate_synced_at is None


def test_variant_price_uses_the_same_stripe_rate(monkeypatch):
    _stripe_credentials()
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    Currency.objects.create(code="KES", name="Kenyan Shilling", symbol="KSh", usd_rate="100")
    product = Product.objects.create(name="Serum", description="d", price="10.00", stock=3, slug="serum")
    ProductVariant.objects.create(product=product, price="2.00", stock=1)
    _patch_client(monkeypatch, {"kes": _quote("160.25")})

    resp = APIClient().get(f"/api/products/products/{product.id}/", {"currency": "KES"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["price"] == "1602.50"
    assert data["variants"][0]["price"] == "320.50"
    assert data["variants"][0]["display_currency"] == "KES"


def test_checkout_charges_the_displayed_price_and_stores_the_rate(monkeypatch):
    _stripe_credentials()
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    Currency.objects.create(code="KES", name="Kenyan Shilling", symbol="KSh", usd_rate="100")
    product = Product.objects.create(name="Serum", description="d", price="10.00", stock=3, slug="serum")
    user, order = _buyer_order("10.00")
    quotes = _patch_client(monkeypatch, {"kes": _quote("160.25")})
    charged = {}

    def fake_checkout(self, payment, success_url, cancel_url):
        charged["amount"] = payment.amount
        charged["currency"] = payment.currency
        charged["unit_amount"] = int(payment.amount * 100)
        payment.checkout_url = "https://checkout.stripe.test/c"
        payment.provider_payment_id = "cs_test_1"
        payment.save(update_fields=["checkout_url", "provider_payment_id", "updated_at"])
        return {"success": True}

    monkeypatch.setattr("orders.payments.stripe.StripeAPI.create_checkout_session", fake_checkout)

    shopper = APIClient().get(f"/api/products/products/{product.id}/", {"currency": "KES"})
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(
        "/api/orders/payments/",
        {"order": order.public_id, "provider": "stripe", "method": "checkout", "currency": "KES"},
        format="json",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["amount"] == shopper.json()["price"] == "1602.50"
    assert data["currency"] == "KES"
    assert data["usd_rate"] == "160.250000"
    assert data["checkout_url"] == "https://checkout.stripe.test/c"
    assert charged == {"amount": Decimal("1602.50"), "currency": "KES", "unit_amount": 160250}
    assert quotes["calls"] == 1

    payment = OrderPayment.objects.get(id=data["id"])
    Currency.objects.filter(code="KES").update(usd_rate=Decimal("200"))
    assert order.recalculate_is_fully_paid() is False
    OrderPayment.objects.filter(pk=payment.pk).update(status=PaymentStatus.COMPLETED)
    assert order.recalculate_is_fully_paid() is True


def test_payment_without_a_stored_rate_uses_the_current_table():
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    kes = Currency.objects.create(code="KES", name="Kenyan Shilling", symbol="KSh", usd_rate="160.25")
    _user, order = _buyer_order("10.00")
    OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.STRIPE,
        status=PaymentStatus.COMPLETED,
        amount=Decimal("1602.50"),
        currency="KES",
    )
    assert order.recalculate_is_fully_paid() is True
    kes.usd_rate = Decimal("200")
    kes.save(update_fields=["usd_rate"])
    assert order.recalculate_is_fully_paid() is False


def test_snapshot_usd_rate_for_primary_and_unknown():
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    Currency.objects.create(code="KES", name="Kenyan Shilling", symbol="KSh", usd_rate="160.25")
    assert snapshot_usd_rate("USD") == Decimal("1")
    assert snapshot_usd_rate("kes") == Decimal("160.250000")
    assert snapshot_usd_rate("") is None
    assert snapshot_usd_rate("ZZZ") is None


def test_update_command_prints_failures(monkeypatch, capsys):
    monkeypatch.setattr(
        "orders.payments.stripe_rates.sync_currency_rates_from_stripe",
        lambda: {"updated": ["KES"], "failed": ["EUR"], "error": None},
    )
    call_command("update_currency_rates")
    assert "Updated: KES. Failed: EUR." in capsys.readouterr().out


def test_update_command_prints_stripe_error(monkeypatch, capsys):
    monkeypatch.setattr(
        "orders.payments.stripe_rates.sync_currency_rates_from_stripe",
        lambda: {"updated": [], "failed": [], "error": "No active Stripe credentials found"},
    )
    call_command("update_currency_rates")
    assert "No active Stripe credentials found" in capsys.readouterr().err


@override_settings(STRIPE_FX_MAX_AGE_SECONDS=900)
def test_schedule_command_queues_repeating_sync():
    call_command("schedule_currency_rate_updates")
    task = Task.objects.get()
    assert "run_currency_rate_sync_task" in task.task_name
    assert task.repeat == 900
