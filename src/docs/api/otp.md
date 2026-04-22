# OTP Management

Resend OTP for **account activation** (inactive accounts) via `POST /api/users/send-otp/`. For **login code** emails (active users), see [Request login OTP](login.md) (`POST /api/users/request-login-otp/`).

ZeptoMail template keys (see `.env.example`):

- **Register** (`POST /api/users/register/`) uses the same key as activation resend: **`ZEPTOMAIL_OTP_TEMPLATE_KEY`** (`purpose=activation` in the API).
- **Login OTP** uses **`ZEPTOMAIL_OTP_LOGIN_TEMPLATE_KEY`** when set; otherwise it falls back to **`ZEPTOMAIL_OTP_TEMPLATE_KEY`** so a single template still works until you add a second key in `.env`.

=== "Endpoint"

    ```
    POST /api/users/send-otp/
    ```

=== "Authentication"

    No authentication required.

=== "Request Body"

    ```json
    {
      "email": "user@example.com"
    }
    ```

=== "Fields"

    | Field | Type | Required | Description |
    |-------|------|----------|-------------|
    | `email` | string | Yes | User's email address |

## Response

=== "Success (200 OK)"

    ```json
    {
      "message": "OTP has been sent to your email address."
    }
    ```

=== "Error (400 Bad Request)"

    ```json
    {
      "email": ["User with this email does not exist."]
    }
    ```

    ```json
    {
      "non_field_errors": ["Account is already active."]
    }
    ```

## Error Cases

- **User Not Found**: No user exists with the provided email
- **Already Active**: The account is already activated (no need for OTP)
- **Email Required**: The email field is missing

## Notes

- Use this endpoint if you didn't receive the OTP or if it expired
- A new OTP will be generated and sent to the email address
- The previous OTP (if any) will be invalidated
- The new OTP is valid for 5 minutes
- Maximum of 3 attempts per OTP before it's locked

## Example Request

```bash
curl -X POST https://api.endovillehealth.com/api/users/send-otp/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com"
  }'
```
