# Google OAuth Login

Login or sign up using Google OAuth.

=== "Endpoint"

    ```
    POST /api/users/google-login/
    ```

=== "Authentication"

    No authentication required (to get tokens).

=== "Request Body"

    ```json
    {
      "access_token": "ya29.a0AfH6SMC..."
    }
    ```

=== "Fields"

    | Field | Type | Required | Description |
    |-------|------|----------|-------------|
    | `access_token` | string | Yes | Google OAuth access token |

## Response

=== "Success (200 OK)"

    ```json
    {
      "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
      "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
      "user": {
        "id": 1,
        "email": "user@gmail.com",
        "first_name": "John",
        "last_name": "Doe",
        "is_active": true
      }
    }
    ```

=== "Error (400 Bad Request)"

    ```json
    {
      "access_token": ["This field is required."]
    }
    ```

    ```json
    {
      "non_field_errors": ["Invalid Google access token."]
    }
    ```

## Error Cases

- **Missing Token**: `access_token` field is required
- **Invalid Token**: Google access token is invalid or expired
- **No Email**: Google account doesn't have an email address
- **API Error**: Error communicating with Google API

## How It Works

1. Client obtains Google OAuth access token from Google
2. Client sends the access token to this endpoint
3. Server verifies the token with Google API
4. Server creates or links the user account
5. Server returns JWT tokens for authentication

## Getting Google Access Token

### Frontend (JavaScript)

```javascript
// Using Google Sign-In SDK
google.accounts.oauth2.initTokenClient({
  client_id: 'YOUR_GOOGLE_CLIENT_ID',
  scope: 'email profile',
  callback: (response) => {
    const accessToken = response.access_token;
    // Send accessToken to /api/users/google-login/
  }
}).requestAccessToken();
```

### OAuth Playground (Testing)

1. Go to [Google OAuth Playground](https://developers.google.com/oauthplayground/)
2. Select "Google OAuth2 API v2" → "userinfo.email" and "userinfo.profile"
3. Authorize and exchange for tokens
4. Use the access token in your API request

## Notes

- If the user doesn't exist, a new account will be created automatically
- The account is automatically activated (`is_active=True`)
- If a user with the same email exists, the Google account will be linked
- JWT tokens work the same as regular email/password login
- The Google access token is only used for verification, not stored

## Example Request

```bash
curl -X POST https://api.endovillehealth.com/api/users/google-login/ \
  -H "Content-Type: application/json" \
  -d '{
    "access_token": "ya29.a0AfH6SMC..."
  }'
```
