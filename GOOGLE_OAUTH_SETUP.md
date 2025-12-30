# Google OAuth Setup Guide

This guide will help you configure Google OAuth credentials for testing and production.

## Step 1: Create OAuth Credentials in Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the required APIs:
   - Go to "APIs & Services" → "Library"
   - Search for "Google Identity API" or "Google+ API"
   - Enable it

## Step 2: Create OAuth 2.0 Client ID

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth 2.0 Client ID"
3. If prompted, configure the OAuth consent screen first:
   - Choose "External" (unless you have a Google Workspace)
   - Fill in app information (App name, User support email, Developer contact)
   - Add scopes: `email`, `profile`
   - Add test users if needed (for testing before verification)
   - Save and continue

4. Back in Credentials, create OAuth 2.0 Client ID:
   - Application type: "Web application"
   - Name: "Endoville Backend" (or your preferred name)

## Step 3: Configure Authorized Redirect URIs

**Critical Step**: You must add the correct redirect URIs.

### For Testing with OAuth Playground:
Add this URI:
```
https://developers.google.com/oauthplayground
```

### For Local Development (if using web flow):
```
http://localhost:8000
http://127.0.0.1:8000
```

### For Production:
```
https://yourdomain.com
https://yourdomain.com/accounts/google/login/callback/
```

**Important Notes:**
- Each URI must be on a separate line
- Use exact URIs (including http/https and port numbers)
- No trailing slashes unless required by your app
- For OAuth Playground, the URI must be exactly: `https://developers.google.com/oauthplayground`

## Step 4: Save Credentials

1. Click "Create"
2. Copy the **Client ID** and **Client Secret**
3. Add them to your `.env` file:

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

## Step 5: Verify Configuration

After saving, your OAuth client configuration should look like:

```
Application type: Web application
Name: Endoville Backend
Authorized JavaScript origins: (optional, can leave empty for API-only)
Authorized redirect URIs:
  - https://developers.google.com/oauthplayground
  - http://localhost:8000 (if needed)
```

## Common Issues and Solutions

### Error: "redirect_uri_mismatch"

**Cause**: The redirect URI in your OAuth request doesn't match any authorized URI.

**Solution**:
1. Check that `https://developers.google.com/oauthplayground` is in your authorized redirect URIs
2. Make sure there are no extra spaces or typos
3. If using OAuth Playground, make sure you clicked the gear icon and entered your credentials
4. Try clearing your browser cache and cookies

### Error: "invalid_client"

**Cause**: Client ID or Client Secret is incorrect.

**Solution**:
1. Double-check your `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`
2. Make sure there are no extra spaces
3. Regenerate credentials if needed

### Error: "access_denied"

**Cause**: User denied permissions or app is in testing mode and user is not a test user.

**Solution**:
1. Add your Google account as a test user in OAuth consent screen
2. Or publish your app (requires verification for production)

## Testing the Configuration

1. Go to [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
2. Click the gear icon (⚙️) → "Use your own OAuth credentials"
3. Enter your Client ID and Client Secret
4. Select scopes: `userinfo.email`, `userinfo.profile`
5. Click "Authorize APIs"
6. If successful, you'll be redirected back to the playground (no error!)
7. Click "Exchange authorization code for tokens"
8. Copy the access token

If you see the "redirect_uri_mismatch" error, go back to Step 3 and verify the redirect URI is correctly configured.

## Production Setup

For production:
1. Add your production domain to authorized redirect URIs
2. Complete OAuth consent screen verification (required for production)
3. Update `ALLOWED_HOSTS` in Django settings
4. Use HTTPS in production (required by Google OAuth)

