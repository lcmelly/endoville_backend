# Payments

Create and track payments for orders.

## Overview

- **User payments**: create a payment for your own order and view payment status/links.
- **Staff payments**: can view and manually update any payment.
- **Payment credentials**: managed via staff API (no admin UI required).
 - Orders are considered **fully paid** when the sum of **completed** payments is **>= the order total**.
   If a completed payment is deleted (or changed), the flag is recalculated automatically.

## Fully Paid Rules

- Only payments with `status="completed"` and `is_deleted=false` count toward the order total.
- If an order is already fully paid, creating a new payment will return an error (both user and staff endpoints).

## Providers

- **IntaSend** (`intasend`): payment link or STK push.
- **Stripe** (`stripe`): Checkout session; redirect URLs and webhook for completion.
- **Cash / Other** (`cash`, `other`): manual (staff confirms).

Both IntaSend and Stripe can be used alongside each other; create a payment with the desired `provider` and `method`.

## Base URLs

- User payments: `/api/orders/payments/`
- Staff credentials: `/api/orders/payment-credentials/`
- Staff manage payments: `/api/orders/staff/payments/`

## Authentication

- All endpoints require authentication.
- Staff endpoints additionally require `is_staff=true`.

## Payment Credentials (Staff API)

Payment provider credentials are **global for the whole app** (not per user) and are stored in `orders.PaymentCredentials`.

=== "Create credentials (staff)"

    ```
    POST /api/orders/payment-credentials/
    ```

    Request body:

    ```json
    {
      "provider": "intasend",
      "environment": "sandbox",
      "api_key": "YOUR_PUBLISHABLE_KEY",
      "private_key": "YOUR_SECRET_OR_PRIVATE_KEY",
      "is_active": true
    }
    ```

    Notes:
    - `private_key` is **write-only** (never returned).
    - Response includes `has_private_key: true/false`.
    - Only one credentials row can be active per `(provider, environment)`.
    - For **Stripe**, use `provider: "stripe"` and store the Stripe **secret key** as `private_key`. Set `STRIPE_WEBHOOK_SECRET` in the environment for the webhook.

=== "List credentials (staff)"

    ```
    GET /api/orders/payment-credentials/
    ```

=== "Update credentials (staff)"

    ```
    PATCH /api/orders/payment-credentials/{id}/
    ```

    Example rotate secret key:

    ```json
    {
      "private_key": "NEW_SECRET_KEY"
    }
    ```

## User Payment Endpoints

=== "List"

    ```
    GET /api/orders/payments/
    ```

    Success (200):

    ```json
    [
      {
        "id": 500,
        "order": 123,
        "provider": "intasend",
        "status": "pending",
        "amount": "40.00",
        "currency": "KES",
        "checkout_url": "https://payment.example.com/xyz",
        "provider_payment_id": "",
        "provider_invoice_id": "INV-123",
        "provider_state": "PENDING",
        "raw_provider_response": {},
        "created_at": "2026-01-19T10:05:00Z",
        "updated_at": "2026-01-19T10:05:00Z"
      }
    ]
    ```

=== "Retrieve"

    ```
    GET /api/orders/payments/{id}/
    ```

=== "Create (owner-only)"

    ```
    POST /api/orders/payments/
    ```

    Error (400) if order is fully paid:

    ```json
    {
      "detail": "Order is already fully paid."
    }
    ```

    Request body (hosted link, IntaSend):

    ```json
    {
      "order": 123,
      "provider": "intasend",
      "method": "link"
    }
    ```

    Request body (STK push, IntaSend):

    ```json
    {
      "order": 123,
      "provider": "intasend",
      "method": "stk",
      "phone_number": "0712345678",
      "email": "john@example.com"
    }
    ```

    Request body (Stripe Checkout):

    ```json
    {
      "order": 123,
      "provider": "stripe",
      "method": "checkout"
    }
    ```

    Optional for Stripe: `success_url`, `cancel_url` (override defaults from settings).

    ```json
    {
      "order": 123,
      "provider": "stripe",
      "method": "checkout",
      "success_url": "https://yoursite.com/order/success/",
      "cancel_url": "https://yoursite.com/order/cancel/"
    }
    ```

    Request body (Cash / Other manual):

    ```json
    {
      "order": 123,
      "provider": "cash",
      "method": "manual"
    }
    ```

    Other manual example:

    ```json
    {
      "order": 123,
      "provider": "other",
      "method": "manual"
    }
    ```

    Success (201):

    ```json
    {
      "id": 500,
      "order": 123,
      "provider": "intasend",
      "status": "pending",
      "amount": "40.00",
      "currency": "KES",
      "checkout_url": "https://payment.example.com/xyz",
      "provider_payment_id": "",
      "provider_invoice_id": "INV-123",
      "provider_state": "PENDING",
      "raw_provider_response": {},
      "created_at": "2026-01-19T10:05:00Z",
      "updated_at": "2026-01-19T10:05:00Z"
    }
    ```

## Staff Payment Management Endpoints

=== "List payments (staff)"

    ```
    GET /api/orders/staff/payments/
    ```

=== "Create payment (staff)"

    ```
    POST /api/orders/staff/payments/
    ```

    Example (record cash payment as completed):

    ```json
    {
      "order": 123,
      "provider": "cash",
      "status": "completed",
      "amount": "40.00",
      "currency": "KES"
    }
    ```

    Error (400) if order is fully paid:

    ```json
    {
      "detail": "Order is already fully paid."
    }
    ```

=== "Update payment status (staff)"

    ```
    PATCH /api/orders/staff/payments/{id}/
    ```

    Example:

    ```json
    {
      "status": "completed",
      "provider_state": "PAID",
      "amount": "40.00"
    }
    ```

## Stripe webhook

To mark Stripe Checkout payments as **completed** when the customer pays, configure a webhook in the Stripe Dashboard and set `STRIPE_WEBHOOK_SECRET` in your environment.

- **URL**: `POST /api/orders/payments/stripe/webhook/`
- **Event**: `checkout.session.completed`
- **Settings** (e.g. in `.env`):
  - `STRIPE_WEBHOOK_SECRET` — signing secret from Stripe (Dashboard → Developers → Webhooks).
  - `STRIPE_SUCCESS_URL` — default redirect after successful payment (optional).
  - `STRIPE_CANCEL_URL` — default redirect when user cancels (optional).

Stripe credentials (secret key) are stored per environment via the staff **Payment credentials** API (`provider=stripe`). The webhook secret is app-wide and not stored in the database.

=== "Delete payment (staff, soft delete)"

    ```
    DELETE /api/orders/staff/payments/{id}/
    ```

    Notes:
    - This is a **soft delete** (the record remains in the database).
    - The payment is marked `is_deleted=true`, and `deleted_by` / `deleted_at` are recorded.
    - Deleted payments are excluded from normal user/staff lists unless `include_deleted=true`.
    - Order `is_fully_paid` is recalculated after the delete.

=== "List including deleted (staff)"

    ```
    GET /api/orders/staff/payments/?include_deleted=true
    ```
