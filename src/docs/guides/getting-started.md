---
title: Getting started
icon: lucide/rocket
---

# Get started

The Endoville API is how the storefront creates accounts, sells products, and ships orders. You can browse products and posts without signing in. To place an order, you create an account, sign in, and send the access token with each request.

Already building the storefront? Start here, then open the page for the area you need from the home page.

## Before you start

You need three things:

- An email address that can receive a short code
- A way to send HTTP requests, such as curl or Postman
- The API base URL, `https://api.endovillehealth.com`

A short code is a one-time password, often called an OTP. We email it to you. It is not your account password.

## Create an account

Signing in takes three calls: register, activate, then sign in. You do this once. After that you reuse the access token until it expires.

### 1. Register

Open a terminal and create the account. This does not sign you in yet. We email a short code to the address you send.

```bash
curl -X POST https://api.endovillehealth.com/api/users/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@example.com",
    "first_name": "Ada",
    "last_name": "Okoye",
    "password": "a-long-password"
  }'
```

Check that inbox for the code. In these examples the code is `123456`. Yours will be different.

### 2. Activate

The account stays off until you send that code back. No token is required for this call.

```bash
curl -X POST https://api.endovillehealth.com/api/users/activate/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@example.com",
    "otp": "123456"
  }'
```

If the code expired, ask for a new one with `POST /api/users/send-otp/`. See [OTP](../api/otp.md).

### 3. Sign in

Sign in with your email and password, or with a fresh login code. Do not send both. The response includes two tokens:

- **Access token.** Send this on later requests. It lasts a few hours.
- **Refresh token.** Use it to get a new access token without signing in again.

```bash
curl -X POST https://api.endovillehealth.com/api/users/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@example.com",
    "password": "a-long-password"
  }'
```

### 4. Call a protected route

Put the access token in the `Authorization` header. The word `Bearer` and a space come before the token.

```bash
curl https://api.endovillehealth.com/api/users/me/ \
  -H "Authorization: Bearer <access_token>"
```

That call returns the profile for the person the token belongs to.

## Sign in with Google

If you already have a Google account, you can skip register and activate. `POST /api/users/google-login/` creates the account when it does not exist yet, and returns the same pair of tokens. See [Google login](../api/google-login.md).

## What to read next

| You want to | Open |
| --- | --- |
| See how the pieces fit | [Architecture](../architecture.md) |
| Load products | [Products](../api/products.md) |
| Keep a cart | [Cart](../api/cart.md) |
| Place an order | [Orders](../api/orders.md) |
