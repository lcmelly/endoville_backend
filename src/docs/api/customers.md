---
title: Customers
icon: lucide/users
---

# Customers

Staff can read every customer and the shipping addresses saved for them.

A customer is an account that is not staff. Each address comes from a shipping address on that person's orders. The same address saved more than once is returned once, and the newest copy is kept. A customer with no orders has an empty `addresses` list.

## List customers

```
GET /api/users/customers/
```

Staff only. A shopper receives 403.

```json
[
  {
    "id": 12,
    "email": "ada@example.com",
    "phone": "+254700000001",
    "first_name": "Ada",
    "last_name": "Buyer",
    "is_active": true,
    "created_at": "2026-01-19T10:00:00Z",
    "addresses": [
      {
        "id": 40,
        "full_name": "Ada Buyer",
        "phone": "0712345678",
        "email": "ada@example.com",
        "address_line_1": "Lane 2",
        "address_line_2": "",
        "city": "Mombasa",
        "state": "",
        "postal_code": "",
        "country": "Kenya"
      }
    ]
  }
]
```

Customers are ordered by first name, then last name, then email. Addresses on a customer are newest first.
