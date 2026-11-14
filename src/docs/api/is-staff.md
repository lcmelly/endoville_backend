---
title: Staff check
icon: lucide/id-card
---

# Staff check

Ask whether the signed-in person is a staff member. Use this when the app needs to show staff tools.

=== "Endpoint"

    ```
    GET /api/users/is-staff/
    ```

=== "Authentication"

    You need to be signed in.

## Response

=== "Success (200 OK)"

    ```json
    {
      "is_staff": true,
      "is_superuser": false,
      "roles": ["Orders", "Shipping", "Stock"]
    }
    ```

    `roles` is empty for a shopper. An admin (`is_superuser: true`) receives every role: `Orders`, `Shipping`, `Stock`, and `Manager`. A staff user receives only the roles an admin ticked. `Manager` is absent until it is ticked.

=== "Error (401 Unauthorized)"

    ```json
    {
      "detail": "Authentication credentials were not provided."
    }
    ```
