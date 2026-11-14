"""
Shipping fee = base fee + (total product weight in kg × the destination's per-kg rate).

Both amounts are USD, which is how product prices and order totals are stored.
Weight comes from each product's unit_weight in grams. A variant line uses its product.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from .models import ShippingCountryRate, ShippingFee

_CENTS = Decimal("0.01")


def weight_grams(product, variant, quantity) -> int:
    shelf = variant.product if variant is not None else product
    return int(shelf.unit_weight) * int(quantity)


def quote_shipping(country: str, grams: int) -> Decimal:
    """
    Return the USD shipping fee for this destination and weight.

    With no country rates saved, the fee is the base fee alone.
    Once an admin has saved any country, a destination that is not on that list
    cannot be quoted.
    """
    base = Decimal(ShippingFee.load().base_fee)
    rates = ShippingCountryRate.objects.all()
    if not rates.exists():
        return base.quantize(_CENTS, rounding=ROUND_HALF_UP)

    name = (country or "").strip()
    match = rates.filter(country__iexact=name).first() if name else None
    if match is None:
        raise ValidationError("Shipping to this country is not set.")

    kilograms = Decimal(int(grams)) / Decimal("1000")
    fee = base + kilograms * Decimal(match.per_kg)
    return fee.quantize(_CENTS, rounding=ROUND_HALF_UP)


def cart_shipping(country: str, grams: int) -> dict:
    """
    Fees a shopper can see for the current basket.

    shipping_fee is one number when the destination is known, when only one
    country is configured, or when no countries are configured (the base fee).
    shipping_fees lists every configured country for this weight.
    """
    rates = list(ShippingCountryRate.objects.all())
    fees = [
        {"country": rate.country, "shipping_fee": f"{quote_shipping(rate.country, grams):.2f}"}
        for rate in rates
    ]
    selected = (country or "").strip()
    shipping_fee = None
    if selected:
        match = next((row for row in fees if row["country"].casefold() == selected.casefold()), None)
        if match is not None:
            shipping_fee = match["shipping_fee"]
        elif not rates:
            shipping_fee = f"{quote_shipping(selected, grams):.2f}"
    elif not rates:
        shipping_fee = f"{quote_shipping("", grams):.2f}"
    elif len(fees) == 1:
        shipping_fee = fees[0]["shipping_fee"]
    return {
        "weight_grams": int(grams),
        "shipping_fee": shipping_fee,
        "shipping_fees": fees,
    }
