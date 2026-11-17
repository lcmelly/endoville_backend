---
title: Messages
icon: lucide/message-square
---

# Messages

A shopper can send a message without signing in. It can be a question, a note about an order, or anything else they need to tell the shop. The text is stored as plain text, at most 500 characters. HTML tags and control characters are removed before it is saved.

Send an email address or a phone number. A phone number is 8 to 15 digits and may start with `+`. Send `captcha_token` from the Cloudflare Turnstile widget. The storefront reads `CUSTOMER_MESSAGE_CAPTCHA_SITE_KEY` and renders Turnstile in every environment, including local development. The server checks the token with Turnstile before it saves the message.

`order_number` is optional. When you send one, it must be the order `id` from the orders API. A counter such as `1` or `2` is not accepted.

One IP address can send 5 messages an hour. One email address or phone number can send 3 a day.

=== "Base URL"

    ```
    /api/orders/messages/
    ```

=== "Authentication"

    | What you want to do | Who can do it |
    |---|---|
    | Read the form limits | Anyone |
    | Send a message | Anyone |
    | List messages | Staff |

## Endpoints

=== "Read"

    ```
    GET /api/orders/messages/
    ```

    Success (200):

    ```json
    {
      "message_max_length": 500,
      "captcha_required": true
    }
    ```

    Set `CUSTOMER_MESSAGE_CAPTCHA_SECRET` from the Turnstile widget. Put `CUSTOMER_MESSAGE_CAPTCHA_SITE_KEY` in the storefront environment. Without the secret, sending a message is refused.

=== "Create"

    ```
    POST /api/orders/messages/
    ```

    ```json
    {
      "email": "amina@example.com",
      "phone": "",
      "message": "The bottle arrived open.",
      "order_number": "k3nR8wQp0sL2aB9x",
      "captcha_token": "turnstile-token"
    }
    ```

    `email` or `phone` is required. `order_number` may be omitted.

    Success (201):

    ```json
    {
      "id": 4,
      "email": "amina@example.com",
      "phone": "",
      "message": "The bottle arrived open.",
      "order_number": "k3nR8wQp0sL2aB9x",
      "created_at": "2026-11-17T00:30:00Z"
    }
    ```

    `400` when the contact, message, order number, or captcha token is not valid. `429` when this IP has already sent 5 messages in the last hour.

=== "List"

    ```
    GET /api/orders/staff/messages/
    ```

    Staff only. Same fields as the create response, newest first.
