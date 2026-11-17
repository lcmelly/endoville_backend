---
title: Password reset
icon: lucide/key-round
---

# Password reset

Ask for a reset link, then set a new password from that link. The link is emailed only when the address belongs to an active account, and it is sent to that account's own email. An unknown address gets the same response and no email.

The link expires after one hour and works once. Signing in is still a separate call.

=== "Request a link"

    ```
    POST /api/users/password-reset/
    ```

    You do not need to be signed in.

    ```json
    {
      "email": "user@example.com"
    }
    ```

    Success (200), whether or not an account exists:

    ```json
    {
      "message": "If an account exists for that email, a reset link has been sent."
    }
    ```

    The link looks like `https://endovillehealth.com/reset-password?uid=...&token=...`. The storefront origin comes from `FRONTEND_URL`.

=== "Set a new password"

    ```
    POST /api/users/password-reset/confirm/
    ```

    ```json
    {
      "uid": "MQ",
      "token": "reset-token",
      "password": "fresh-pass-4821"
    }
    ```

    Success (200):

    ```json
    {
      "message": "Password updated. You can sign in with your new password."
    }
    ```

    A used, expired, or mismatched link returns 400:

    ```json
    {
      "token": ["This reset link is invalid or has expired."]
    }
    ```

## Notes

- One IP address can call these endpoints 5 times an hour.
- The password must be at least 8 characters and pass the normal password checks.
- Leave `ZEPTOMAIL_PASSWORD_RESET_TEMPLATE_KEY` empty to send a plain HTML email. When it is set, the template receives `name` and `reset_url`.
