# Payments

Create and track payments for orders.

=== "Base URLs"

    - User payments: `/api/orders/payments/`
    - Check payment status (refresh from provider): `POST /api/orders/payments/{id}/check-status/`
    - Payment credentials (staff): `/api/orders/payment-credentials/`
    - Staff manage payments: `/api/orders/staff/payments/`
    - IntaSend test connection (staff): `/api/orders/payments/intasend/test/`
    - Stripe webhook: `POST /api/orders/payments/stripe/webhook/`

=== "Authentication"

    JWT required.

    - **Non-staff:** Can create and view **their own** order payments; only **IntaSend** and **Stripe** providers are allowed. Cash/other must be created via staff API.
    - **Staff:** Can create and view all payments and credentials; any provider (IntaSend, Stripe, cash, other) is allowed.

## Providers and methods

| Provider   | Methods        | Notes |
|-----------|----------------|-------|
| **IntaSend** (`intasend`) | `link`, `stk` | Link: hosted checkout URL. STK: M-Pesa push; amount is converted to **KES** using currency rates. |
| **Stripe** (`stripe`)     | `checkout`    | Redirects to Stripe Checkout; webhook marks payment completed. |
| **Cash / Other** (`cash`, `other`) | `manual` | Staff confirms later via staff API. |

- Orders are **fully paid** when the sum of **completed** payments (converted to primary currency) **≥** order total.
- If an order is already fully paid, creating a new payment returns **400** with `"Order is already fully paid."`
- Before creating an IntaSend payment, the API syncs all existing IntaSend payments for that order with the provider and blocks if the order is already fully paid. For **link**, if a pending link already exists, that payment is returned instead of creating a new one.

## Endpoints

=== "List"

    ```
    GET /api/orders/payments/
    ```

    Returns payments for the authenticated user's orders (staff: all). Soft-deleted payments are excluded.

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
        "checkout_url": "https://payment.intasend.com/checkout/...",
        "provider_payment_id": "",
        "provider_invoice_id": "08XPG72",
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

    Returns a single payment (owner or staff). Use this to read the **stored** status; it does not call the provider.

=== "Check status (refresh from provider)"

    ```
    POST /api/orders/payments/{id}/check-status/
    ```

    Returns the payment and a **status_check** object. The third-party API (IntaSend) is **only called when the stored payment status is `pending` or `processing`**. If the payment is already `completed`, `failed`, or `cancelled`, the API returns the stored status without calling IntaSend or Stripe.

    - **Pending/processing + IntaSend:** Calls IntaSend, updates the payment record, and returns the latest status.
    - **Already completed/failed/cancelled:** No provider call; returns current payment and status.
    - **Other providers:** Returns current stored payment and status (no provider call).

    Success (200):

    ```json
    {
      "payment": {
        "id": 500,
        "order": 123,
        "provider": "intasend",
        "status": "completed",
        "amount": "40.00",
        "currency": "KES",
        "checkout_url": "",
        "provider_payment_id": "...",
        "provider_invoice_id": "08XPG72",
        "provider_state": "COMPLETE",
        "raw_provider_response": { ... },
        "created_at": "...",
        "updated_at": "..."
      },
      "status_check": {
        "is_complete": true,
        "status": "completed",
        "provider_state": "COMPLETE",
        "success": true
      }
    }
    ```

    Use **`status_check.is_complete`** (or `status_check.status === "completed"`) to know if the payment is complete. If the provider call failed, `status_check.success` is `false` and `status_check.error` may be set.

=== "Create (owner-only)"

    ```
    POST /api/orders/payments/
    ```

    **Required:** `order` (id), `provider`, `method`. Amount defaults to order total converted to the requested (or default) currency. You must own the order (or be staff).

    **IntaSend — payment link**

    ```json
    {
      "order": 123,
      "provider": "intasend",
      "method": "link"
    }
    ```

    Optional: `phone_number`, `email` (passed to checkout; otherwise from order shipping address). If the order already has a pending IntaSend payment with a `checkout_url`, that payment is returned (201) and no new payment or link is created.

    **IntaSend — STK push (M-Pesa)**

    ```json
    {
      "order": 123,
      "provider": "intasend",
      "method": "stk",
      "phone_number": "0712345678",
      "email": "john@example.com"
    }
    ```

    - `phone_number` is **required** (or from order shipping address).
    - Optional: `email`, `narrative`.
    - The amount sent to M-Pesa is **converted to KES** using the app currency rates (products `Currency` table); the stored payment may use another currency for display/fully-paid calculation.

    **Stripe Checkout**

    ```json
    {
      "order": 123,
      "provider": "stripe",
      "method": "checkout"
    }
    ```

    Optional: `success_url`, `cancel_url` (override settings).

    **Cash / Other (manual)**

    ```json
    {
      "order": 123,
      "provider": "cash",
      "method": "manual"
    }
    ```

    Success (201): payment object including `checkout_url` for link/Stripe when applicable.

    **Common errors (400)**

    | Cause | Response |
    |-------|----------|
    | Non-staff uses cash/other | `{"provider": "Only IntaSend and Stripe are available. Use staff API for cash/other."}` |
    | Order already fully paid | `{"detail": "Order is already fully paid."}` |
    | Missing/invalid credentials | `{"detail": "No active IntaSend credentials found"}` or similar |
    | Provider error | `{"detail": "<message>", "payment": {...}}` |
    | IntaSend STK without phone | `{"phone_number": ["..."]}` or validation error |

## Payment credentials (staff)

Credentials are **global** (not per user), stored in `PaymentCredentials`. `private_key` is write-only and stored encrypted.

=== "Create credentials"

    ```
    POST /api/orders/payment-credentials/
    ```

    ```json
    {
      "provider": "intasend",
      "environment": "sandbox",
      "api_key": "YOUR_PUBLISHABLE_KEY",
      "private_key": "YOUR_SECRET_KEY",
      "is_active": true
    }
    ```

    - **IntaSend:** `api_key` = publishable key, `private_key` = secret key. `environment`: `sandbox` or `live`.
    - **Stripe:** `api_key` can be blank; set `private_key` to `sk_test_...` or `sk_live_...`. Only one active row per `(provider, environment)`.

=== "List credentials"

    ```
    GET /api/orders/payment-credentials/
    ```

=== "Update credentials"

    ```
    PATCH /api/orders/payment-credentials/{id}/
    ```

    Example (rotate secret): `{"private_key": "NEW_SECRET"}`

## Staff payment management

=== "List payments"

    ```
    GET /api/orders/staff/payments/
    ```

    Query: `?include_deleted=true` to include soft-deleted payments.

=== "Create payment"

    ```
    POST /api/orders/staff/payments/
    ```

    Example (record cash as completed):

    ```json
    {
      "order": 123,
      "provider": "cash",
      "status": "completed",
      "amount": "40.00",
      "currency": "KES"
    }
    ```

    Returns 400 if order is already fully paid.

=== "Update payment"

    ```
    PATCH /api/orders/staff/payments/{id}/
    ```

    Example: `{"status": "completed", "provider_state": "PAID"}`

=== "Delete payment (soft)"

    ```
    DELETE /api/orders/staff/payments/{id}/
    ```

    Soft-deletes the payment (`is_deleted=true`). Order `is_fully_paid` is recalculated.

## IntaSend test connection (staff)

=== "Test"

    ```
    GET /api/orders/payments/intasend/test/
    ```

    Validates stored IntaSend credentials by calling the provider API. Staff only.

    - **200:** `{"status": "ok", "message": "IntaSend service initialized successfully"}`
    - **400:** Invalid/missing credentials (e.g. `"No active IntaSend credentials found"`)
    - **503:** IntaSend SDK not installed

## Stripe webhook

Configure in Stripe Dashboard and set `STRIPE_WEBHOOK_SECRET` in your environment.

- **URL:** `POST /api/orders/payments/stripe/webhook/`
- **Event:** `checkout.session.completed` — marks the related payment as completed.

Optional settings:

- `STRIPE_WEBHOOK_SECRET` — signing secret from Stripe (required for webhook).
- `STRIPE_SUCCESS_URL`, `STRIPE_CANCEL_URL` — default redirects for Checkout.

Stripe **secret key** is stored in Payment credentials (DB); the **webhook secret** is from environment only.

## Notes

- Only payments with `status="completed"` and `is_deleted=false` count toward the order total. Amounts are converted to primary currency using the products **Currency** rates.
- IntaSend **link**: optional `INTASEND_REDIRECT_URL_BASE` in settings for post-payment redirect (e.g. `https://yoursite.com/payment/success/`).
- Payment `status` values: `pending`, `processing`, `completed`, `failed`, `cancelled`.

## Related docs

- Orders: `api/orders.md`
- Shipments: `api/shipments.md` (if present)
