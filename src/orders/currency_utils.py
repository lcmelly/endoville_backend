"""
Order total and payment amount conversion using products.Currency.

Order total is stored in the primary currency (typically USD). When creating a payment
in KES or another currency, we convert the order total using the Currency.usd_rate
(1 USD = usd_rate × target currency). When checking if an order is fully paid, we
convert each payment amount back to primary for comparison.
"""

from decimal import Decimal

from products.models import Currency


def get_currency_rate(code: str):
    """Return Currency for code, or None if not found/inactive."""
    if not code:
        return None
    return Currency.objects.filter(code=code.upper().strip(), is_active=True).first()


def get_primary_currency():
    """Return the primary currency (e.g. USD), or first active USD by code."""
    c = Currency.objects.filter(is_primary=True, is_active=True).first()
    if c:
        return c
    return Currency.objects.filter(code="USD", is_active=True).first()


def order_total_in_currency(order_total_primary: Decimal, target_currency_code: str) -> Decimal:
    """
    Convert order total (in primary currency, e.g. USD) to target currency.
    Uses Currency.usd_rate: 1 USD = usd_rate × target. Returns value rounded to 2 decimals.
    If target is primary or rate not found, returns order_total_primary unchanged.
    """
    if order_total_primary is None:
        return Decimal("0")
    order_total_primary = Decimal(str(order_total_primary))
    primary = get_primary_currency()
    target_code = (target_currency_code or "").strip().upper()
    if not target_code:
        return order_total_primary
    if primary and target_code == primary.code:
        return order_total_primary
    target_currency = get_currency_rate(target_code)
    if not target_currency or not target_currency.usd_rate:
        return order_total_primary
    rate = Decimal(str(target_currency.usd_rate))
    return (order_total_primary * rate).quantize(Decimal("0.01"))


def amount_to_primary(amount: Decimal, currency_code: str) -> Decimal:
    """
    Convert a payment amount from the given currency to primary (USD).
    amount_primary = amount / usd_rate. For primary currency, returns amount unchanged.
    """
    if amount is None:
        return Decimal("0")
    amount = Decimal(str(amount))
    primary = get_primary_currency()
    code = (currency_code or "").strip().upper()
    if not code or (primary and code == primary.code):
        return amount
    currency = get_currency_rate(code)
    if not currency or not currency.usd_rate:
        return amount
    rate = Decimal(str(currency.usd_rate))
    if rate == 0:
        return amount
    return (amount / rate).quantize(Decimal("0.01"))
