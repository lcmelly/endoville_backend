import pytest
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import ShippingAddress
from users.models import CustomUser


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def test_staff_customer_list_includes_addresses_and_hides_staff(api_client):
    staff = CustomUser.objects.create_user(
        email="desk@example.com",
        password="strongpass",
        first_name="Ada",
        last_name="Staff",
        is_active=True,
        is_staff=True,
    )
    shopper = CustomUser.objects.create_user(
        email="ada@example.com",
        password="strongpass",
        first_name="Ada",
        last_name="Buyer",
        phone="+254700000001",
        is_active=True,
    )
    ShippingAddress.objects.create(
        user=shopper,
        full_name="Ada Buyer",
        phone="0712345678",
        email="ada@example.com",
        address_line_1="Street 1",
        city="Nairobi",
        country="Kenya",
    )
    ShippingAddress.objects.create(
        user=shopper,
        full_name="Ada Buyer",
        phone="0712345678",
        email="ada@example.com",
        address_line_1="Street 1",
        city="Nairobi",
        country="Kenya",
    )
    ShippingAddress.objects.create(
        user=shopper,
        full_name="Ada Buyer",
        phone="0712345678",
        email="ada@example.com",
        address_line_1="Lane 2",
        city="Mombasa",
        country="Kenya",
    )
    ShippingAddress.objects.create(
        user=staff,
        full_name="Ada Staff",
        phone="0700000000",
        email="desk@example.com",
        address_line_1="Office",
        city="Nairobi",
        country="Kenya",
    )
    CustomUser.objects.create_user(
        email="new@example.com",
        password="strongpass",
        first_name="New",
        last_name="Shopper",
        is_active=False,
    )

    api_client.force_authenticate(user=shopper)
    forbidden = api_client.get("/api/users/customers/")
    assert forbidden.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=staff)
    response = api_client.get("/api/users/customers/")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    ids = [row["id"] for row in body]
    assert shopper.id in ids
    assert staff.id not in ids

    customer = next(row for row in body if row["id"] == shopper.id)
    assert customer["email"] == "ada@example.com"
    assert customer["phone"] == "+254700000001"
    assert customer["first_name"] == "Ada"
    assert [address["address_line_1"] for address in customer["addresses"]] == ["Lane 2", "Street 1"]
    assert customer["addresses"][1]["city"] == "Nairobi"

    inactive = next(row for row in body if row["email"] == "new@example.com")
    assert inactive["is_active"] is False
    assert inactive["addresses"] == []
