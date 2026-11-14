---
title: OTP
icon: lucide/mail-check
---

# Short codes

Use this when someone needs a new activation code. It works for accounts that are not active yet.

If the person is already active and wants a code to sign in, use [Request a login code](login.md) instead (`POST /api/users/request-login-otp/`).

Which email template is used:

- Registration and a new activation code use `ZEPTOMAIL_OTP_TEMPLATE_KEY`.
- A login code uses `ZEPTOMAIL_OTP_LOGIN_TEMPLATE_KEY` when that is set. If it is not set, we fall back to the activation template, so one template is enough until you add a second key.

=== "Endpoint"

    ```
    POST /api/users/send-otp/
    ```

=== "Authentication"

    You do not need to be signed in.

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
