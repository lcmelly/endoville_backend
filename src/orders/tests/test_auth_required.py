import pytest
from rest_framework import status
from rest_framework.test import APIClient

from products.models import Product
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
def product():
    return Product.objects.create(
        name="P1",
        description="d",
        price="10.00",
        stock=5,
        image_urls=[],
        meta_title="",
        meta_description="",
        slug="p1",
    )


def test_create_order_requires_auth(api_client, product):
    resp = api_client.post(
        "/api/orders/orders/",
        {
            "shipping_address": {
                "full_name": "John Doe",
                "phone": "0712345678",
                "email": "john@example.com",
                "address_line_1": "Street 1",
                "address_line_2": "",
                "city": "Nairobi",
                "state": "",
                "postal_code": "",
                "country": "Kenya",
            },
            "items": [{"product": product.id, "quantity": 1}],
            "shipping_fee": "0.00",
            "notes": "",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_create_order_requires_shipping_address(api_client, user, product):
    """Placing an order without a shipping address returns 400."""
    api_client.force_authenticate(user=user)
    resp = api_client.post(
        "/api/orders/orders/",
        {
            "items": [{"product": product.id, "quantity": 1}],
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "shipping_address" in resp.json()


def test_create_payment_requires_auth(api_client):
    resp = api_client.post(
        "/api/orders/payments/",
        {"order": 1, "provider": "intasend", "method": "link"},
        format="json",
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

