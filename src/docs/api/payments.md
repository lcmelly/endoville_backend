---
title: Payments
icon: lucide/credit-card
---

# Payments

Start a payment for an order, then check whether it went through.

A shopper can pay their own order with IntaSend or Stripe. Staff can record any provider, including cash.

=== "Base URLs"

    - User payments: `/api/orders/payments/`
    - Check payment status (refresh from provider): `POST /api/orders/payments/{id}/check-status/`
    - Payment credentials (staff): `/api/orders/payment-credentials/`
    - Staff manage payments: `/api/orders/staff/payments/`
    - Staff refunds: `/api/orders/staff/refunds/`
    - IntaSend test connection (staff): `/api/orders/payments/intasend/test/`
    - Stripe webhook: `POST /api/orders/payments/stripe/webhook/`

=== "Authentication"

    You need to be signed in, except for the Stripe webhook, which Stripe calls itself.

    - **Shoppers** can create and read payments on their own orders. Only IntaSend and Stripe are allowed. Cash and other methods are recorded by staff.
    - **Staff** can create and read every payment, and the stored provider keys. Any provider is allowed.
    - Nobody can edit or delete a payment. `PATCH` and `DELETE` return **405**. Returning money is a refund.

## Providers and methods

| Provider   | Methods        | Notes |
|-----------|----------------|-------|
| **IntaSend** (`intasend`) | `link`, `stk` | Link: hosted checkout URL. STK: M-Pesa push; amount is converted to **KES** using currency rates. |
| **Stripe** (`stripe`)     | `checkout`    | Redirects to Stripe Checkout; webhook marks payment completed. |
| **Cash / Other** (`cash`, `other`) | `manual` | Staff record the payment, including `status: "completed"`, when they create it. |

- Orders are **fully paid** when money still held, converted to the primary currency, is at least the order total. `completed` and `refund_initiated` payments count in full. A `completed` refund is subtracted. An `initiated` refund still counts as held.
- If an order is already fully paid, creating a new payment returns **400** with `"Order is already fully paid."`
- If an order is cancelled, creating a new payment returns **400** with `"Cannot record a payment for a cancelled order."`
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
        "transaction_id": "pay-8f3a1c",
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

    Returns the payment and a **status_check** object. The provider is called only when the stored payment status is `pending` or `processing`. If the payment is already `completed`, `failed`, `cancelled`, `refund_initiated`, or `refunded`, the API returns the stored status without calling IntaSend or Stripe.

    - **Pending/processing + IntaSend:** Calls IntaSend, updates the payment record, and returns the latest status.
    - **Pending/processing + Stripe:** Staff or the order owner can call this. It reads the Checkout Session. A paid session marks the payment `completed`. An expired session marks it `cancelled`. The same check runs every minute for every open Stripe payment while `python manage.py process_tasks` is running.
    - **Already completed, failed, cancelled, refund_initiated, or refunded:** No provider call; returns current payment and status.
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
        "transaction_id": "pay-8f3a1c",
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

    Optional: `success_url`, `cancel_url` (override settings). The charged amount is the order total converted with the same Stripe FX rate shoppers see on the product. That rate is stored on the payment as `usd_rate`, so a later rate refresh does not change whether the order is fully paid.

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
    | Order is cancelled | `{"detail": "Cannot record a payment for a cancelled order."}` |
    | Missing/invalid credentials | `{"detail": "No active IntaSend credentials found"}` or similar |
    | Provider error | `{"detail": "<message>", "payment": {...}}` |
    | IntaSend STK without phone | `{"phone_number": ["..."]}` or validation error |

## Payment credentials (staff)

Credentials are **global** (not per user), stored in `PaymentCredentials`. The **private key** is encrypted on save and only decrypted when the backend calls the provider (IntaSend/Stripe); it is never returned in API responses or stored in plain text. In requests, send `private_key` to set or rotate the secret (write-only).

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
      "currency": "KES",
      "transaction_id": "txn-cash-1042"
    }
    ```

    `transaction_id` is optional. Omit it, send `null`, or send `""`. The stored value and the response use `null` when it is empty. A non-empty id must be unique.

    Before the payment is saved, open Stripe checkout sessions on that order are checked with Stripe. A paid session is marked `completed`. If that covers the order, this call returns 400 and no new payment is created. If an open Stripe session cannot be checked, the call returns 400 and no payment is created.

    Returns 400 if the order is cancelled or already fully paid. Returns 400 if a non-empty `transaction_id` is already used.

Payments are not edited or deleted. A shopper and a staff user both get **405** for `PATCH` or `DELETE` on a payment. Returning money is a refund.

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

`checkout.session.completed` marks the related payment completed. The endpoint checks the `Stripe-Signature` header with `STRIPE_WEBHOOK_SECRET`.

- **URL:** `POST /api/orders/payments/stripe/webhook/`
- **Event:** `checkout.session.completed`

The Stripe **secret key** is stored in Payment credentials. The **webhook signing secret** is environment only.

| Setting | Role |
| --- | --- |
| `STRIPE_WEBHOOK_SECRET` | Signing secret. The webhook returns 400 until this is set. |
| `STRIPE_SUCCESS_URL` | Where Checkout sends the shopper after payment, when the client did not send `success_url`. |
| `STRIPE_CANCEL_URL` | Where Checkout sends the shopper if they leave, when the client did not send `cancel_url`. |

### Local development

The storefront already sends `success_url` and `cancel_url` (`/orders?payment=success` and `/orders?payment=failed`). The two URL settings are the fallback, and for local work they point at `http://localhost:3000`.

Stripe cannot call your machine directly. Forward the event with the Stripe CLI while `runserver` is on port 8000:

```bash
brew install stripe/stripe-cli/stripe
stripe login
stripe listen --forward-to localhost:8000/api/orders/payments/stripe/webhook/ --events checkout.session.completed
```

`stripe listen` prints a signing secret that starts with `whsec_`. Put that value in `STRIPE_WEBHOOK_SECRET` and restart `runserver`. Leave `stripe listen` running while you pay a test Checkout session. The CLI shows the delivery, and the payment becomes `completed`.

A deployed server uses a Dashboard webhook endpoint on the public URL instead of `stripe listen`, and that endpoint's own signing secret.

## Refunds

A refund is a record that money is going back to the customer. Creating or completing one does not call Stripe or IntaSend. Every refund has a `reason` and a `transaction_id`. Staff send both when they record a refund. A line change fills the reason from the change and assigns a transaction id. `provider_refund_id` is still optional and is the id from Stripe or IntaSend when staff have it.

Shoppers read refunds on the order (`refunds` on `GET /api/orders/orders/{id}/`). Staff list and update them here.

A refund is created in two situations:

- Staff refund a **cancelled** order that has a completed payment, in full or in part.
- Staff remove a line, or replace it with a cheaper product, on an open paid order. The API writes an `initiated` refund for the price difference. See `api/orders.md`.

=== "List"

    ```
    GET /api/orders/staff/refunds/
    GET /api/orders/staff/refunds/{id}/
    ```

    Staff only. Each refund has `id`, `order`, `payment`, `status` (`initiated` or `completed`), `amount`, `currency`, `reason`, `transaction_id`, `provider_refund_id`, `initiated_by`, `completed_at`, `created_at`, and `updated_at`.

=== "Initiate"

    ```
    POST /api/orders/staff/refunds/
    ```

    Staff only. The order must be `CANCELLED` (or already `REFUNDED` when another payment on it still needs a refund). The payment must be `completed` or `refund_initiated`. `reason` and `transaction_id` are required. `transaction_id` is unique. Omit `amount` to refund whatever balance is still held. A smaller `amount` records a partial refund, and another refund can cover the rest later.

    ```json
    {
      "payment": 500,
      "reason": "Customer cancelled after paying",
      "transaction_id": "txn-8841"
    }
    ```

    Partial refund of a 40.00 payment:

    ```json
    {
      "payment": 500,
      "amount": "15.00",
      "reason": "One item was unavailable",
      "transaction_id": "txn-8842"
    }
    ```

    A later refund on the same payment can cover the remaining 25.00. `amount` must be greater than zero and no larger than the balance still held.

    Errors:

    | Status | When |
    | --- | --- |
    | 403 | The caller is not staff |
    | 400 | The order is not `CANCELLED` or `REFUNDED` |
    | 400 | The payment is not `completed` or `refund_initiated` |
    | 400 | `amount` is missing when nothing is left to refund, or it is larger than the balance still held |
    | 400 | `reason` is missing or blank |
    | 400 | `transaction_id` is missing, blank, or already used |

    Success (201):

    ```json
    {
      "id": 9,
      "order": 123,
      "payment": 500,
      "status": "initiated",
      "amount": "40.00",
      "currency": "KES",
      "reason": "Customer cancelled after paying",
      "transaction_id": "txn-8841",
      "provider_refund_id": "",
      "initiated_by": 2,
      "completed_at": null,
      "created_at": "2026-01-20T10:00:00Z",
      "updated_at": "2026-01-20T10:00:00Z"
    }
    ```

    While any refund on that payment is `initiated`, the payment status becomes `refund_initiated`. The order stays `CANCELLED`. An initiated refund still counts as paid.

=== "Mark done"

    ```
    PATCH /api/orders/staff/refunds/{id}/
    ```

    ```json
    {
      "status": "completed",
      "provider_refund_id": "re_123"
    }
    ```

    `completed_at` is set. When the completed refunds cover the whole payment, its status becomes `refunded`. A completed refund for only part of the payment leaves the payment `completed`, and that part is taken out of the paid sum. When every received payment on a cancelled order is `refunded`, the order status becomes `REFUNDED`.

    Creating the record with `"status": "completed"` records it as done in one step.

    Setting the order status to `REFUNDED` writes a completed refund for each payment still `completed` or `refund_initiated`, and those payments become `refunded`.

    Refunds are not deleted. Removing or replacing an order line can also create a partial refund. See `api/orders.md`.

## Notes

- Money still held is payments in `completed` or `refund_initiated` (`is_deleted=false`), minus refunds in `completed`. Each amount is converted to the primary currency with the `usd_rate` stored on that payment. Payments created before rate snapshots fall back to the current products **Currency** rate. A payment in `refunded` has been covered by completed refunds, so it adds nothing further.
- IntaSend **link**: optional `INTASEND_REDIRECT_URL_BASE` in settings for post-payment redirect (e.g. `https://yoursite.com/payment/success/`).
- Payment `status` values: `pending`, `processing`, `completed`, `failed`, `cancelled`, `refund_initiated`, `refunded`.
- Refund `status` values: `initiated`, `completed`.

## Related docs

- Orders: `api/orders.md`
- Shipments: `api/shipments.md` (if present)
