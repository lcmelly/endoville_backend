import pytest
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import Order, PaymentCredentials, PaymentProvider, ShippingAddress, Shipment
from users.models import CustomUser


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def staff_user():
    return CustomUser.objects.create_user(
        email="staff@example.com",
        password="strongpass",
        is_active=True,
        is_staff=True,
    )


@pytest.fixture
def user():
    return CustomUser.objects.create_user(
        email="user@example.com",
        password="strongpass",
        is_active=True,
    )


@pytest.fixture
def order(user):
    addr = ShippingAddress.objects.create(
        user=user,
        full_name="John Doe",
        phone="0712345678",
        email="john@example.com",
        address_line_1="Street 1",
        address_line_2="",
        city="Nairobi",
        state="",
        postal_code="",
        country="Kenya",
    )
    o = Order.objects.create(user=user, shipping_address=addr, subtotal="0", total="10.00")
    Shipment.objects.create(order=o)
    return o


def test_payment_credentials_staff_only(api_client, user, staff_user):
    api_client.force_authenticate(user=user)
    resp = api_client.post(
        "/api/orders/payment-credentials/",
        {
            "provider": "intasend",
            "environment": "sandbox",
            "api_key": "pk",
            "private_key": "sk",
            "is_active": True,
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        "/api/orders/payment-credentials/",
        {
            "provider": "intasend",
            "environment": "sandbox",
            "api_key": "pk",
            "private_key": "sk",
            "is_active": True,
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    # private key should never be returned
    assert "private_key" not in data
    assert data["has_private_key"] is True
    assert PaymentCredentials.objects.filter(provider=PaymentProvider.INTASEND, is_active=True).exists()


def test_staff_can_update_shipment_and_add_event(api_client, staff_user, order):
    shipment = order.shipment
    api_client.force_authenticate(user=staff_user)

    resp = api_client.patch(
        f"/api/orders/staff/shipments/{shipment.id}/",
        {"status": "DISPATCHED", "carrier": "DHL", "tracking_number": "TRK-1"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK

    resp = api_client.post(
        "/api/orders/staff/shipment-events/",
        {"shipment": shipment.id, "status": "DISPATCHED", "message": "Dispatched", "location": "Warehouse"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED


def test_staff_can_update_payment_status_and_amount(api_client, staff_user, order):
    from orders.models import OrderPayment, PaymentProvider

    payment = OrderPayment.objects.create(order=order, provider=PaymentProvider.CASH, amount="10.00", currency="KES")

    api_client.force_authenticate(user=staff_user)
    resp = api_client.patch(
        f"/api/orders/staff/payments/{payment.id}/",
        {"status": "completed", "amount": "9.50"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK


def test_order_is_fully_paid_ticks_and_unticks_on_payment_delete(api_client, staff_user, order):
    """
    If completed payments sum >= order.total, order.is_fully_paid becomes True.
    If a payment is deleted and sum drops below total, it becomes False.
    """
    from orders.models import OrderPayment, PaymentProvider, PaymentStatus

    api_client.force_authenticate(user=staff_user)

    # Create 2 completed payments totaling the order total (10.00)
    p1 = OrderPayment.objects.create(
        order=order, provider=PaymentProvider.CASH, status=PaymentStatus.COMPLETED, amount="5.00", currency="KES"
    )
    p2 = OrderPayment.objects.create(
        order=order, provider=PaymentProvider.CASH, status=PaymentStatus.COMPLETED, amount="5.00", currency="KES"
    )

    order.refresh_from_db()
    assert order.is_fully_paid is True

    # Soft-delete one payment, order should become not fully paid
    resp = api_client.delete(f"/api/orders/staff/payments/{p2.id}/")
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    order.refresh_from_db()
    assert order.is_fully_paid is False

    p2.refresh_from_db()
    assert p2.is_deleted is True
    assert p2.deleted_by_id == staff_user.id


def test_non_staff_cannot_update_staff_payment_endpoint(api_client, user, order):
    from orders.models import OrderPayment, PaymentProvider

    payment = OrderPayment.objects.create(order=order, provider=PaymentProvider.CASH, amount="10.00", currency="KES")
    api_client.force_authenticate(user=user)
    resp = api_client.patch(
        f"/api/orders/staff/payments/{payment.id}/",
        {"status": "completed"},
        format="json",
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_is_fully_paid_uses_only_completed_and_not_deleted(api_client, staff_user, order):
    """
    - pending/failed payments should not count
    - deleted payments should not count
    - status/amount changes should trigger reevaluation
    """
    from orders.models import OrderPayment, PaymentProvider, PaymentStatus

    # pending payment (should not count)
    p1 = OrderPayment.objects.create(
        order=order, provider=PaymentProvider.CASH, status=PaymentStatus.PENDING, amount="10.00", currency="KES"
    )
    order.refresh_from_db()
    assert order.is_fully_paid is False

    # update to completed should trigger tick
    p1.status = PaymentStatus.COMPLETED
    p1.save(update_fields=["status", "updated_at"])
    order.refresh_from_db()
    assert order.is_fully_paid is True

    # soft delete should untick (deleted payments excluded)
    api_client.force_authenticate(user=staff_user)
    resp = api_client.delete(f"/api/orders/staff/payments/{p1.id}/")
    assert resp.status_code == status.HTTP_204_NO_CONTENT
    order.refresh_from_db()
    assert order.is_fully_paid is False
