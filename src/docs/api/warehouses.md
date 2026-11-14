---
title: Warehouses
icon: lucide/warehouse
---

# Warehouses

This is the address a placed order is sent to before it goes out to the customer. It is not the customer's delivery address.

Nothing is filled in for you. Until a manager or an admin adds a warehouse, new orders come back with `warehouse` set to `null`.

A new warehouse becomes the active one, and the previous active warehouse is switched off. Checkout attaches that active address to the order. Orders that were already placed keep the address they were given at the time.

=== "Base URL"

    ```
    /api/orders/staff/warehouses/
    ```

=== "Authentication"

    You need to be signed in.

    | What you want to do | Who can do it |
    |---|---|
    | Read the list or one warehouse | Staff |
    | Add or change an address | A person in the `Manager` group, or a Django admin (`is_superuser`) |

    Staff who are not managers can read the address and cannot change it. A shopper gets `403`. Add someone to the `Manager` group in Django admin, under Groups.

## Endpoints

=== "List"

    ```
    GET /api/orders/staff/warehouses/
    ```

    Success (200):

    ```json
    [
      {
        "id": 1,
        "code": "WH-1",
        "name": "Receiving warehouse",
        "phone": "7012033251",
        "address_line_1": "330 Tompkins Ave",
        "address_line_2": "Unit 3623 PMB A3415",
        "city": "Staten Island",
        "state": "NY",
        "postal_code": "10304",
        "country": "USA",
        "is_active": true
      }
    ]
    ```

    An empty list means no warehouse has been added yet.

=== "Retrieve"

    ```
    GET /api/orders/staff/warehouses/{id}/
    ```

    Same object as one row in the list.

=== "Create"

    ```
    POST /api/orders/staff/warehouses/
    ```

    Managers and admins only.

    ```json
    {
      "code": "WH-1",
      "name": "Receiving warehouse",
      "phone": "7012033251",
      "address_line_1": "330 Tompkins Ave",
      "address_line_2": "Unit 3623 PMB A3415",
      "city": "Staten Island",
      "state": "NY",
      "postal_code": "10304",
      "country": "USA"
    }
    ```

    Success (201) returns the stored warehouse, including `id` and `is_active`.

    Required: `code`, `name`, `address_line_1`, `city`, `state`, `postal_code`, `country`. `phone` and `address_line_2` may be blank. `code` must be unique.

=== "Update"

    ```
    PATCH /api/orders/staff/warehouses/{id}/
    PUT /api/orders/staff/warehouses/{id}/
    ```

    Managers and admins only. `code` and `is_active` cannot be changed through this API. `PUT` sends the full address. `PATCH` sends only the fields that change.

    ```json
    {
      "address_line_1": "100 New Dock St",
      "address_line_2": "Unit 1",
      "city": "Brooklyn",
      "state": "NY",
      "postal_code": "11201",
      "country": "USA"
    }
    ```

    Success (200) returns the updated warehouse.

## Fields

| Field | On create | On update | Notes |
|---|---|---|---|
| `id` | — | — | Read-only |
| `code` | Required | Read-only | Unique, up to 32 characters |
| `name` | Required | Optional | |
| `phone` | Optional | Optional | |
| `address_line_1` | Required | Optional | |
| `address_line_2` | Optional | Optional | |
| `city` | Required | Optional | |
| `state` | Required | Optional | |
| `postal_code` | Required | Optional | |
| `country` | Required | Optional | |
| `is_active` | — | — | Read-only. A new warehouse is active, and any previous active warehouse is deactivated |

The `warehouse` object nested on an order uses the same address fields and omits `is_active`.

## Related docs

- Orders: `api/orders.md`
- Shipments: `api/shipments.md`
