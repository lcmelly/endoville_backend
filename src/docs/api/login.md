# Authentication

Login with email, password, and OTP to receive JWT tokens.

=== "Endpoint"

    ```
    POST /api/users/login/
    ```

=== "Authentication"

    No authentication required (to get tokens).

=== "Request Body"

    ```json
    {
      "email": "user@example.com",
      "password": "securepassword123",
      "otp": "123456"
    }
    ```

=== "Fields"

    | Field | Type | Required | Description |
    |-------|------|----------|-------------|
    | `email` | string | Yes | User's email address |
    | `password` | string | Yes | User's password |
    | `otp` | string | Yes | 6-digit OTP code for additional security |

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
        "is_active": true
      }
    }
    ```

=== "Error (400 Bad Request)"

    ```json
    {
      "non_field_errors": ["Invalid email or password."]
    }
    ```

    ```json
    {
      "otp": ["Invalid OTP or OTP has expired."]
    }
    ```

## Error Cases

- **Invalid Credentials**: Email or password is incorrect
- **Inactive Account**: Account is not activated
- **Invalid OTP**: OTP code is incorrect or expired
- **Expired OTP**: OTP has expired (valid for 5 minutes)
- **Used OTP**: OTP has already been used

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

- Both email/password and OTP must be valid
- The account must be activated (`is_active=True`)
- OTP is single-use and expires after 5 minutes
- Maximum of 3 OTP verification attempts
- The access token should be stored securely (e.g., in localStorage or secure cookies)
- Use the refresh token to obtain a new access token before it expires

## Example Request

```bash
curl -X POST https://api.endovillehealth.com/api/users/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123",
    "otp": "123456"
  }'
```
