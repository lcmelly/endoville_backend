# Blogs

Manage blog posts, authors, and comments.

=== "Base URL"

    ```
    /api/blogs/
    ```

=== "Authentication"

    - Reads are public.
    - Writes depend on staff/ownership rules below.

## Permissions Summary

| Resource | Read | Create | Update | Delete |
| --- | --- | --- | --- | --- |
| Authors | Anyone | Staff only | Staff only | Staff only |
| Posts | Anyone | Staff only | Staff only | Staff only |
| Comments | Anyone | Authenticated users | Staff only | Staff or comment owner |

## Authors

=== "List"

    ```
    GET /api/blogs/authors/
    ```

    Success (200 OK):

    ```json
    [
      {
        "id": 1,
        "name": "Dr. Jane Doe",
        "title": "Chief Medical Officer",
        "email": "jane@example.com",
        "bio": "Brief bio...",
        "image_url": "https://cdn.example.com/authors/jane.png",
        "image_ref": "authors/jane.png",
        "image_alt": "Dr. Jane Doe",
        "image_title": "Dr. Jane Doe",
        "created_at": "2026-01-19T10:00:00Z",
        "updated_at": "2026-01-19T10:00:00Z"
      }
    ]
    ```

=== "Retrieve"

    ```
    GET /api/blogs/authors/{id}/
    ```

    Success (200 OK) includes nested `posts`:

    ```json
    {
      "id": 1,
      "name": "Dr. Jane Doe",
      "title": "Chief Medical Officer",
      "email": "jane@example.com",
      "bio": "Brief bio...",
      "image_url": "https://cdn.example.com/authors/jane.png",
      "image_ref": "authors/jane.png",
      "image_alt": "Dr. Jane Doe",
      "image_title": "Dr. Jane Doe",
      "created_at": "2026-01-19T10:00:00Z",
      "updated_at": "2026-01-19T10:00:00Z",
      "posts": [
        {
          "id": 10,
          "title": "Healthy Living Tips",
          "slug": "healthy-living-tips",
          "is_published": true,
          "views": 12,
          "created_at": "2026-01-19T10:00:00Z",
          "updated_at": "2026-01-19T10:00:00Z"
        }
      ]
    }
    ```

=== "Create (staff)"

    ```
    POST /api/blogs/authors/
    ```

    ```json
    {
      "name": "Dr. Jane Doe",
      "title": "Chief Medical Officer",
      "email": "jane@example.com",
      "bio": "Brief bio...",
      "image_url": "https://cdn.example.com/authors/jane.png",
      "image_ref": "authors/jane.png",
      "image_alt": "Dr. Jane Doe",
      "image_title": "Dr. Jane Doe"
    }
    ```

    Error (403 Forbidden) if not staff:

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

=== "Update (staff)"

    ```
    PUT /api/blogs/authors/{id}/
    PATCH /api/blogs/authors/{id}/
    ```

    ```json
    {
      "name": "Dr. Jane Doe",
      "title": "Chief Medical Officer",
      "email": "jane@example.com",
      "bio": "Updated bio...",
      "image_url": "https://cdn.example.com/authors/jane.png",
      "image_ref": "authors/jane.png",
      "image_alt": "Dr. Jane Doe",
      "image_title": "Dr. Jane Doe"
    }
    ```

    - `PUT` expects the full object (all writable fields).
    - `PATCH` can send only the fields to change.

=== "Delete (staff)"

    ```
    DELETE /api/blogs/authors/{id}/
    ```

## Posts

=== "List"

    ```
    GET /api/blogs/posts/
    ```

    Success (200 OK):

    ```json
    [
      {
        "id": 10,
        "title": "Healthy Living Tips",
        "slug": "healthy-living-tips",
        "author": 1,
        "author_name": "Dr. Jane Doe",
        "content": "Post body...",
        "excerpt": "SEO description up to 160 chars",
        "featured_image_ref": "",
        "featured_image_alt": "",
        "featured_image_title": "",
        "meta_keywords": "health,wellness",
        "is_published": true,
        "views": 12,
        "created_at": "2026-01-19T10:00:00Z",
        "updated_at": "2026-01-19T10:00:00Z"
      }
    ]
    ```

=== "Retrieve"

    ```
    GET /api/blogs/posts/{id}/
    ```

=== "Create (staff)"

    ```
    POST /api/blogs/posts/
    ```

    ```json
    {
      "title": "Healthy Living Tips",
      "author": 1,
      "subcategories": [1, 2],
      "related_products": [1, 5, 8],
      "content": "Post body...",
      "excerpt": "SEO description up to 160 chars",
      "featured_image_ref": "s3://bucket/key",
      "featured_image_alt": "alt text",
      "featured_image_title": "image title",
      "meta_keywords": "health,wellness",
      "is_published": true
    }
    ```

    Error (401 Unauthorized) if not authenticated:

    ```json
    {
      "detail": "Authentication credentials were not provided."
    }
    ```

    Error (403 Forbidden) if authenticated but not staff:

    ```json
    {
      "detail": "You do not have permission to perform this action."
    }
    ```

=== "Update (staff)"

    ```
    PUT /api/blogs/posts/{id}/
    PATCH /api/blogs/posts/{id}/
    ```

    ```json
    {
      "title": "Healthy Living Tips (Updated)",
      "author": 1,
      "subcategories": [1, 2],
      "related_products": [1, 5, 8],
      "content": "Revised post body...",
      "excerpt": "Updated SEO description",
      "featured_image_ref": "s3://bucket/new-key",
      "featured_image_alt": "new alt text",
      "featured_image_title": "new image title",
      "meta_keywords": "health,wellness,updated",
      "is_published": true
    }
    ```

    - `PUT` expects the full object (all writable fields).
    - `PATCH` can send only the fields to change.

=== "Delete (staff)"

    ```
    DELETE /api/blogs/posts/{id}/
    ```

## Comments

=== "List"

    ```
    GET /api/blogs/comments/
    GET /api/blogs/comments/?post={post_id}
    ```

    Success (200 OK):

    ```json
    [
      {
        "id": 100,
        "post": 10,
        "author": 1,
        "author_display": "John Doe",
        "content": "Great article!",
        "created_at": "2026-01-19T10:05:00Z",
        "updated_at": "2026-01-19T10:05:00Z"
      }
    ]
    ```

=== "Retrieve"

    ```
    GET /api/blogs/comments/{id}/
    ```

=== "Create (authenticated)"

    ```
    POST /api/blogs/comments/
    ```

    ```json
    {
      "post": 1,
      "content": "Great article!"
    }
    ```

    Error (401 Unauthorized) if not authenticated:

    ```json
    {
      "detail": "Authentication credentials were not provided."
    }
    ```

=== "Delete (owner or staff)"

    ```
    DELETE /api/blogs/comments/{id}/
    ```

## Notes

- Unauthenticated users can only read posts and comments.
- Non-staff authenticated users can create comments; they may delete only their own comments.
- Only staff can create/update/delete authors and posts, and only staff can edit comments.

## Categories & Subcategories

Blogs support categories and subcategories:

- Categories:
  - `GET /api/blogs/categories/` (public)
  - Staff CRUD at `/api/blogs/categories/{id}/`
- Subcategories:
  - `GET /api/blogs/subcategories/` (public)
  - Staff CRUD at `/api/blogs/subcategories/{id}/`

A post can belong to **multiple** subcategories using the `subcategories` field on the post endpoints.
