# Staff Check

Check whether the currently authenticated user is a staff user.

=== "Endpoint"

    ```
    GET /api/users/is-staff/
    ```

=== "Authentication"

    JWT required.

## Response

=== "Success (200 OK)"

    ```json
    {
      "is_staff": true
    }
    ```

=== "Error (401 Unauthorized)"

    ```json
    {
      "detail": "Authentication credentials were not provided."
    }
    ```
