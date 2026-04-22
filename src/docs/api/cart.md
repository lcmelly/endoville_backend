# Cart

Persist and sync the authenticated user’s shopping cart with the backend. Line items mirror order placement rules: each row is either a **product** or a **variant**, not both.

=== "Base URL"

    ```
    /api/orders/cart/
    ```

=== "Authentication"

    JWT required.

    - Each user has at most **one** cart (`Cart` is one-to-one with the user).
    - Only the signed-in user can read or modify their own cart.

## Frontend sync flow

1. **On app load (logged in)**  
   Call `GET /api/orders/cart/me/` and replace local cart state with the response `items` (and optionally show `subtotal`).

2. **When the user changes the cart**  
   Debounce updates, then call `PUT` or `POST` `/api/orders/cart/sync/` with the full desired `items` list. The server **replaces** all cart items with the payload (idempotent full sync).

3. **After checkout**  
   When `POST /api/orders/orders/` succeeds, the backend **clears** that user’s cart. Refresh local state from the create response or call `GET .../cart/me/` again (cart will be empty).

4. **Explicit empty cart**  
   Optionally `DELETE /api/orders/cart/clear/` to remove all items without sending a full `items` array.

## Endpoints

=== "Get current cart"

    ```
    GET /api/orders/cart/me/
    ```

    Creates an empty cart for the user if none exists yet.

    Success (200):

    ```json
    {
      "id": 1,
      "user": 42,
      "items": [
        {
          "id": 10,
          "product": 5,
          "variant": null,
          "quantity": 2,
          "product_name": "Vitamin C 1000mg",
          "variant_description": "",
          "barcode": "",
          "unit_price": "20.00",
          "line_total": "40.00"
        },
        {
          "id": 11,
          "product": null,
          "variant": 3,
          "quantity": 1,
          "product_name": "Omega-3",
          "variant_description": "Size: 60 caps",
          "barcode": "1234567890",
          "unit_price": "15.50",
          "line_total": "15.50"
        }
      ],
      "subtotal": "55.50",
      "created_at": "2026-04-20T08:00:00Z",
      "updated_at": "2026-04-22T12:30:00Z"
    }
    ```

    - `unit_price` follows the same rule as orders: variant override price, else product price.
    - `subtotal` is the sum of line totals for all items.

=== "Sync cart (replace all items)"

    ```
    PUT /api/orders/cart/sync/
    POST /api/orders/cart/sync/
    ```

    Request body:

    ```json
    {
      "items": [
        { "product": 5, "quantity": 2 },
        { "variant": 3, "quantity": 1 }
      ]
    }
    ```

    Rules:

    - Each element must include **`quantity`** (integer ≥ 1).
    - Include **`product`** *or* **`variant`**, not both.
    - Duplicate product or variant IDs in one request should be avoided; the database enforces one row per product/variant per cart—prefer merging quantities on the client before sync.

    Success (200): same shape as `GET .../cart/me/`.

    Syncing also **resets** abandoned-cart reminder tracking for that cart (see below).

=== "Clear cart"

    ```
    DELETE /api/orders/cart/clear/
    ```

    Removes all line items. Success (200): same shape as `GET .../cart/me/` with an empty `items` array.

## Relation to orders

- Placing an order uses `POST /api/orders/orders/` with `items` in the same product/variant shape as the cart sync payload.
- After a successful order create, the user’s **server-side cart is cleared** automatically.
- See also: `api/orders.md`

## Abandoned cart reminders (ops)

The backend can email users who leave items in the cart without purchasing. Reminders are sent at **12 hours**, then **24 hours**, then **48 hours** of cart inactivity (based on `updated_at`), then no further emails for that cart cycle.

- **Template**: set environment variable `ZEPTOMAIL_CART_REMINDER_TEMPLATE_KEY` to your ZeptoMail template key. If unset, reminder sending is skipped.
- **Background processing** ([django-background-tasks](https://django-background-tasks.readthedocs.io/)): reminder work runs in the DB-backed task queue, not inline in the web process.

    1. Install the package and add `background_task` to `INSTALLED_APPS` (already included in this project).
    2. Apply migrations (creates `background_task` tables): `python src/manage.py migrate`
    3. **Once per environment** (after deploy), schedule the repeating job:

        ```bash
        python src/manage.py schedule_abandoned_cart_reminders
        ```

        Interval between runs defaults to **900** seconds (15 minutes); override with env `ABANDONED_CART_REMINDER_BG_INTERVAL_SECONDS`.

    4. Run a worker continuously (Supervisor, systemd, etc.):

        ```bash
        python src/manage.py process_tasks
        ```

    Optional: queue a **single** run without setting up repeat (still needs `process_tasks`):

    ```bash
    python src/manage.py send_abandoned_cart_reminders
    ```

- **User activity**: any successful `sync` or `clear` updates the cart and resets the reminder schedule for the next abandonment window.

### ZeptoMail `merge_info` keys

The reminder email builder sends (among others): `name`, `team`, `support_email`, `support_phone`, `current_year`, `reminder_hours` (`"12"`, `"24"`, or `"48"`), `item_count`, `subtotal`, `currency`, `cart_items` (JSON array of `{ name, quantity, unit_price, line_total }`), **`cart_items_html`** (pre-rendered table rows for the template), and **`cart_url`** (from env `FRONTEND_CART_URL`, or `#` if unset).

A ready-to-paste HTML layout lives at `src/docs/email-templates/zeptomail-abandoned-cart-reminder.html`. If ZeptoMail escapes `{{cart_items_html}}`, configure that merge field as HTML/raw per ZeptoMail’s docs.

## Related docs

- Orders: `api/orders.md`
- Payments: `api/payments.md`
