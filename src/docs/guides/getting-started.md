# Getting Started

Quick start guide for using the Endoville Backend API.

## Prerequisites

- A valid email address
- Internet connection
- HTTP client (curl, Postman, or similar)

## Authentication Flow

### 1. Register

Create a new account:

```bash
POST /api/users/register/
```

You'll receive an email with an OTP code.

### 2. Activate Account

Activate your account using the OTP:

```bash
POST /api/users/activate/
```

### 3. Login

Login with your credentials and OTP:

```bash
POST /api/users/login/
```

You'll receive JWT tokens (access and refresh).

### 4. Use Access Token

Include the access token in authenticated requests:

```bash
Authorization: Bearer <access_token>
```

## Quick Example

```bash
# 1. Register
curl -X POST https://api.endovillehealth.com/api/users/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "password": "securepassword123"
  }'

# 2. Check email for OTP (e.g., "123456")

# 3. Activate
curl -X POST https://api.endovillehealth.com/api/users/activate/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "otp": "123456"
  }'

# 4. Login
curl -X POST https://api.endovillehealth.com/api/users/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123",
    "otp": "654321"
  }'

# Response includes access token - use it for authenticated requests
```

## Alternative: Google Login

You can also login using Google OAuth:

```bash
POST /api/users/google-login/
```

No registration or activation needed - account is created automatically.

