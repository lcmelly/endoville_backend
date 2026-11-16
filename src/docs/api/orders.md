---
title: Orders
icon: lucide/receipt
---

# Orders

Place an order, then come back and read it. A shopper sees only their own orders. Staff can see every order.

=== "Base URL"

    ```
    /api/orders/orders/
    ```

=== "Authentication"

    You need to be signed in.

    - A shopper can create orders and read their own.
    - Staff can read and manage every order.

## Endpoints

=== "List"

    ```
    GET /api/orders/orders/
    ```

    - Users: returns only their orders
    - Staff: returns all orders

    Success (200):

    ```json
    [
      {
        "id": 123,
        "user": 1,
        "status": "PLACED",
        "shipping_address": {
          "id": 10,
          "full_name": "John Doe",
          "phone": "0712345678",
          "email": "john@example.com",
          "address_line_1": "Street 1",
          "address_line_2": "",
          "city": "Nairobi",
          "state": "",
          "postal_code": "",
          "country": "Kenya",
          "created_at": "2026-01-19T10:00:00Z"
        },
        "warehouse": {
          "id": 1,
          "code": "WH-1",
          "name": "Receiving warehouse",
          "phone": "7012033251",
          "address_line_1": "330 Tompkins Ave",
          "address_line_2": "Unit 3623 PMB A3415",
          "city": "Staten Island",
          "state": "NY",
          "postal_code": "10304",
          "country": "USA"
        },
        "subtotal": "40.00",
        "shipping_fee": "0.00",
        "total": "40.00",
        "is_fully_paid": false,
        "notes": "",
        "created_at": "2026-01-19T10:00:00Z",
        "updated_at": "2026-01-19T10:00:00Z",
        "items": [
          {
            "id": 1,
            "product": 1,
            "variant": null,
            "product_name": "Vitamin C 1000mg",
            "variant_description": "",
            "barcode": "",
            "quantity": 2,
            "unit_price": "20.00",
            "line_total": "40.00"
          }
        ],
        "shipment": {
          "id": 55,
          "status": "ORDER_PLACED",
          "carrier": "",
          "tracking_number": "",
          "tracking_url": "",
          "estimated_delivery_at": null,
          "delivered_at": null,
          "created_at": "2026-01-19T10:00:00Z",
          "updated_at": "2026-01-19T10:00:00Z",
          "events": [
            {
              "id": 100,
              "status": "ORDER_PLACED",
              "message": "Order placed",
              "location": "",
              "occurred_at": "2026-01-19T10:00:00Z"
            }
          ]
        },
        "payments": [
          {
            "id": 1,
            "provider": "intasend",
            "status": "pending",
            "amount": "40.00",
            "currency": "KES",
            "checkout_url": "https://pay.intasend.com/...",
            "transaction_id": "pay-8f3a1c",
            "provider_payment_id": "",
            "provider_invoice_id": "",
            "created_at": "2026-01-19T10:00:00Z",
            "updated_at": "2026-01-19T10:00:00Z"
          }
        ],
        "refunds": []
      }
    ]
    ```

    Each order includes a **`payments`** array: payment attempts for that order (non–soft-deleted only), ordered by most recent first. Each payment object has: `id`, `provider`, `status`, `amount`, `currency`, `checkout_url`, `transaction_id`, `provider_payment_id`, `provider_invoice_id`, `created_at`, `updated_at`. `transaction_id` may be `null`. Staff may send one when they record a payment. A non-empty id must be unique.

    Each order also includes a **`refunds`** array. Staff add one when they refund a cancelled order, and when they remove a paid line or replace it with a cheaper product. See `api/payments.md`.

## Notes

- `is_fully_paid` is `true` when the money still held on the order, converted to the primary currency, is at least `total`. The field is derived. A covered bill sets `PROCESSING` while the parcel has not left. `SHIPPING` and `COMPLETE` follow the parcel. If the bill stops being covered during `PROCESSING`, the order returns to `PAYMENT_PENDING`.
- Payments in `completed` or `refund_initiated` count in full. Each refund in `completed` is subtracted. An `initiated` refund still counts as held. Conversion uses the `usd_rate` stored on the payment.
- When completed refunds cover a payment, its status becomes `refunded`. A smaller completed refund leaves the payment `completed` and subtracts only that amount.
- When an order is moved to `CANCELLED`, pending payments for that order are marked `cancelled`.
- Payments and refunds are managed in the Payments doc: `api/payments.md`

=== "Retrieve"

    ```
    GET /api/orders/orders/{id}/
    ```

    Response includes:
    - `items[]`
    - `shipping_address` — the customer's delivery address
    - `warehouse` — the receiving warehouse this order is shipped to, or `null` when none is active.
    - `shipment` (with `events[]`)
    - `payments[]` — payment attempts for this order (same shape as in list; soft-deleted payments excluded)
    - `refunds[]` — refund records for this order

=== "Cancel Order"

    ```
    PATCH /api/orders/orders/{id}/
    ```

    Request body:

    ```json
    {
      "status": "CANCELLED"
    }
    ```

    Cancellation rules:
    - User: can cancel **only their own unpaid order**
    - Staff: can cancel **any order**
    - Non-staff cannot update other order fields through this endpoint

    Success (200):

    ```json
    {
      "id": 123,
      "user": 1,
      "status": "CANCELLED",
      "shipping_address": {
        "id": 10,
        "full_name": "John Doe",
        "phone": "0712345678",
        "email": "john@example.com",
        "address_line_1": "Street 1",
        "address_line_2": "",
        "city": "Nairobi",
        "state": "",
        "postal_code": "",
        "country": "Kenya",
        "created_at": "2026-01-19T10:00:00Z"
      },
      "warehouse": {
        "id": 1,
        "code": "WH-1",
        "name": "Receiving warehouse",
        "phone": "7012033251",
        "address_line_1": "330 Tompkins Ave",
        "address_line_2": "Unit 3623 PMB A3415",
        "city": "Staten Island",
        "state": "NY",
        "postal_code": "10304",
        "country": "USA"
      },
      "subtotal": "40.00",
      "shipping_fee": "0.00",
      "total": "40.00",
      "is_fully_paid": false,
      "notes": "",
      "created_at": "2026-01-19T10:00:00Z",
      "updated_at": "2026-01-19T10:15:00Z",
      "items": [],
      "shipment": null,
      "payments": [
        {
          "id": 1,
          "provider": "intasend",
          "status": "cancelled",
          "amount": "40.00",
          "currency": "KES",
          "checkout_url": "https://pay.intasend.com/...",
          "transaction_id": "pay-8f3a1c",
          "provider_payment_id": "",
          "provider_invoice_id": "",
          "created_at": "2026-01-19T10:00:00Z",
          "updated_at": "2026-01-19T10:15:00Z"
        }
      ],
      "refunds": []
    }
    ```

    Common errors:
    - `400 Bad Request`: user tries to cancel an order that is already fully paid
    - `403 Forbidden`: non-staff tries to update fields other than `status`, or attempts forbidden order updates

=== "Create (authenticated)"

    ```
    POST /api/orders/orders/
    ```

    ```json
    {
      "shipping_address": {
        "full_name": "John Doe",
        "phone": "0712345678",
        "email": "john@example.com",
        "address_line_1": "Street 1",
        "address_line_2": "",
        "city": "Nairobi",
        "state": "",
        "postal_code": "",
        "country": "Kenya"
      },
      "items": [
        { "product": 1, "quantity": 2 },
        { "variant": 10, "quantity": 1 }
      ],
      "shipping_fee": "0.00",
      "notes": ""
    }
    ```

    Notes:
    - `shipping_fee` on this request is ignored. Checkout sets it from the shipping table: the country's fee for one unit of weight, or that fee times weight divided by the unit weight when the basket is heavier. See `api/shipping-rates.md`.
    - Order creation reduces stock only when that product or variant has `track_stock` on. A variant line never changes the product's stock. A product or variant with `track_stock` off can be ordered without a stock check.
    - A shipment is created automatically with an initial event: **Order placed**.
    - On successful create, that customer’s **server-side cart is cleared** (see `api/cart.md`).
    - `warehouse` is the active receiving warehouse at checkout, or `null` when none is active. It is not the customer’s `shipping_address`.
    - A shopper’s order is always their own. Sending another person’s `user` id returns 400.
    - Staff can place the order for a customer by sending that customer’s `user` id. The order, shipping address, and cleared cart belong to the customer. Omit `user` and the order is for the staff user.

    Staff placing an order for customer `42`:

    ```json
    {
      "user": 42,
      "shipping_address": {
        "full_name": "John Doe",
        "phone": "0712345678",
        "email": "john@example.com",
        "address_line_1": "Street 1",
        "address_line_2": "",
        "city": "Nairobi",
        "state": "",
        "postal_code": "",
        "country": "Kenya"
      },
      "items": [
        { "product": 1, "quantity": 2 }
      ],
      "shipping_fee": "0.00",
      "notes": "Placed by phone"
    }
    ```

    Success (201):

    ```json
    {
      "id": 123,
      "user": 1,
      "status": "PLACED",
      "shipping_address": {
        "id": 10,
        "full_name": "John Doe",
        "phone": "0712345678",
        "email": "john@example.com",
        "address_line_1": "Street 1",
        "address_line_2": "",
        "city": "Nairobi",
        "state": "",
        "postal_code": "",
        "country": "Kenya",
        "created_at": "2026-01-19T10:00:00Z"
      },
      "warehouse": {
        "id": 1,
        "code": "WH-1",
        "name": "Receiving warehouse",
        "phone": "7012033251",
        "address_line_1": "330 Tompkins Ave",
        "address_line_2": "Unit 3623 PMB A3415",
        "city": "Staten Island",
        "state": "NY",
        "postal_code": "10304",
        "country": "USA"
      },
      "subtotal": "40.00",
      "shipping_fee": "0.00",
      "total": "40.00",
      "is_fully_paid": false,
      "notes": "",
      "created_at": "2026-01-19T10:00:00Z",
      "updated_at": "2026-01-19T10:00:00Z",
      "items": [
        {
          "id": 1,
          "product": 1,
          "variant": null,
          "product_name": "Vitamin C 1000mg",
          "variant_description": "",
          "barcode": "",
          "quantity": 2,
          "unit_price": "20.00",
          "line_total": "40.00"
        }
      ],
      "shipment": {
        "id": 55,
        "status": "ORDER_PLACED",
        "carrier": "",
        "tracking_number": "",
        "tracking_url": "",
        "estimated_delivery_at": null,
        "delivered_at": null,
        "created_at": "2026-01-19T10:00:00Z",
        "updated_at": "2026-01-19T10:00:00Z",
        "events": [
          {
            "id": 100,
            "status": "ORDER_PLACED",
            "message": "Order placed",
            "location": "",
            "occurred_at": "2026-01-19T10:00:00Z"
          }
        ]
      },
      "payments": [],
      "refunds": []
    }
    ```

    The created order includes `payments` (empty until payment attempts are created via the payments API) and `refunds` (empty until staff record a refund).

=== "Confirm, unavailable, or replace a line (staff)"

    ```
    POST /api/orders/orders/{id}/items/{item_id}/confirm/
    POST /api/orders/orders/{id}/items/{item_id}/unavailable/
    POST /api/orders/orders/{id}/items/{item_id}/remove/
    POST /api/orders/orders/{id}/items/{item_id}/replace/
    ```

    Staff only, and only while the order is `PAYMENT_PENDING`, `PLACED`, or `PROCESSING`.

    A new line is `pending`. Every line must be `confirmed`, `unavailable`, or `replaced` before the order can move to `SHIPPING` or `COMPLETE`, and at least one line must be `confirmed`.

    Confirm marks the line as what will ship. Optional body: `{ "note": "Packed" }`. The note is `availability_note` on the line, and the customer can read it.

    Unavailable keeps the line on the order, sets `availability` to `unavailable`, and leaves it out of `subtotal` and `total`. Its `line_total` stays so the customer can see what was dropped. Stock goes back, and the product no longer counts as sold. `POST .../remove/` does the same thing. Optional body: `{ "note": "Supplier is out" }`.

    Replace keeps the original line as `replaced` and adds a new `confirmed` line for the other product or variant. The new line's `replaces` is the original line id. The original line's `replacement` is the new line id. Stock goes back on the old product and is taken from the replacement.

    ```json
    { "product": 88 }
    ```

    ```json
    { "variant": 14, "quantity": 1 }
    ```

    The order `subtotal` and `total` are recalculated from `pending` and `confirmed` lines only. Success is **200** and the body is the full order, including every line, `payments`, and `refunds`.

    When the new total is lower and the customer has a `completed` payment, the order includes an `initiated` refund for the difference. Its `reason` is `Marked {product name} unavailable` or `Replaced {old name} with {new name}`. The payment status becomes `refund_initiated`. Mark that refund `completed` in the Payments doc when the money has been returned. The order status stays as it was.

    A more expensive replacement raises `total`. `is_fully_paid` becomes `false` when the payments no longer cover it. No refund is created.

    `quantity` on replace defaults to the line's current quantity. Send `product` or `variant`, one of them.

    Errors:

    | Status | When |
    | --- | --- |
    | 403 | The caller is not staff |
    | 404 | That line is not on this order |
    | 400 | The order is `SHIPPING`, `COMPLETE`, `CANCELLED`, or `REFUNDED` |
    | 400 | Confirm or replace is used on a line that is already `unavailable` or `replaced` |
    | 400 | The replacement does not have enough stock |
    | 400 | Replace sends both `product` and `variant`, or neither |

    Example after marking a 20.00 line unavailable on a paid 40.00 order:

    ```json
    {
      "id": 123,
      "status": "PROCESSING",
      "subtotal": "20.00",
      "shipping_fee": "0.00",
      "total": "20.00",
      "is_fully_paid": true,
      "items": [
        {
          "id": 1,
          "product": 9,
          "variant": null,
          "product_name": "Vitamin C 1000mg",
          "quantity": 1,
          "unit_price": "20.00",
          "line_total": "20.00",
          "availability": "unavailable",
          "availability_note": "Supplier is out",
          "replaces": null,
          "replacement": null
        },
        {
          "id": 2,
          "product": 8,
          "variant": null,
          "product_name": "Vitamin D3",
          "quantity": 1,
          "unit_price": "20.00",
          "line_total": "20.00",
          "availability": "pending",
          "availability_note": "",
          "replaces": null,
          "replacement": null
        }
      ],
      "payments": [
        {
          "id": 1,
          "status": "refund_initiated",
          "amount": "40.00",
          "currency": "KES"
        }
      ],
      "refunds": [
        {
          "id": 3,
          "order": 123,
          "payment": 1,
          "status": "initiated",
          "amount": "20.00",
          "currency": "KES",
          "reason": "Marked Vitamin C 1000mg unavailable",
          "transaction_id": "rf-3f1c0a9b",
          "completed_at": null
        }
      ]
    }
    ```

=== "Order status"

    Read `status` on the order. These are the values clients should handle:

    | Status | When it is set |
    | --- | --- |
    | `PAYMENT_PENDING` | The order was just created |
    | `PLACED` | Legacy value. Treat a paid order in this status like `PROCESSING` |
    | `PROCESSING` | Completed payments cover `total` |
    | `SHIPPING` | Staff record the parcel as `DISPATCHED` or `OUT_FOR_DELIVERY`, after every line is confirmed, unavailable, or replaced |
    | `COMPLETE` | Staff record the parcel as `DELIVERED`, with the same line check when the order was not already shipping |
    | `CANCELLED` | The shopper cancelled an unpaid order, or staff cancelled it |
    | `REFUNDED` | Every received payment on a cancelled order has been refunded in full |

    `SHIPPING` and `COMPLETE` follow the shipment. Adding a timeline event is enough: see `api/shipments.md`. Setting the shipment status directly does the same. Either call returns **400** while a line is still `pending`, or when every line was marked unavailable. The message names the products still waiting.

    Each line includes `availability` (`pending`, `confirmed`, `unavailable`, `replaced`), `availability_note`, `replaces`, and `replacement`. Unavailable and replaced lines stay in `items` and are left out of the total.

    `REFUNDED` follows the refund records. Staff can also `PATCH` the order with `{ "status": "REFUNDED" }`. That writes a completed refund for any balance still held and marks those payments `refunded`.

## Related docs

- Cart: `api/cart.md`
- Shipping rates: `api/shipping-rates.md`
- Warehouses: `api/warehouses.md`
- Payments: `api/payments.md`
- Shipments: `api/shipments.md`
