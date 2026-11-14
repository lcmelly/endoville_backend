---
title: Staff changes
icon: lucide/scroll-text
---

# Staff changes

Staff changes to an order, a payment, a price, or a refund are stored. Each row names the staff user, the action, the record, and the values before and after.

A shopper action is not stored. A payment provider callback is not stored, because no staff user is on that request.

## Read the log

```
GET /api/users/staff-changes/
```

Staff only. A shopper receives 403.

| Query | Meaning |
| --- | --- |
| `target_type` | `order`, `payment`, `refund`, `product`, or `variant` |
| `order_id` | Rows tied to that order |
| `action` | One action name from the table below |
| `limit` | How many rows to return. The default is 100 and the most is 500 |

Newest rows come first.

```json
[
  {
    "id": 1,
    "actor_id": 4,
    "actor_email": "staff@example.com",
    "action": "order.status_changed",
    "target_type": "order",
    "target_id": "18",
    "order_id": 18,
    "summary": "Order #18 status PAYMENT_PENDING -> PROCESSING",
    "changes": {"status": {"from": "PAYMENT_PENDING", "to": "PROCESSING"}},
    "created_at": "2026-10-24T22:00:00Z"
  }
]
```

## What is stored

| Action | When |
| --- | --- |
| `order.status_changed` | Staff change the order status, a shipment step moves the order, or a payment moves it to processing |
| `order.line_confirmed` | Staff confirm a line will ship |
| `order.line_removed` | Staff mark a line unavailable. The line stays on the order and drops out of the total |
| `order.line_replaced` | Staff replace a line. The original stays, and a new confirmed line is what ships |
| `payment.recorded` | Staff record a payment |
| `payment.status_changed` | A staff action changes a payment status, including a refund or cancelling an unpaid order |
| `refund.recorded` | A refund row is created |
| `refund.status_changed` | A refund moves from initiated to completed |
| `product.price_changed` | Staff change a product price or cost price |
| `variant.price_changed` | Staff change a variant price or cost price |

A stock-only edit is not stored. The same list is in Django admin under Staff change logs, and those rows cannot be edited there.
