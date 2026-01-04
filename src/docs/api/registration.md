# User Registration

Register a new user account.

=== "Endpoint"

    ```
    POST /api/users/register/
    ```

=== "Authentication"

    No authentication required.

=== "Request Body"

    ```json
    {
      "email": "user@example.com",
      "first_name": "John",
      "last_name": "Doe",
      "password": "securepassword123"
    }
    ```

=== "Fields"

    | Field | Type | Required | Description |
    |-------|------|----------|-------------|
    | `email` | string | Yes | User's email address (must be unique) |
    | `first_name` | string | Yes | User's first name |
    | `last_name` | string | Yes | User's last name |
    | `password` | string | Yes | User's password (min 8 characters recommended) |

## Response

=== "Success (201 Created)"

    ```json
    {
      "message": "Registration successful. Please check your email for OTP to activate your account.",
      "user": {
        "id": 1,
        "email": "user@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "is_active": false,
        "is_staff": false,
        "created_at": "2026-01-03T12:00:00Z"
      }
    }
    ```

=== "Error (400 Bad Request)"

    ```json
    {
      "email": ["This field is required."],
      "password": ["This field is required."]
    }
    ```

## Notes

- The account will be created with `is_active=False`
- An OTP will be sent to the provided email address
- You must activate the account using the OTP before logging in
- The password is securely hashed before storage

## Example Request

```bash
curl -X POST https://api.endovillehealth.com/api/users/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "password": "securepassword123"
  }'
```
