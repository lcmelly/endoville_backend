# Blogs

Manage blog posts, authors, and comments.

Base path: `/api/blogs/`

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

=== "Retrieve"

    ```
    GET /api/blogs/authors/{id}/
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
      "bio": "Brief bio..."
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
      "bio": "Updated bio..."
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
      "content": "Post body...",
      "excerpt": "SEO description up to 160 chars",
      "featured_image_ref": "s3://bucket/key",
      "featured_image_alt": "alt text",
      "featured_image_title": "image title",
      "meta_keywords": "health,wellness",
      "is_published": true
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

=== "Delete (owner or staff)"

    ```
    DELETE /api/blogs/comments/{id}/
    ```

=== "Notes"

- Unauthenticated users can only read posts and comments.
- Non-staff authenticated users can create comments; they may delete only their own comments.
- Only staff can create, update, or delete authors and posts, and only staff can edit comments.
