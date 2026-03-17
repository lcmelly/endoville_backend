# Products

Manage product catalog: brands, categories, subcategories, products, variants (optional sku/barcode), and **product reviews**. Reviews are shared across all variants of a product. Each product has a stored **avg_rating** (0–5) and **review_count** updated automatically when reviews are added, updated, or deleted.

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

    **Example: 200 OK**

    ```json
    [
      {
        "id": 1,
        "code": "USD",
        "name": "US Dollar",
        "symbol": "$",
        "usd_rate": "1.000000",
        "is_primary": true,
        "is_active": true,
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z"
      },
      {
        "id": 2,
        "code": "KES",
        "name": "Kenyan Shilling",
        "symbol": "KSh",
        "usd_rate": "160.500000",
        "is_primary": false,
        "is_active": true,
        "created_at": "2025-01-16T12:00:00Z",
        "updated_at": "2025-01-16T12:00:00Z"
      }
    ]
    ```

    **Example: Error** — List is public; no 403. Invalid request may return `400` with detail.

=== "Retrieve"

    ```
    GET /api/products/currencies/{id}/
    ```

    **Example: 200 OK**

    ```json
    {
      "id": 2,
      "code": "KES",
      "name": "Kenyan Shilling",
      "symbol": "KSh",
      "usd_rate": "160.500000",
      "is_primary": false,
      "is_active": true,
      "created_at": "2025-01-16T12:00:00Z",
      "updated_at": "2025-01-16T12:00:00Z"
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
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

    **Example: 201 Created**

    ```json
    {
      "id": 2,
      "code": "KES",
      "name": "Kenyan Shilling",
      "symbol": "KSh",
      "usd_rate": "160.500000",
      "is_primary": false,
      "is_active": true,
      "created_at": "2025-01-16T12:00:00Z",
      "updated_at": "2025-01-16T12:00:00Z"
    }
    ```

    **Example: 400 Bad Request (validation)**

    ```json
    {
      "code": ["currency with this code already exists."]
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
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

    **Example: 200 OK**

    ```json
    {
      "id": 2,
      "code": "KES",
      "name": "Kenyan Shilling",
      "symbol": "KSh",
      "usd_rate": "161.000000",
      "is_primary": false,
      "is_active": true,
      "created_at": "2025-01-16T12:00:00Z",
      "updated_at": "2025-02-19T14:30:00Z"
    }
    ```

    **Example: 400 Bad Request (validation)**

    ```json
    {
      "usd_rate": ["A valid number is required."]
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

=== "Delete (staff)"

    ```
    DELETE /api/products/currencies/{id}/
    ```

    **Example: 204 No Content** — Empty response body.

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
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
| Brands | Anyone | Staff only | Staff only | Staff only |
| Categories | Anyone | Staff only | Staff only | Staff only |
| Subcategories | Anyone | Staff only | Staff only | Staff only |
| Products | Anyone | Staff only | Staff only | Staff only |
| Variants | Anyone | Staff only | Staff only | Staff only |
| Product Reviews | Anyone | Authenticated (must have completed order with product) | Owner or staff | Owner or staff |
| Variation Attributes | Anyone | Staff only | Staff only | Staff only |
| Variation Options | Anyone | Staff only | Staff only | Staff only |

## Brands

Brands can have multiple images using aligned arrays:

- `image_urls`: public image URLs
- `image_refs`: storage keys/paths in the same order as `image_urls`
- `image_labels`: labels in the same order as `image_urls`, for example `logo` or `banner one`

=== "List"

    ```
    GET /api/products/brands/
    ```

    **Example: 200 OK**

    ```json
    [
      {
        "id": 1,
        "name": "Nature Made",
        "image_urls": [
          "https://cdn.example.com/brands/nature-made-logo.png",
          "https://cdn.example.com/brands/nature-made-banner.png"
        ],
        "image_refs": [
          "brands/nature-made-logo.png",
          "brands/nature-made-banner.png"
        ],
        "image_labels": ["logo", "banner"],
        "description": "Trusted wellness and supplement brand."
      }
    ]
    ```

    **Example: Error** — List is public; no 403.

=== "Retrieve"

    ```
    GET /api/products/brands/{id}/
    ```

    **Example: 200 OK**

    ```json
    {
      "id": 1,
      "name": "Nature Made",
      "image_urls": [
        "https://cdn.example.com/brands/nature-made-logo.png",
        "https://cdn.example.com/brands/nature-made-banner.png"
      ],
      "image_refs": [
        "brands/nature-made-logo.png",
        "brands/nature-made-banner.png"
      ],
      "image_labels": ["logo", "banner"],
      "description": "Trusted wellness and supplement brand."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

=== "Create (staff)"

    ```
    POST /api/products/brands/
    ```

    ```json
    {
      "name": "Nature Made",
      "image_urls": [
        "https://cdn.example.com/brands/nature-made-logo.png",
        "https://cdn.example.com/brands/nature-made-banner.png"
      ],
      "image_refs": [
        "brands/nature-made-logo.png",
        "brands/nature-made-banner.png"
      ],
      "image_labels": ["logo", "banner"],
      "description": "Trusted wellness and supplement brand."
    }
    ```

    **Example: 201 Created**

    ```json
    {
      "id": 1,
      "name": "Nature Made",
      "image_urls": [
        "https://cdn.example.com/brands/nature-made-logo.png",
        "https://cdn.example.com/brands/nature-made-banner.png"
      ],
      "image_refs": [
        "brands/nature-made-logo.png",
        "brands/nature-made-banner.png"
      ],
      "image_labels": ["logo", "banner"],
      "description": "Trusted wellness and supplement brand."
    }
    ```

    **Example: 400 Bad Request (validation)**

    ```json
    {
      "name": ["This field may not be blank."]
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

=== "Update (staff)"

    ```
    PUT /api/products/brands/{id}/
    PATCH /api/products/brands/{id}/
    ```

    ```json
    {
      "name": "Nature Made",
      "image_urls": [
        "https://cdn.example.com/brands/nature-made-logo.png",
        "https://cdn.example.com/brands/nature-made-banner-v2.png"
      ],
      "image_refs": [
        "brands/nature-made-logo.png",
        "brands/nature-made-banner-v2.png"
      ],
      "image_labels": ["logo", "banner"],
      "description": "Updated brand description."
    }
    ```

    - `PUT` expects the full object.
    - `PATCH` can send only the fields you want to change.

    **Example: 200 OK**

    ```json
    {
      "id": 1,
      "name": "Nature Made",
      "image_urls": [
        "https://cdn.example.com/brands/nature-made-logo.png",
        "https://cdn.example.com/brands/nature-made-banner-v2.png"
      ],
      "image_refs": [
        "brands/nature-made-logo.png",
        "brands/nature-made-banner-v2.png"
      ],
      "image_labels": ["logo", "banner"],
      "description": "Updated brand description."
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

=== "Delete (staff)"

    ```
    DELETE /api/products/brands/{id}/
    ```

    **Example: 204 No Content** — Empty response body.

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

=== "Fields"

    | Field | Type | Required | Description |
    | --- | --- | --- | --- |
    | `name` | string | Yes | Brand name. |
    | `image_urls` | array[string] | No | Public image URLs for the brand. |
    | `image_refs` | array[string] | No | Storage keys/paths for brand images, in the same order as `image_urls`. |
    | `image_labels` | array[string] | No | Labels for each brand image, in the same order as `image_urls`. |
    | `description` | string | No | Brand description. |

## Categories

=== "List"

    ```
    GET /api/products/categories/
    ```

    **Example: 200 OK**

    ```json
    [
      {
        "id": 1,
        "name": "Supplements",
        "description": "All supplement products"
      },
      {
        "id": 2,
        "name": "Vitamins",
        "description": "Vitamin products"
      }
    ]
    ```

    **Example: Error** — List is public; no 403.

=== "Retrieve"

    ```
    GET /api/products/categories/{id}/
    ```

    **Example: 200 OK**

    ```json
    {
      "id": 1,
      "name": "Supplements",
      "description": "All supplement products"
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
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

    **Example: 201 Created**

    ```json
    {
      "id": 1,
      "name": "Supplements",
      "description": "All supplement products"
    }
    ```

    **Example: 400 Bad Request (validation)**

    ```json
    {
      "name": ["This field may not be blank."]
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
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

    **Example: 200 OK**

    ```json
    {
      "id": 1,
      "name": "Supplements",
      "description": "Updated description"
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

=== "Delete (staff)"

    ```
    DELETE /api/products/categories/{id}/
    ```

    **Example: 204 No Content** — Empty response body.

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

## Subcategories

=== "List"

    ```
    GET /api/products/subcategories/
    ```

    **Example: 200 OK**

    ```json
    [
      {
        "id": 1,
        "name": "Vitamins",
        "category": 1
      },
      {
        "id": 2,
        "name": "Minerals",
        "category": 1
      }
    ]
    ```

    **Example: Error** — List is public; no 403.

=== "Retrieve"

    ```
    GET /api/products/subcategories/{id}/
    ```

    **Example: 200 OK**

    ```json
    {
      "id": 1,
      "name": "Vitamins",
      "category": 1
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
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

    **Example: 201 Created**

    ```json
    {
      "id": 1,
      "name": "Vitamins",
      "category": 1
    }
    ```

    **Example: 400 Bad Request (validation)**

    ```json
    {
      "category": ["This field is required."],
      "name": ["This field may not be blank."]
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
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

    **Example: 200 OK**

    ```json
    {
      "id": 1,
      "name": "Vitamins",
      "category": 1
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

=== "Delete (staff)"

    ```
    DELETE /api/products/subcategories/{id}/
    ```

    **Example: 204 No Content** — Empty response body.

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

## Products

Product `sku` and `barcode` are **optional**. When provided, `barcode` must be unique across all products.

=== "List"

    ```
    GET /api/products/products/
    GET /api/products/products/?currency=KES
    ```

    Non-staff: use `?currency=CODE` for converted prices; `display_currency` and `currency_symbol` are always included (default: primary/USD).

    **Example: 200 OK**

    ```json
    [
      {
        "id": 1,
        "name": "Vitamin C 1000mg",
        "description": "High-strength Vitamin C",
        "brand": 1,
        "brand_details": {
          "id": 1,
          "name": "Nature Made",
          "image_urls": [
            "https://cdn.example.com/brands/nature-made-logo.png",
            "https://cdn.example.com/brands/nature-made-banner.png"
          ],
          "image_refs": [
            "brands/nature-made-logo.png",
            "brands/nature-made-banner.png"
          ],
          "image_labels": ["logo", "banner"],
          "description": "Trusted wellness and supplement brand."
        },
        "price": "19.99",
        "display_currency": "USD",
        "currency_symbol": "$",
        "stock": 100,
        "sku": "VIT-C-1000",
        "barcode": "0123456789001",
        "image_urls": ["https://cdn.example.com/p/vit-c-1.png"],
        "image_refs": ["p/vit-c-1.png"],
        "subcategories": [1, 2],
        "meta_title": "Vitamin C 1000mg",
        "meta_description": "High-strength Vitamin C for immune support",
        "slug": "vitamin-c-1000mg",
        "avg_rating": "4.25",
        "review_count": 12,
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
        "variants": [
          {
            "id": 1,
            "product": 1,
            "options": [10, 11],
            "options_details": [
              { "id": 10, "attribute": 1, "attribute_name": "Color", "value": "Red" },
              { "id": 11, "attribute": 2, "attribute_name": "Size", "value": "XL" }
            ],
            "sku": "SKU-RED-XL",
            "barcode": "0123456789012",
            "price": "24.99",
            "stock": 10,
            "image_urls": ["https://cdn.example.com/p/vit-c-red-xl.png"],
            "image_refs": ["p/vit-c-red-xl.png"],
            "is_active": true,
            "created_at": "2025-01-15T10:00:00Z",
            "updated_at": "2025-01-15T10:00:00Z",
            "avg_rating": "4.25",
            "review_count": 12,
            "reviews": [],
            "display_currency": "USD",
            "currency_symbol": "$"
          }
        ],
        "reviews": [
          {
            "id": 1,
            "product": 1,
            "order": 42,
            "user": 5,
            "user_display": "Jane",
            "rating": 5,
            "body": "Great product.",
            "is_anonymous": false,
            "created_at": "2025-02-01T12:00:00Z",
            "updated_at": "2025-02-01T12:00:00Z"
          }
        ]
      }
    ]
    ```

    **Example: Error** — List is public; no 403.

=== "Retrieve"

    ```
    GET /api/products/products/{id}/
    GET /api/products/products/{id}/?currency=KES
    ```

    Response includes a nested `variants` array. Non-staff: use `?currency=CODE` for converted `price`; `display_currency` and `currency_symbol` are always included.

    **Example: 200 OK (non-staff, with currency)**

    Request: `GET /api/products/products/1/?currency=KES` (product stored price: 19.99 USD; KES usd_rate: 160.50)

    ```json
    {
      "id": 1,
      "name": "Vitamin C 1000mg",
      "description": "High-strength Vitamin C",
      "brand": 1,
      "brand_details": {
        "id": 1,
        "name": "Nature Made",
        "image_urls": [
          "https://cdn.example.com/brands/nature-made-logo.png",
          "https://cdn.example.com/brands/nature-made-banner.png"
        ],
        "image_refs": [
          "brands/nature-made-logo.png",
          "brands/nature-made-banner.png"
        ],
        "image_labels": ["logo", "banner"],
        "description": "Trusted wellness and supplement brand."
      },
      "price": "3208.40",
      "display_currency": "KES",
      "currency_symbol": "KSh",
      "stock": 100,
      "sku": "VIT-C-1000",
      "barcode": "0123456789001",
      "image_urls": ["https://cdn.example.com/p/vit-c-1.png"],
      "image_refs": ["p/vit-c-1.png"],
      "avg_rating": "4.25",
      "review_count": 12,
      "variants": [
        {
          "id": 1,
          "price": "4010.50",
          "display_currency": "KES",
          "currency_symbol": "KSh",
          "barcode": "0123456789012",
          "image_urls": ["https://cdn.example.com/p/vit-c-red-xl.png"],
          "image_refs": ["p/vit-c-red-xl.png"],
          "avg_rating": "4.25",
          "review_count": 12,
          "reviews": []
        }
      ],
      "reviews": [
        {
          "id": 1,
          "product": 1,
          "order": 42,
          "user": 5,
          "user_display": "Jane",
          "rating": 5,
          "body": "Great product.",
          "is_anonymous": false,
          "created_at": "2025-02-01T12:00:00Z",
          "updated_at": "2025-02-01T12:00:00Z"
        }
      ]
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

=== "Create (staff)"

    ```
    POST /api/products/products/
    ```

    Request body: `name`, `description`, `price`, and `stock` are required; `brand`, `sku`, and `barcode` are optional (when provided, `barcode` must be unique).

    ```json
    {
      "name": "Vitamin C 1000mg",
      "description": "High-strength Vitamin C",
      "brand": 1,
      "price": "19.99",
      "cost_price": "12.00",
      "stock": 100,
      "sku": "VIT-C-1000",
      "barcode": "0123456789001",
      "image_urls": ["https://cdn.example.com/p/vit-c-1.png"],
      "image_refs": ["p/vit-c-1.png"],
      "subcategories": [1, 2],
      "meta_title": "Vitamin C 1000mg",
      "meta_description": "High-strength Vitamin C for immune support"
    }
    ```

    **Example: 201 Created**

    ```json
    {
      "id": 1,
      "name": "Vitamin C 1000mg",
      "description": "High-strength Vitamin C",
      "brand": 1,
      "brand_details": {
        "id": 1,
        "name": "Nature Made",
        "image_urls": [
          "https://cdn.example.com/brands/nature-made-logo.png",
          "https://cdn.example.com/brands/nature-made-banner.png"
        ],
        "image_refs": [
          "brands/nature-made-logo.png",
          "brands/nature-made-banner.png"
        ],
        "image_labels": ["logo", "banner"],
        "description": "Trusted wellness and supplement brand."
      },
      "price": "19.99",
      "cost_price": "12.00",
      "stock": 100,
      "sku": "VIT-C-1000",
      "barcode": "0123456789001",
      "image_urls": ["https://cdn.example.com/p/vit-c-1.png"],
      "image_refs": ["p/vit-c-1.png"],
      "subcategories": [1, 2],
      "meta_title": "Vitamin C 1000mg",
      "meta_description": "High-strength Vitamin C for immune support",
      "slug": "vitamin-c-1000mg",
      "avg_rating": null,
      "review_count": 0,
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-01-15T10:00:00Z",
      "variants": [],
      "reviews": [],
      "display_currency": "USD",
      "currency_symbol": "$"
    }
    ```

    - `avg_rating` and `review_count` are read-only; they are updated automatically when reviews are added, updated, or deleted.

    **Example: 400 Bad Request (validation)**

    ```json
    {
      "name": ["This field may not be blank."],
      "price": ["A valid number is required."],
      "description": ["This field may not be blank."]
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
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
      "brand": 1,
      "price": "21.99",
      "cost_price": "13.00",
      "stock": 80,
      "sku": "VIT-C-1000",
      "barcode": "0123456789001",
      "image_urls": ["https://cdn.example.com/p/vit-c-1.png"],
      "image_refs": ["p/vit-c-1.png"],
      "subcategories": [1],
      "meta_title": "Vitamin C 1000mg",
      "meta_description": "Updated meta description"
    }
    ```

    - `slug`, `avg_rating`, `review_count`, `created_at`, and `updated_at` are read-only. `sku` and `barcode` are optional.
    - Variants are managed via the variants endpoints (see below).

    **Example: 200 OK**

    ```json
    {
      "id": 1,
      "name": "Vitamin C 1000mg",
      "description": "Updated description",
      "brand": 1,
      "brand_details": {
        "id": 1,
        "name": "Nature Made",
        "image_urls": [
          "https://cdn.example.com/brands/nature-made-logo.png",
          "https://cdn.example.com/brands/nature-made-banner.png"
        ],
        "image_refs": [
          "brands/nature-made-logo.png",
          "brands/nature-made-banner.png"
        ],
        "image_labels": ["logo", "banner"],
        "description": "Trusted wellness and supplement brand."
      },
      "price": "21.99",
      "cost_price": "13.00",
      "stock": 80,
      "sku": "VIT-C-1000",
      "barcode": "0123456789001",
      "image_urls": ["https://cdn.example.com/p/vit-c-1.png"],
      "image_refs": ["p/vit-c-1.png"],
      "subcategories": [1],
      "meta_title": "Vitamin C 1000mg",
      "meta_description": "Updated meta description",
      "slug": "vitamin-c-1000mg",
      "avg_rating": "4.25",
      "review_count": 12,
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-02-19T14:30:00Z",
      "variants": [],
      "reviews": [],
      "display_currency": "USD",
      "currency_symbol": "$"
    }
    ```

    **Example: 400 Bad Request (validation)**

    ```json
    {
      "price": ["A valid number is required."]
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

=== "Delete (staff)"

    ```
    DELETE /api/products/products/{id}/
    ```

    **Example: 204 No Content** — Empty response body.

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

=== "Product fields (read-only for ratings)"

    | Field | Type | Description |
    | --- | --- | --- |
    | `brand` | integer or null | Brand ID assigned to the product. |
    | `brand_details` | object or null | Nested brand object returned in product responses. |
    | `avg_rating` | string (decimal) or null | Average of all review ratings (0–5). Updated when reviews change. |
    | `review_count` | integer | Number of reviews. Updated when reviews change. |
    | `reviews` | array | Up to 10 most recent reviews (see Product Reviews below). |

## Product Reviews

Reviews are attached to a **product** and shared across all its variants. They are **linked to a completed order**: only users who have purchased the product (via a fully paid, placed order containing that product) can submit a review. Rating is **0–5**. One review per user per product. The product’s `avg_rating` and `review_count` are updated automatically on every review create/update/delete.

- **Create**: Requires authentication and an `order` that belongs to you, is placed, is fully paid, and contains the product. You can submit at most one review per product.
- **user_display**: Shown as the reviewer’s **first name** (or "Customer" if missing). If the review is **anonymous** (`is_anonymous: true`), `user_display` is redacted as **"Anonymous"**.

=== "List"

    ```
    GET /api/products/product-reviews/
    GET /api/products/product-reviews/?product=1
    ```

    Optional query: `?product={id}` to filter by product.

    **Example: 200 OK**

    ```json
    [
      {
        "id": 1,
        "product": 1,
        "order": 42,
        "user": 5,
        "user_display": "Jane",
        "rating": 5,
        "body": "Great product, fast delivery.",
        "is_anonymous": false,
        "created_at": "2025-02-01T12:00:00Z",
        "updated_at": "2025-02-01T12:00:00Z"
      },
      {
        "id": 2,
        "product": 1,
        "order": 38,
        "user": 7,
        "user_display": "Anonymous",
        "rating": 4,
        "body": "Good value.",
        "is_anonymous": true,
        "created_at": "2025-02-02T09:00:00Z",
        "updated_at": "2025-02-02T09:00:00Z"
      }
    ]
    ```

    **Example: Error** — List is public; no 403.

=== "Retrieve"

    ```
    GET /api/products/product-reviews/{id}/
    ```

    **Example: 200 OK**

    ```json
    {
      "id": 1,
      "product": 1,
      "order": 42,
      "user": 5,
      "user_display": "Jane",
      "rating": 5,
      "body": "Great product, fast delivery.",
      "is_anonymous": false,
      "created_at": "2025-02-01T12:00:00Z",
      "updated_at": "2025-02-01T12:00:00Z"
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

=== "Create (authenticated purchaser)"

    ```
    POST /api/products/product-reviews/
    ```

    Requires authentication. You must have a **completed** order (status `PLACED`, fully paid) that contains the product. One review per user per product.

    ```json
    {
      "product": 1,
      "order": 42,
      "rating": 5,
      "body": "Great product.",
      "is_anonymous": false
    }
    ```

    - `product` (required): Product ID you are reviewing.
    - `order` (required): Order ID that contains this product (must be your order, placed, and fully paid).
    - `rating` (required): **0–5** (inclusive).
    - `body` (optional): Review text.
    - `is_anonymous` (optional): If `true`, `user_display` is shown as "Anonymous". Default `false`.

    **Example: 201 Created**

    ```json
    {
      "id": 1,
      "product": 1,
      "order": 42,
      "user": 5,
      "user_display": "Jane",
      "rating": 5,
      "body": "Great product.",
      "is_anonymous": false,
      "created_at": "2025-02-01T12:00:00Z",
      "updated_at": "2025-02-01T12:00:00Z"
    }
    ```

    **Example: 400 Bad Request (validation)**

    ```json
    {
      "order": "This order does not contain the selected product."
    }
    ```

    ```json
    {
      "product": "You have already reviewed this product."
    }
    ```

    **Example: 401 Unauthorized**

    ```json
    {
      "detail": "Authentication required to submit a review."
    }
    ```

=== "Update (owner or staff)"

    ```
    PUT /api/products/product-reviews/{id}/
    PATCH /api/products/product-reviews/{id}/
    ```

    Only the review owner or staff can update (e.g. `rating`, `body`, `is_anonymous`).

    ```json
    {
      "rating": 4,
      "body": "Updated review text.",
      "is_anonymous": false
    }
    ```

    **Example: 200 OK**

    ```json
    {
      "id": 1,
      "product": 1,
      "order": 42,
      "user": 5,
      "user_display": "Jane",
      "rating": 4,
      "body": "Updated review text.",
      "is_anonymous": false,
      "created_at": "2025-02-01T12:00:00Z",
      "updated_at": "2025-02-19T14:30:00Z"
    }
    ```

    **Example: 403 Forbidden (not owner and not staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

=== "Delete (owner or staff)"

    ```
    DELETE /api/products/product-reviews/{id}/
    ```

    Only the review owner or staff can delete.

    **Example: 204 No Content** — Empty response body.

    **Example: 403 Forbidden (not owner and not staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

=== "Fields"

    | Field | Type | Required (create) | Description |
    | --- | --- | --- | --- |
    | `product` | integer | Yes | Product ID. |
    | `order` | integer | Yes | Order ID; must be your order, status PLACED, fully paid, and contain the product. |
    | `rating` | integer | Yes | Rating 0–5 (inclusive). |
    | `body` | string | No | Optional review text. |
    | `is_anonymous` | boolean | No | If true, `user_display` is shown as "Anonymous". Default false. |
    | `user` | integer | No | Read-only; set from request. |
    | `user_display` | string | — | First name of the reviewer, or "Customer", or "Anonymous" if `is_anonymous`. |

=== "Example: Create review (authenticated purchaser)"

    ```bash
    curl -X POST https://api.endovillehealth.com/api/products/product-reviews/ \
      -H "Authorization: Bearer <access_token>" \
      -H "Content-Type: application/json" \
      -d '{
        "product": 1,
        "order": 42,
        "rating": 5,
        "body": "Excellent quality.",
        "is_anonymous": false
      }'
    ```

=== "Example: List reviews for a product"

    ```bash
    curl "https://api.endovillehealth.com/api/products/product-reviews/?product=1"
    ```

## Variation Attributes (e.g. Color, Size)

=== "List"

    ```
    GET /api/products/variation-attributes/
    ```

    **Example: 200 OK**

    ```json
    [
      { "id": 1, "name": "Color" },
      { "id": 2, "name": "Size" }
    ]
    ```

    **Example: Error** — List is public; no 403.

=== "Create (staff)"

    ```
    POST /api/products/variation-attributes/
    ```

    ```json
    {
      "name": "Color"
    }
    ```

    **Example: 201 Created**

    ```json
    {
      "id": 1,
      "name": "Color"
    }
    ```

    **Example: 400 Bad Request (validation)**

    ```json
    {
      "name": ["This field may not be blank."]
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

## Variation Options (e.g. Color=Red)

=== "List"

    ```
    GET /api/products/variation-options/
    ```

    **Example: 200 OK**

    ```json
    [
      { "id": 10, "attribute": 1, "attribute_name": "Color", "value": "Red" },
      { "id": 11, "attribute": 2, "attribute_name": "Size", "value": "XL" }
    ]
    ```

    **Example: Error** — List is public; no 403.

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

    **Example: 201 Created**

    ```json
    {
      "id": 10,
      "attribute": 1,
      "attribute_name": "Color",
      "value": "Red"
    }
    ```

    **Example: 400 Bad Request (validation)**

    ```json
    {
      "attribute": ["This field is required."],
      "value": ["This field may not be blank."]
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
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

    **Example: 200 OK**

    ```json
    {
      "id": 10,
      "attribute": 1,
      "attribute_name": "Color",
      "value": "Red"
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

## Variants

Variant `sku` and `barcode` are **optional**. When provided, `barcode` must be unique across all variants.

=== "List"

    ```
    GET /api/products/variants/
    GET /api/products/variants/?currency=KES
    ```

    Non-staff: `display_currency` and `currency_symbol` always included; use `?currency=CODE` to convert.

    **Example: 200 OK**

    ```json
    [
      {
        "id": 1,
        "product": 1,
        "options": [10, 11],
        "options_details": [
          { "id": 10, "attribute": 1, "attribute_name": "Color", "value": "Red" },
          { "id": 11, "attribute": 2, "attribute_name": "Size", "value": "XL" }
        ],
        "sku": "SKU-RED-XL",
        "barcode": "0123456789012",
        "price": "24.99",
        "stock": 10,
        "image_urls": ["https://cdn.example.com/p/vit-c-red-xl.png"],
        "image_refs": ["p/vit-c-red-xl.png"],
        "is_active": true,
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
        "avg_rating": "4.25",
        "review_count": 12,
        "reviews": [],
        "display_currency": "USD",
        "currency_symbol": "$"
      }
    ]
    ```

    Variants include the parent product’s `avg_rating`, `review_count`, and up to 10 `reviews` (same as on the product).

    **Example: Error** — List is public; no 403.

=== "Retrieve"

    ```
    GET /api/products/variants/{id}/
    GET /api/products/variants/{id}/?currency=KES
    ```

    Non-staff: `display_currency` and `currency_symbol` always included; use `?currency=CODE` to convert. Response includes the product’s `avg_rating`, `review_count`, and `reviews`.

    **Example: 200 OK**

    ```json
    {
      "id": 1,
      "product": 1,
      "options": [10, 11],
      "options_details": [
        { "id": 10, "attribute": 1, "attribute_name": "Color", "value": "Red" },
        { "id": 11, "attribute": 2, "attribute_name": "Size", "value": "XL" }
      ],
      "sku": "SKU-RED-XL",
      "barcode": "0123456789012",
      "price": "24.99",
      "stock": 10,
      "image_urls": ["https://cdn.example.com/p/vit-c-red-xl.png"],
      "image_refs": ["p/vit-c-red-xl.png"],
      "is_active": true,
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-01-15T10:00:00Z",
      "avg_rating": "4.25",
      "review_count": 12,
      "reviews": [
        {
          "id": 1,
          "product": 1,
          "order": 42,
          "user": 5,
          "user_display": "Jane",
          "rating": 5,
          "body": "Great product.",
          "is_anonymous": false,
          "created_at": "2025-02-01T12:00:00Z",
          "updated_at": "2025-02-01T12:00:00Z"
        }
      ],
      "display_currency": "USD",
      "currency_symbol": "$"
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

=== "Create (staff)"

    ```
    POST /api/products/variants/
    ```

    Request body: `product` is required; `options`, `sku`, `barcode`, `price`, `cost_price`, `stock`, `image_urls`, `image_refs`, `is_active` are optional. `sku` and `barcode` may be omitted or null.

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

    **Example: 201 Created**

    ```json
    {
      "id": 1,
      "product": 1,
      "options": [10, 11],
      "options_details": [
        { "id": 10, "attribute": 1, "attribute_name": "Color", "value": "Red" },
        { "id": 11, "attribute": 2, "attribute_name": "Size", "value": "XL" }
      ],
      "sku": "SKU-RED-XL",
      "barcode": "0123456789012",
      "price": "24.99",
      "cost_price": "15.00",
      "stock": 10,
      "image_urls": ["https://cdn.example.com/p/vit-c-red-xl.png"],
      "image_refs": ["p/vit-c-red-xl.png"],
      "is_active": true,
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-01-15T10:00:00Z",
      "avg_rating": "4.25",
      "review_count": 12,
      "reviews": [],
      "display_currency": "USD",
      "currency_symbol": "$"
    }
    ```

    **Example: 400 Bad Request (validation)**

    ```json
    {
      "barcode": ["product variant with this barcode already exists."],
      "product": ["This field is required."]
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
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

    - `sku` and `barcode` are optional; when provided, `barcode` must be unique.

    **Example: 200 OK**

    ```json
    {
      "id": 1,
      "product": 1,
      "options": [10, 11],
      "options_details": [
        { "id": 10, "attribute": 1, "attribute_name": "Color", "value": "Red" },
        { "id": 11, "attribute": 2, "attribute_name": "Size", "value": "XL" }
      ],
      "sku": "SKU-RED-XL",
      "barcode": "0123456789012",
      "price": "24.99",
      "cost_price": "16.00",
      "stock": 12,
      "image_urls": ["https://cdn.example.com/p/vit-c-red-xl.png"],
      "image_refs": ["p/vit-c-red-xl.png"],
      "is_active": true,
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-02-19T14:30:00Z",
      "avg_rating": "4.25",
      "review_count": 12,
      "reviews": [],
      "display_currency": "USD",
      "currency_symbol": "$"
    }
    ```

    **Example: 400 Bad Request (validation)**

    ```json
    {
      "barcode": ["product variant with this barcode already exists."]
    }
    ```

    **Example: 403 Forbidden (non-staff)**

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

    **Example: 404 Not Found**

    ```json
    {
      "detail": "Not found."
    }
    ```

## Product and variant image fields

- **`image_urls`**: Array of image URLs (display).
- **`image_refs`**: Array of storage keys/paths for the same images, in the same order as `image_urls`.

## Brand image fields

- **`image_urls`**: Array of brand image URLs.
- **`image_refs`**: Array of storage keys/paths for the same brand images, in the same order as `image_urls`.
- **`image_labels`**: Array of labels for the same brand images, in the same order as `image_urls` and `image_refs`.

## Product and variant rating fields

- **`avg_rating`**: Stored on the product; shown on product and on each variant (from the product). Decimal 0–5, or `null` if there are no reviews. Updated automatically when reviews are added, updated, or deleted.
- **`review_count`**: Number of reviews for the product; same value on product and variants.
- **`reviews`**: Array of up to 10 most recent reviews on the product; same list on product detail and on each variant (reviews are shared across variants).

## Notes

- All product endpoints are public for reads.
- All writes (create/update/delete) require a **staff** user.
- Non-staff: `display_currency` and `currency_symbol` included by default (USD); use `?currency=CODE` to convert.
- Reviews use a 0–5 rating; one review per user per product when the user is set.
