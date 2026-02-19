# Products

Manage product catalog: categories, subcategories, products, and variants (with barcodes).

=== "Base URL"

    ```
    /api/products/
    ```

=== "Authentication"

    - Reads are public.
    - Writes require `is_staff=true`.

## Cost Price (Staff-only)

Products and variants include a `cost_price` field, but it is **only returned in API responses when the requester is a staff user**.

- Public/non-staff: `cost_price` is omitted from responses.
- Staff: `cost_price` is included for both products and nested variants.

## Currency conversion (non-staff)

For **non-staff** product and variant responses, prices include `display_currency` and `currency_symbol`. Prices use the primary currency (e.g. USD) by default. Use `?currency=CODE` to convert. The API uses the Currency `usd_rate` for conversion when `?currency=` is passed.
- **Default**: When no `?currency=` param is passed, the primary currency (typically USD) is used. Prices include `display_currency` and `currency_symbol`.
- **With `?currency=CODE`**: Prices are converted; response includes `display_currency`, `currency_symbol`, and converted `price`.
- **Staff**: Always see stored prices; `display_currency` and `currency_symbol` are included (primary/USD).

## Currencies

Manage currencies for price conversion. Stored prices are in the primary currency (e.g. USD). `usd_rate` means 1 USD = usd_rate × &lt;currency&gt; (e.g. KES with usd_rate 160.50 → 1 USD = 160.50 KES).

=== "List"

    ```
    GET /api/products/currencies/
    ```

=== "Retrieve"

    ```
    GET /api/products/currencies/{id}/
    ```

=== "Create (staff)"

    ```
    POST /api/products/currencies/
    ```

    ```json
    {
      "code": "KES",
      "name": "Kenyan Shilling",
      "symbol": "KSh",
      "usd_rate": "160.50",
      "is_primary": false,
      "is_active": true
    }
    ```

=== "Update (staff)"

    ```
    PUT /api/products/currencies/{id}/
    PATCH /api/products/currencies/{id}/
    ```

    ```json
    {
      "code": "KES",
      "name": "Kenyan Shilling",
      "symbol": "KSh",
      "usd_rate": "161.00",
      "is_primary": false,
      "is_active": true
    }
    ```

    - `PUT` expects the full object.
    - `PATCH` can send only the fields you want to change.
    - Setting `is_primary=true` on one currency clears `is_primary` on others.

=== "Delete (staff)"

    ```
    DELETE /api/products/currencies/{id}/
    ```

=== "Fields"

    | Field | Type | Required | Description |
    | --- | --- | --- | --- |
    | `code` | string | Yes | Currency code (e.g. USD, KES). Unique. |
    | `name` | string | No | Display name (e.g. US Dollar) |
    | `symbol` | string | No | Symbol (e.g. $, KSh) |
    | `usd_rate` | string | No | Conversion rate: 1 USD = usd_rate × this currency. Default 1. |
    | `is_primary` | boolean | No | Primary currency (typically USD). Only one can be primary. |
    | `is_active` | boolean | No | If false, currency is excluded from product conversion. Default true. |

=== "Example: Create currency (staff)"

    ```bash
    curl -X POST https://api.endovillehealth.com/api/products/currencies/ \
      -H "Authorization: Bearer <access_token>" \
      -H "Content-Type: application/json" \
      -d '{
        "code": "KES",
        "name": "Kenyan Shilling",
        "symbol": "KSh",
        "usd_rate": "160.50",
        "is_primary": false,
        "is_active": true
      }'
    ```

=== "Example: Update currency (staff)"

    ```bash
    curl -X PATCH https://api.endovillehealth.com/api/products/currencies/1/ \
      -H "Authorization: Bearer <access_token>" \
      -H "Content-Type: application/json" \
      -d '{
        "usd_rate": "161.00"
      }'
    ```

=== "Example: Delete currency (staff)"

    ```bash
    curl -X DELETE https://api.endovillehealth.com/api/products/currencies/1/ \
      -H "Authorization: Bearer <access_token>"
    ```

## Permissions Summary

| Resource | Read | Create | Update | Delete |
| --- | --- | --- | --- | --- |
| Currencies | Anyone | Staff only | Staff only | Staff only |
| Categories | Anyone | Staff only | Staff only | Staff only |
| Subcategories | Anyone | Staff only | Staff only | Staff only |
| Products | Anyone | Staff only | Staff only | Staff only |
| Variants | Anyone | Staff only | Staff only | Staff only |
| Variation Attributes | Anyone | Staff only | Staff only | Staff only |
| Variation Options | Anyone | Staff only | Staff only | Staff only |

## Categories

=== "List"

    ```
    GET /api/products/categories/
    ```

=== "Retrieve"

    ```
    GET /api/products/categories/{id}/
    ```

=== "Create (staff)"

    ```
    POST /api/products/categories/
    ```

    ```json
    {
      "name": "Supplements",
      "description": "All supplement products"
    }
    ```

=== "Update (staff)"

    ```
    PUT /api/products/categories/{id}/
    PATCH /api/products/categories/{id}/
    ```

    ```json
    {
      "name": "Supplements",
      "description": "Updated description"
    }
    ```

    - `PUT` expects the full object.
    - `PATCH` can send only the fields you want to change.

=== "Delete (staff)"

    ```
    DELETE /api/products/categories/{id}/
    ```

## Subcategories

=== "List"

    ```
    GET /api/products/subcategories/
    ```

=== "Retrieve"

    ```
    GET /api/products/subcategories/{id}/
    ```

=== "Create (staff)"

    ```
    POST /api/products/subcategories/
    ```

    ```json
    {
      "name": "Vitamins",
      "category": 1
    }
    ```

=== "Update (staff)"

    ```
    PUT /api/products/subcategories/{id}/
    PATCH /api/products/subcategories/{id}/
    ```

    ```json
    {
      "name": "Vitamins",
      "category": 1
    }
    ```

=== "Delete (staff)"

    ```
    DELETE /api/products/subcategories/{id}/
    ```

## Products

=== "List"

    ```
    GET /api/products/products/
    GET /api/products/products/?currency=KES
    ```

    Non-staff: use `?currency=CODE` for converted prices; `display_currency` and `currency_symbol` are always included (default: primary/USD).

=== "Retrieve"

    ```
    GET /api/products/products/{id}/
    GET /api/products/products/{id}/?currency=KES
    ```

    Response includes a nested `variants` array. Non-staff: use `?currency=CODE` for converted `price`; `display_currency` and `currency_symbol` are always included.

=== "Example response (non-staff, with currency)"

    Request: `GET /api/products/products/1/?currency=KES` (product stored price: 19.99 USD; KES usd_rate: 160.50)

    ```json
    {
      "id": 1,
      "name": "Vitamin C 1000mg",
      "description": "High-strength Vitamin C",
      "price": "3208.40",
      "display_currency": "KES",
      "currency_symbol": "KSh",
      "stock": 100,
      "image_urls": ["https://cdn.example.com/p/vit-c-1.png"],
      "image_refs": ["p/vit-c-1.png"],
      "variants": [
        {
          "id": 1,
          "price": "4010.50",
          "display_currency": "KES",
          "currency_symbol": "KSh",
          "barcode": "0123456789012",
          "image_urls": ["https://cdn.example.com/p/vit-c-red-xl.png"],
          "image_refs": ["p/vit-c-red-xl.png"]
        }
      ]
    }
    ```

=== "Create (staff)"

    ```
    POST /api/products/products/
    ```

    ```json
    {
      "name": "Vitamin C 1000mg",
      "description": "High-strength Vitamin C",
      "price": "19.99",
      "cost_price": "12.00",
      "stock": 100,
      "image_urls": ["https://cdn.example.com/p/vit-c-1.png"],
      "image_refs": ["p/vit-c-1.png"],
      "subcategories": [1, 2],
      "meta_title": "Vitamin C 1000mg",
      "meta_description": "High-strength Vitamin C for immune support"
    }
    ```

=== "Update (staff)"

    ```
    PUT /api/products/products/{id}/
    PATCH /api/products/products/{id}/
    ```

    ```json
    {
      "name": "Vitamin C 1000mg",
      "description": "Updated description",
      "price": "21.99",
      "cost_price": "13.00",
      "stock": 80,
      "image_urls": ["https://cdn.example.com/p/vit-c-1.png"],
      "image_refs": ["p/vit-c-1.png"],
      "subcategories": [1],
      "meta_title": "Vitamin C 1000mg",
      "meta_description": "Updated meta description"
    }
    ```

    - `slug`, `created_at`, and `updated_at` are read-only.
    - Variants are managed via the variants endpoints (see below).

=== "Delete (staff)"

    ```
    DELETE /api/products/products/{id}/
    ```

## Variation Attributes (e.g. Color, Size)

=== "List"

    ```
    GET /api/products/variation-attributes/
    ```

=== "Create (staff)"

    ```
    POST /api/products/variation-attributes/
    ```

    ```json
    {
      "name": "Color"
    }
    ```

## Variation Options (e.g. Color=Red)

=== "List"

    ```
    GET /api/products/variation-options/
    ```

=== "Create (staff)"

    ```
    POST /api/products/variation-options/
    ```

    ```json
    {
      "attribute": 1,
      "value": "Red"
    }
    ```

=== "Update (staff)"

    ```
    PUT /api/products/variation-options/{id}/
    PATCH /api/products/variation-options/{id}/
    ```

    ```json
    {
      "attribute": 1,
      "value": "Red"
    }
    ```

## Variants (barcode-based)

=== "List"

    ```
    GET /api/products/variants/
    GET /api/products/variants/?currency=KES
    ```

    Non-staff: `display_currency` and `currency_symbol` always included; use `?currency=CODE` to convert.

=== "Retrieve"

    ```
    GET /api/products/variants/{id}/
    GET /api/products/variants/{id}/?currency=KES
    ```

    Non-staff: `display_currency` and `currency_symbol` always included; use `?currency=CODE` to convert.

=== "Create (staff)"

    ```
    POST /api/products/variants/
    ```

    ```json
    {
      "product": 1,
      "options": [10, 11],
      "sku": "SKU-RED-XL",
      "barcode": "0123456789012",
      "price": "24.99",
      "cost_price": "15.00",
      "stock": 10,
      "image_urls": ["https://cdn.example.com/p/vit-c-red-xl.png"],
      "image_refs": ["p/vit-c-red-xl.png"],
      "is_active": true
    }
    ```

=== "Update (staff)"

    ```
    PUT /api/products/variants/{id}/
    PATCH /api/products/variants/{id}/
    ```

    ```json
    {
      "product": 1,
      "options": [10, 11],
      "sku": "SKU-RED-XL",
      "barcode": "0123456789012",
      "price": "24.99",
      "cost_price": "16.00",
      "stock": 12,
      "image_urls": ["https://cdn.example.com/p/vit-c-red-xl.png"],
      "image_refs": ["p/vit-c-red-xl.png"],
      "is_active": true
    }
    ```

    - `barcode` must be unique.

## Product and variant image fields

- **`image_urls`**: Array of image URLs (display).
- **`image_refs`**: Array of storage keys/paths for the same images, in the same order as `image_urls`.

## Notes

- All product endpoints are public for reads.
- All writes (create/update/delete) require a **staff** user.
- Non-staff: `display_currency` and `currency_symbol` included by default (USD); use `?currency=CODE` to convert.
