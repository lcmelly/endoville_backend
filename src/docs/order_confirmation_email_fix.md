# Order Confirmation Email Fix

## Problem
Order confirmation emails were being sent prematurely:
- Sent when order was created (before payment)
- Sent when payment was initiated (pending/processing status)
- Not verifying payment completion before sending
- Customers received confirmation emails even if they hadn't paid

## Solution
Emails are now sent ONLY when payment status becomes COMPLETED.

## Changes Made

### 1. orders/emails.py
**Added payment verification:**
```python
# Only send email if order has at least one completed payment
has_completed_payment = order.payments.filter(
    status=PaymentStatus.COMPLETED,
    is_deleted=False
).exists()
if not has_completed_payment:
    logger.info("Order confirmation email skipped; no completed payment for order %s.", order.id)
    return False
```

### 2. orders/models.py (OrderPayment.save)
**Added email trigger on payment completion:**
```python
def save(self, *args, **kwargs):
    # Track if status is changing to COMPLETED
    is_newly_completed = False
    if self.pk:
        try:
            old_payment = OrderPayment.objects.get(pk=self.pk)
            if old_payment.status != PaymentStatus.COMPLETED and self.status == PaymentStatus.COMPLETED:
                is_newly_completed = True
        except OrderPayment.DoesNotExist:
            pass

    super().save(*args, **kwargs)
    self._sync_order_paid_flag()

    # Send confirmation email when payment is completed
    if is_newly_completed:
        from django.db import transaction
        from .emails import send_order_confirmation_email
        transaction.on_commit(lambda: send_order_confirmation_email(self.order_id))
```

### 3. orders/serializers.py
**Removed email trigger from order creation:**
- Line 252: Removed `transaction.on_commit(lambda: send_order_confirmation_email(order.id))`
- Added comment explaining emails are sent on payment completion

### 4. orders/views.py
**Removed email triggers from payment creation:**
- Removed `_queue_confirmation_email()` helper method
- Removed email trigger from 3 locations:
  - Line 213: Reusing existing payment link
  - Line 227: Manual payments (cash/other)
  - Line 288: All other payment provider workflows
- Removed unused import of `send_order_confirmation_email`

## Email Flow (New Behavior)

1. **Order Created** → ❌ No email sent
2. **Payment Initiated** (pending/processing) → ❌ No email sent
3. **Payment Completed** → ✅ **Confirmation email sent**

### When Payment Becomes COMPLETED:
- Stripe webhook (checkout.session.completed)
- IntaSend status check (check_payment_status)
- Manual staff update via admin panel
- Direct status update via API

## Email Content Verification
The email now includes:
- Order details with COMPLETED payment status
- Payment invoice/reference from the completed payment
- Accurate payment provider information
- All order items and shipping details

## Testing
Updated tests to verify:
- ✅ Email sent only when payment is COMPLETED
- ✅ Email NOT sent when order is created
- ✅ Email NOT sent when payment is initiated
- ✅ Email includes correct COMPLETED payment details
- ✅ Email skipped if no completed payment exists

## Benefits
1. **Accuracy**: Customers only receive confirmation after successful payment
2. **Trust**: No misleading emails for unpaid orders
3. **Payment Details**: Email shows actual completed payment information
4. **Consistency**: Same behavior across all payment providers (IntaSend, Stripe, Cash, etc.)
