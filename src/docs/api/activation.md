# Account Activation

Activate a user account using the OTP received via email.

=== "Endpoint"

    ```
    POST /api/users/activate/
    ```

=== "Authentication"

    No authentication required.

=== "Request Body"

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
    | `otp` | string | Yes | 6-digit OTP code received via email |

## Response

=== "Success (200 OK)"

    ```json
    {
      "message": "Account activated successfully.",
      "user": {
        "id": 1,
        "email": "user@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "is_active": true,
        "is_staff": false
      }
    }
    ```

=== "Error (400 Bad Request)"

    ```json
    {
      "non_field_errors": ["Invalid OTP or OTP has expired."]
    }
    ```

## Error Cases

- **Invalid OTP**: The OTP code is incorrect
- **Expired OTP**: The OTP has expired (valid for 5 minutes)
- **Already Activated**: The account is already active
- **User Not Found**: No user exists with the provided email

## Notes

- OTPs expire after 5 minutes
- OTPs can only be used once
- After activation, the user can log in
- If the OTP expires, use the resend OTP endpoint to get a new one

## Example Request

```bash
curl -X POST https://api.endovillehealth.com/api/users/activate/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "otp": "123456"
  }'
```
