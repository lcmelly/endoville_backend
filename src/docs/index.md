# Endoville Backend API Documentation

Welcome to the Endoville Backend API Documentation.

## Overview

This API provides user management, authentication, and account activation functionality.

## Getting Started

### Base URL

```
https://api.endovillehealth.com/api/users/
```

### Authentication

Most endpoints require JWT authentication. You'll receive access and refresh tokens after successful login.

### API Endpoints

- [User Registration](api/registration.md)
- [Account Activation](api/activation.md)
- [OTP Management](api/otp.md)
- [Authentication](api/authentication.md)
- [Google OAuth Login](api/google-login.md)

## Response Format

All responses are in JSON format.

### Success Response

```json
{
  "message": "Operation successful",
  "data": { ... }
}
```

### Error Response

```json
{
  "field_name": ["Error message"],
  "non_field_errors": ["General error message"]
}
```

## Status Codes

- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication required
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

