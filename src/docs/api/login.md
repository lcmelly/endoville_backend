# Authentication

Login with **email** and **either** a **password** or a **code** (OTP)—not both. Returns JWT tokens.

=== "Endpoint"

    ```
    POST /api/users/login/
    ```

=== "Authentication"

    No authentication required (to get tokens).

=== "Option A: Password login"

    ```json
    {
      "email": "user@example.com",
      "password": "securepassword123"
    }
    ```

=== "Option B: Code (OTP) login"

    ```json
    {
      "email": "user@example.com",
      "otp": "123456"
    }
    ```

=== "Fields"

    | Field | Type | Required | Description |
    |-------|------|----------|-------------|
    | `email` | string | Yes | User's email address |
    | `password` | string | One of these | User's password (use with Option A only) |
    | `otp` | string | One of these | 6-digit code from email/SMS (use with Option B only) |

    You must provide **exactly one** of `password` or `otp`. Do not send both; do not omit both.

## Response

=== "Success (200 OK)"

    ```json
    {
      "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
      "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
      "user": {
        "id": 1,
        "email": "user@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "image_url": "https://cdn.example.com/u/1.png",
        "image_ref": "u/1.png",
        "is_active": true
      }
    }
    ```

=== "Error (400 Bad Request)"

    Both password and code provided:

    ```json
    {
      "non_field_errors": ["Use either password or code to login, not both."]
    }
    ```

    Neither password nor code provided:

    ```json
    {
      "non_field_errors": ["Provide either password or code to login."]
    }
    ```

    Invalid credentials (password login):

    ```json
    {
      "email": ["Invalid email or password."]
    }
    ```
    or
    ```json
    {
      "password": ["Invalid email or password."]
    }
    ```

    Invalid or missing OTP (code login):

    ```json
    {
      "otp": ["No valid OTP found. Please request a new one."]
    }
    ```
    or
    ```json
    {
      "otp": ["OTP verification failed. OTP has expired."]
    }
    ```

## Error Cases

- **Both / neither**: Sending both `password` and `otp`, or neither.
- **Invalid credentials**: Wrong email or password (password login).
- **Inactive account**: Account is not activated.
- **Invalid OTP**: Code incorrect, expired, or already used (code login).
- **No OTP**: No valid OTP found for the email (request a new one).

## JWT Tokens

### Access Token

- **Lifetime**: 3 hours
- **Usage**: Include in `Authorization` header for authenticated requests
- **Format**: `Bearer <access_token>`

### Refresh Token

- **Lifetime**: 7 days
- **Usage**: Use to get a new access token when it expires
- **Endpoint**: `/api/token/refresh/` (if implemented)

## Using the Access Token

Include the access token in the `Authorization` header:

```bash
curl -X GET https://api.endovillehealth.com/api/users/profile/ \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

## Notes

- Use **either** password **or** code to login, not both.
- The account must be activated (`is_active=True`).
- For code login: OTP is single-use, expires after 5 minutes, and has a maximum of 3 verification attempts.
- Store the access token securely (e.g., in localStorage or secure cookies).
- Use the refresh token to obtain a new access token before it expires.

## Example Requests

Password login:

```bash
curl -X POST https://api.endovillehealth.com/api/users/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepassword123"}'
```

Code (OTP) login:

```bash
curl -X POST https://api.endovillehealth.com/api/users/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "otp": "123456"}'
```
