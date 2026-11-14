---
title: Shipping rates
icon: lucide/truck
---

# Shipping rates

Checkout sets the shipping fee. A fee sent with the order is ignored.

The fee is in USD:

`base fee + (total product weight in kilograms × the country's price per kilogram)`

Product weight is `unit_weight`, in grams. A variant line uses the product's weight. Half a kilogram is 500 grams.

Example: the base fee is `2.00` and Kenya is `20.00` per kilogram. A basket that weighs 500 grams ships for `2.00 + 10.00 = 12.00`.

Until an admin adds a country, every destination pays only the base fee. After at least one country is saved, checkout and quotes refuse a country that is not on the list. The message is `Shipping to this country is not set.`

The `Orders` role can still change `shipping_fee` on an order that has already been placed.

=== "Base URL"

    ```
    /api/orders/shipping-rates/
    ```

=== "Authentication"

    | What you want to do | Who can do it |
    |---|---|
    | Read the schedule | Anyone |
    | Quote a basket | Anyone |
    | Replace the base fee and the countries | An admin (`is_superuser`) |

    A staff user who is not an admin gets `403` on the update.

## Endpoints

=== "Read"

    ```
    GET /api/orders/shipping-rates/
    ```

    Success (200):

    ```json
    {
      "base_fee": "2.00",
      "countries": [
        { "country": "Kenya", "per_kg": "20.00" }
      ]
    }
    ```

    A new shop has `"base_fee": "0.00"` and `"countries": []`.

=== "Replace"

    ```
    PUT /api/orders/shipping-rates/
    ```

    Admins only. This replaces the whole schedule. A country left out of `countries` is removed.

    ```json
    {
      "base_fee": "2.00",
      "countries": [
        { "country": "Kenya", "per_kg": "20.00" },
        { "country": "Nigeria", "per_kg": "15.00" }
      ]
    }
    ```

    Success (200) returns the saved schedule. `base_fee` and `per_kg` cannot be negative. The same country cannot be listed twice. Matching ignores letter case, so `kenya` and `Kenya` are one country.

=== "Quote"

    ```
    POST /api/orders/shipping-rates/quote/
    ```

    ```json
    {
      "country": "Kenya",
      "items": [
        { "product": 1, "quantity": 1 },
        { "variant": 10, "quantity": 2 }
      ]
    }
    ```

    Each item is a product or a variant, and a quantity of at least 1.

    Success (200):

    ```json
    {
      "country": "Kenya",
      "weight_grams": 500,
      "shipping_fee": "12.00"
    }
    ```

    `400` when the country is not on the schedule, or an item is missing.
