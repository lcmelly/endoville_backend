# Orders

Place and view orders.

=== "Base URL"

    ```
    /api/orders/orders/
    ```

=== "Authentication"

    JWT required.

    - Users can create and view **their own** orders.
    - Staff can view/manage all orders.

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
            "provider_payment_id": "",
            "provider_invoice_id": "",
            "created_at": "2026-01-19T10:00:00Z",
            "updated_at": "2026-01-19T10:00:00Z"
          }
        ]
      }
    ]
    ```

    Each order includes a **`payments`** array: payment attempts for that order (non–soft-deleted only), ordered by most recent first. Each payment object has: `id`, `provider`, `status`, `amount`, `currency`, `checkout_url`, `provider_payment_id`, `provider_invoice_id`, `created_at`, `updated_at`.

## Notes

- `is_fully_paid` becomes `true` when the sum of payments with `status="completed"` is **>=** the order `total`.
- If a completed payment is updated or deleted, `is_fully_paid` is recalculated automatically.
- When an order is moved to `CANCELLED`, pending payments for that order are automatically marked as `cancelled`.
- Payments are managed in the Payments doc: `api/payments.md`

=== "Retrieve"

    ```
    GET /api/orders/orders/{id}/
    ```

    Response includes:
    - `items[]`
    - `shipping_address`
    - `shipment` (with `events[]`)
    - `payments[]` — payment attempts for this order (same shape as in list; soft-deleted payments excluded)

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
          "provider_payment_id": "",
          "provider_invoice_id": "",
          "created_at": "2026-01-19T10:00:00Z",
          "updated_at": "2026-01-19T10:15:00Z"
        }
      ]
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
    - Order creation reduces product/variant stock.
    - A shipment is created automatically with an initial event: **Order placed**.
    - On successful create, the authenticated user’s **server-side cart is cleared** (see `api/cart.md`).

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
      "payments": []
    }
    ```

    The created order includes `payments` (empty until payment attempts are created via the payments API).

## Related docs

- Cart: `api/cart.md`
- Payments: `api/payments.md`
- Shipments: `api/shipments.md`
