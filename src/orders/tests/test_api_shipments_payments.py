import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import Order, OrderPayment, PaymentProvider, ShippingAddress
from users.models import CustomUser


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return CustomUser.objects.create_user(
        email="user@example.com",
        password="strongpass",
        is_active=True,
    )


@pytest.fixture
def other_user():
    return CustomUser.objects.create_user(
        email="other@example.com",
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
    return Order.objects.create(user=user, shipping_address=addr, subtotal="0", total="10.00")


def test_urls_resolve():
    assert reverse("orders:order-list") == "/api/orders/orders/"
    assert reverse("orders:shipment-list") == "/api/orders/shipments/"
    assert reverse("orders:payment-list") == "/api/orders/payments/"


def test_shipment_list_requires_auth(api_client):
    resp = api_client.get("/api/orders/shipments/")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_payment_list_requires_auth(api_client):
    resp = api_client.get("/api/orders/payments/")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_payment_create_owner_only(api_client, order, other_user):
    api_client.force_authenticate(user=other_user)
    resp = api_client.post(
        "/api/orders/payments/",
        {"order": order.id, "provider": "intasend", "method": "link"},
        format="json",
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_payment_create_calls_provider_client(monkeypatch, api_client, order, user):
    """
    Avoid real SDK calls by monkeypatching IntaSendAPI used by the view.
    """

    class DummyIntaSend:
        def create_payment_link(self, payment, phone_number=None, email=None):
            payment.checkout_url = "https://example.com/pay"
            payment.save(update_fields=["checkout_url", "updated_at"])
            return {"success": True, "payment_url": payment.checkout_url}

    import orders.payments.intasend as intasend_mod

    monkeypatch.setattr(intasend_mod, "IntaSendAPI", lambda: DummyIntaSend())

    api_client.force_authenticate(user=user)
    resp = api_client.post(
        "/api/orders/payments/",
        {"order": order.id, "provider": "intasend", "method": "link"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["provider"] == PaymentProvider.INTASEND
    assert data["checkout_url"] == "https://example.com/pay"
    assert OrderPayment.objects.filter(id=data["id"], order=order).exists()


def test_payment_create_cash_manual(api_client, order, user):
    api_client.force_authenticate(user=user)
    resp = api_client.post(
        "/api/orders/payments/",
        {"order": order.id, "provider": "cash", "method": "manual"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["provider"] == "cash"


def test_payment_create_rejected_if_order_fully_paid(api_client, order, user):
    """
    Trying to create a payment for a fully paid order should return an error.
    """
    from orders.models import OrderPayment, PaymentProvider, PaymentStatus

    # Mark the order as fully paid via a completed payment
    OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.CASH,
        status=PaymentStatus.COMPLETED,
        amount=order.total,
        currency="KES",
    )
    order.refresh_from_db()
    assert order.is_fully_paid is True

    api_client.force_authenticate(user=user)
    resp = api_client.post(
        "/api/orders/payments/",
        {"order": order.id, "provider": "cash", "method": "manual"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST

