---
title: Staff users
icon: lucide/user-round-cog
---

# Staff users

An admin adds a staff user and ticks the roles that person should have. A role is a Django group. An admin (`is_superuser`) has every role without being added to the groups.

| Role | Allows |
|---|---|
| `Orders` | All orders, line confirm / remove / replace, payments, refunds, and payment credentials. Placing an order for a customer. |
| `Shipping` | Shipments and shipment events. Reading every order and shipment. |
| `Stock` | Creating and editing products and variants, including stock. |
| `Manager` | Creating and updating a warehouse address. |

A staff user can hold more than one role. Shoppers are not listed here.

## Who can call these

A Django admin. Other staff receive `403`.

## Endpoints

=== "List"

    ```
    GET /api/users/staff/
    ```

    **Example: 200 OK**

    ```json
    [
      {
        "id": 4,
        "email": "ship@example.com",
        "phone": null,
        "first_name": "Sam",
        "last_name": "",
        "is_active": true,
        "is_staff": true,
        "is_superuser": false,
        "roles": ["Shipping"]
      }
    ]
    ```

=== "Add"

    ```
    POST /api/users/staff/
    ```

    `email`, `password`, and `roles` are required. `roles` needs at least one of `Orders`, `Shipping`, `Stock`, and `Manager`. `first_name`, `last_name`, and `phone` are optional.

    ```json
    {
      "email": "ship@example.com",
      "password": "strongpass",
      "first_name": "Sam",
      "roles": ["Shipping", "Stock"]
    }
    ```

    **Example: 201 Created** — The new staff user, with `roles` limited to the ticks in the request.

    **Example: 400 Bad Request**

    ```json
    {
      "roles": ["Choose at least one role."]
    }
    ```

=== "Read and update"

    ```
    GET /api/users/staff/{id}/
    PATCH /api/users/staff/{id}/
    ```

    `PATCH` replaces the role ticks when `roles` is sent. `password` sets a new password. `is_active` can turn the account off. Email stays as it is.

    ```json
    {
      "roles": ["Shipping"],
      "is_active": true
    }
    ```

    **Example: 200 OK** — The staff user after the change.

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```
