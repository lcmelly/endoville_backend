---
title: Shipments
icon: lucide/truck
---

# Shipments

This is how a shopper follows a parcel, and how staff record each step.

One order has one shipment. The shopper reads their own. Staff can update the status and add a line to the timeline. A dispatched, out-for-delivery, or delivered update also changes the order `status` the shopper reads on `GET /api/orders/orders/{id}/`.

## Base URLs

- User shipments: `/api/orders/shipments/`
- Staff shipments: `/api/orders/staff/shipments/`
- Staff shipment events: `/api/orders/staff/shipment-events/`

## Who can call these

- Every shipment route needs a signed-in person.
- The staff shipment routes need the `Shipping` role, or an admin. `Orders` can read shipments and cannot change them here.

## What the shopper sees

The status moves through these steps:

- `ORDER_PLACED`, the order exists
- `DISPATCHED`, it has left
- `OUT_FOR_DELIVERY`, it is on the way to the door
- `DELIVERED`, they have it

Those steps come back as `events` on the shipment.

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

## What an update does to the order

Adding an event moves the shipment forward to that event's status, and the order follows.

| Event or shipment `status` | Shipment becomes | Order `status` becomes |
| --- | --- | --- |
| `DISPATCHED` | `DISPATCHED` | `SHIPPING` |
| `OUT_FOR_DELIVERY` | `OUT_FOR_DELIVERY` | `SHIPPING` |
| `DELIVERED` | `DELIVERED` | `COMPLETE` |

`DELIVERED` also sets `delivered_at` from the event's `occurred_at` when `delivered_at` is still empty. `PATCH /api/orders/staff/shipments/{id}/` with the same status values updates the order the same way.

The order stays in `PROCESSING` until staff have decided every line. A `DISPATCHED`, `OUT_FOR_DELIVERY`, or `DELIVERED` update returns **400** while any line is still `pending`, or when the order has lines and none are `confirmed`. The message names the unconfirmed products. Confirm, mark unavailable, or replace those lines first. See `api/orders.md`.

An event does this when it is created, and when staff change an existing event's `status`. An earlier status leaves a shipment that is already further along unchanged. `ORDER_PLACED` does not move the order.

Carrier, tracking number, and tracking URL are still set on the shipment itself. The event is what the shopper sees in `events`, and what moves `status` on the order.
