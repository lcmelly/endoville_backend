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
def admin_user():
    return CustomUser.objects.create_superuser(email="admin@example.com", password="strongpass")


def test_admin_can_add_a_staff_user_with_selected_roles(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    created = api_client.post(
        "/api/users/staff/",
        {
            "email": "ship@example.com",
            "password": "strongpass",
            "first_name": "Sam",
            "roles": ["Shipping"],
        },
        format="json",
    )
    assert created.status_code == status.HTTP_201_CREATED
    assert created.json()["roles"] == ["Shipping"]
    assert created.json()["is_staff"] is True
    assert created.json()["is_superuser"] is False

    shipper = CustomUser.objects.get(email="ship@example.com")
    api_client.force_authenticate(user=shipper)
    who = api_client.get("/api/users/is-staff/")
    assert who.json()["roles"] == ["Shipping"]
    assert api_client.get("/api/orders/staff/shipments/").status_code == status.HTTP_200_OK
    assert api_client.get("/api/orders/staff/payments/").status_code == status.HTTP_403_FORBIDDEN
    assert api_client.post("/api/users/staff/", {"email": "x@example.com"}, format="json").status_code == (
        status.HTTP_403_FORBIDDEN
    )

    product = Product.objects.create(name="Serum", description="d", price="10.00", slug="role-serum")
    denied = api_client.patch(f"/api/products/products/{product.id}/", {"stock": 4}, format="json")
    assert denied.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=admin_user)
    updated = api_client.patch(
        f"/api/users/staff/{shipper.id}/",
        {"roles": ["Shipping", "Stock"]},
        format="json",
    )
    assert updated.status_code == status.HTTP_200_OK
    assert updated.json()["roles"] == ["Shipping", "Stock"]

    api_client.force_authenticate(user=shipper)
    allowed = api_client.patch(f"/api/products/products/{product.id}/", {"stock": 4}, format="json")
    assert allowed.status_code == status.HTTP_200_OK


def test_staff_cannot_add_staff_users(api_client):
    staff = CustomUser.objects.create_user(
        email="clerk@example.com", password="strongpass", is_active=True, is_staff=True
    )
    api_client.force_authenticate(user=staff)
    resp = api_client.get("/api/users/staff/")
    assert resp.status_code == status.HTTP_403_FORBIDDEN
