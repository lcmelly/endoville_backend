import pytest
from background_task.models import Task

from orders.background_tasks import ensure_open_stripe_payment_status_schedule
from orders.models import Order, OrderPayment, PaymentProvider, PaymentStatus, ShippingAddress
from orders.payments.stripe import sync_all_open_stripe_payments
from users.models import CustomUser


pytestmark = pytest.mark.django_db


def _order():
    user = CustomUser.objects.create_user(email="stripe-job@example.com", password="strongpass", is_active=True)
    address = ShippingAddress.objects.create(
        user=user,
        full_name="Jane Buyer",
        phone="0712345678",
        email="stripe-job@example.com",
        address_line_1="Street 1",
        city="Nairobi",
        country="Kenya",
    )
    return Order.objects.create(user=user, shipping_address=address, subtotal="10.00", total="10.00")


def test_minute_job_marks_a_paid_open_stripe_session_complete(monkeypatch):
    order = _order()
    payment = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.STRIPE,
        status=PaymentStatus.PENDING,
        amount="10.00",
        currency="USD",
        provider_payment_id="cs_test_minute",
    )
    OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.STRIPE,
        status=PaymentStatus.PENDING,
        amount="10.00",
        currency="USD",
        provider_payment_id="",
    )

    class FakeAPI:
        def __init__(self):
            pass

        def check_payment_status(self, row):
            row.status = PaymentStatus.COMPLETED
            row.provider_state = "paid"
            row.save(update_fields=["status", "provider_state", "updated_at"])
            return {"success": True, "status": row.status}

    monkeypatch.setattr("orders.payments.stripe.StripeAPI", FakeAPI)
    checked = sync_all_open_stripe_payments()
    assert checked == 1
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.COMPLETED


def test_stripe_status_job_is_scheduled_once_per_minute():
    ensure_open_stripe_payment_status_schedule()
    ensure_open_stripe_payment_status_schedule()
    rows = list(Task.objects.filter(task_name__endswith="run_open_stripe_payment_status_task"))
    assert len(rows) == 1
    assert rows[0].repeat == 60
