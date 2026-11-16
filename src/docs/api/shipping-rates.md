---
title: Shipping rates
icon: lucide/truck
---

# Shipping rates

Checkout sets the shipping fee. A fee sent with the order is ignored.

The fee is in USD. Each country is one row: a unit weight in grams, and the USD fee for that unit.

A basket at or below the unit weight pays that fee. A heavier basket pays `(weight in grams ÷ unit weight) × fee`.

Product weight is `unit_weight`, in grams. A variant line uses the product's weight.

Example: Kenya is `20.00` per `1000` grams. A 500 gram basket ships for `20.00`. A 1500 gram basket ships for `30.00`.

Until an admin adds a country, every destination pays `0.00`. After at least one country is saved, checkout and quotes refuse a country that is not on the list. The message is `Shipping to this country is not set.`

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
    | Replace the country rates | An admin (`is_superuser`) |

    A staff user who is not an admin gets `403` on the update.

## Endpoints

=== "Read"

    ```
    GET /api/orders/shipping-rates/
    ```

    Success (200):

    ```json
    {
      "countries": [
        { "country": "Kenya", "unit_weight": 1000, "fee": "20.00" }
      ]
    }
    ```

    A new shop has `"countries": []`. `unit_weight` is grams. `fee` is USD for that many grams.

=== "Replace"

    ```
    PUT /api/orders/shipping-rates/
    ```

    Admins only. This replaces the whole table. A country left out of `countries` is removed. The same rows can be edited one at a time in Django admin.

    ```json
    {
      "countries": [
        { "country": "Kenya", "unit_weight": 1000, "fee": "20.00" },
        { "country": "Nigeria", "unit_weight": 500, "fee": "15.00" }
      ]
    }
    ```

    Success (200) returns the saved table. `fee` cannot be negative. `unit_weight` is at least 1 gram. The same country cannot be listed twice. Matching ignores letter case, so `kenya` and `Kenya` are one country.

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
      "shipping_fee": "20.00"
    }
    ```

    `400` when the country is not on the schedule, or an item is missing.
