# User Profile

Get and update the currently authenticated user's profile.

=== "Endpoint"

    ```
    GET /api/users/me/
    PATCH /api/users/me/
    ```

=== "Authentication"

    JWT required.

=== "Editable Fields"

    | Field | Type | Required | Description |
    |-------|------|----------|-------------|
    | `first_name` | string | No | User first name |
    | `last_name` | string | No | User last name |
    | `image_url` | string | No | Profile image URL |
    | `gender` | string | No | `M`, `F`, `O`, or `N` |
    | `date_of_birth` | string | No | Date in `YYYY-MM-DD` format |

=== "Read-only (for now)"

    | Field | Type | Description |
    |-------|------|-------------|
    | `email` | string | Cannot be changed via this endpoint |
    | `phone` | string | Cannot be changed via this endpoint |

## Responses

=== "Success (200 OK)"

    ```json
    {
      "id": 1,
      "email": "user@example.com",
      "phone": "+254712345678",
      "first_name": "John",
      "last_name": "Doe",
      "image_url": "https://cdn.example.com/u/1.png",
      "gender": "M",
      "date_of_birth": "1998-02-25",
      "created_at": "2026-01-19T10:00:00Z",
      "updated_at": "2026-01-19T10:10:00Z"
    }
    ```

=== "Error (401 Unauthorized)"

    ```json
    {
      "detail": "Authentication credentials were not provided."
    }
    ```

## Example Request

```bash
curl -X PATCH https://api.endovillehealth.com/api/users/me/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jane",
    "last_name": "Doe",
    "image_url": "https://cdn.example.com/u/1-new.png",
    "gender": "F",
    "date_of_birth": "1998-02-25"
  }'
```
