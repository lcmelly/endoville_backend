"""
Shipping fee for a destination country.

A basket at or below that country's unit weight pays the unit fee.
A heavier basket pays (weight ÷ unit weight) × that fee.

Both amounts are USD, which is how product prices and order totals are stored.
Weight comes from each product's unit_weight in grams. A variant line uses its product.
With no country rows saved, the fee is 0. Once any country is saved, a destination
that is not on the list cannot be quoted.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from .models import ShippingCountryRate

_CENTS = Decimal("0.01")


def weight_grams(product, variant, quantity) -> int:
    shelf = variant.product if variant is not None else product
    return int(shelf.unit_weight) * int(quantity)


def fee_for_weight(unit_fee, unit_weight, grams: int) -> Decimal:
    """Charge one unit when the basket is lighter than the unit, otherwise scale by weight."""
    unit = Decimal(int(unit_weight))
    if unit < 1:
        raise ValidationError("Shipping unit weight must be at least 1 gram.")
    weight = Decimal(int(grams))
    amount = Decimal(unit_fee)
    charged = amount if weight <= unit else weight / unit * amount
    return charged.quantize(_CENTS, rounding=ROUND_HALF_UP)


def quote_shipping(country: str, grams: int) -> Decimal:
    """Return the USD shipping fee for this destination and weight."""
    rates = ShippingCountryRate.objects.all()
    if not rates.exists():
        return Decimal("0.00")

    name = (country or "").strip()
    match = rates.filter(country__iexact=name).first() if name else None
    if match is None:
        raise ValidationError("Shipping to this country is not set.")
    return fee_for_weight(match.fee, match.unit_weight, grams)


def cart_shipping(country: str, grams: int) -> dict:
    """
    Fees a shopper can see for the current basket.

    shipping_fee is one number when the destination is known, when only one
    country is configured, or when no countries are configured (then 0).
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
        shipping_fee = f"{quote_shipping('', grams):.2f}"
    elif len(fees) == 1:
        shipping_fee = fees[0]["shipping_fee"]
    return {
        "weight_grams": int(grams),
        "shipping_fee": shipping_fee,
        "shipping_fees": fees,
    }
