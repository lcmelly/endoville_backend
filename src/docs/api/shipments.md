# Shipments

Track shipping progress for orders.

## Base URLs

- User shipments: `/api/orders/shipments/`
- Staff shipments: `/api/orders/staff/shipments/`
- Staff shipment events: `/api/orders/staff/shipment-events/`

## Authentication

- All endpoints require authentication.
- Staff endpoints additionally require `is_staff=true`.

## Shipping Status Steps

- `ORDER_PLACED`
- `DISPATCHED`
- `OUT_FOR_DELIVERY`
- `DELIVERED`

Users see a timeline via `events[]` on the shipment response.

## User Endpoints

=== "List"

    ```
    GET /api/orders/shipments/
    ```

    Success (200):

    ```json
    [
      {
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
      }
    ]
    ```

=== "Retrieve"

    ```
    GET /api/orders/shipments/{id}/
    ```

## Staff Endpoints

=== "Update shipment (staff)"

    ```
    PATCH /api/orders/staff/shipments/{id}/
    ```

    Request body:

    ```json
    {
      "status": "DISPATCHED",
      "carrier": "DHL",
      "tracking_number": "TRK-123",
      "tracking_url": "https://carrier.example.com/track/TRK-123",
      "estimated_delivery_at": "2026-01-25T10:00:00Z"
    }
    ```

=== "Add shipment event (staff)"

    ```
    POST /api/orders/staff/shipment-events/
    ```

    Request body:

    ```json
    {
      "shipment": 55,
      "status": "DISPATCHED",
      "message": "Dispatched from warehouse",
      "location": "Nairobi",
      "occurred_at": "2026-01-19T12:00:00Z"
    }
    ```

Notes:
- Staff should update `Shipment.status` **and** add a matching `ShipmentEvent` so users see the timeline update.
- When the shipment is delivered, set `status=DELIVERED` and set `delivered_at`.
