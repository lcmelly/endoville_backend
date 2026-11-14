import pytest
from django.contrib.auth.models import Group
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import Warehouse
from users.models import CustomUser

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def warehouse():
    return Warehouse.objects.create(
        code="WH-1",
        name="Receiving warehouse",
        phone="7012033251",
        address_line_1="330 Tompkins Ave",
        address_line_2="Unit 3623 PMB A3415",
        city="Staten Island",
        state="NY",
        postal_code="10304",
        country="USA",
        is_active=True,
    )


@pytest.fixture
def staff_user():
    return CustomUser.objects.create_user(
        email="clerk@example.com",
        password="strongpass",
        is_active=True,
        is_staff=True,
    )


@pytest.fixture
def manager():
    user = CustomUser.objects.create_user(
        email="manager@example.com",
        password="strongpass",
        is_active=True,
        is_staff=True,
    )
    group, _created = Group.objects.get_or_create(name="Manager")
    user.groups.add(group)
    return user


@pytest.fixture
def admin_user():
    return CustomUser.objects.create_superuser(
        email="admin@example.com",
        password="strongpass",
    )


def test_migrations_do_not_create_a_default_warehouse(api_client):
    assert not Warehouse.objects.filter(code="US-IMAIL").exists()
    assert Warehouse.objects.count() == 0


def test_manager_can_add_a_warehouse_address(api_client, manager, staff_user):
    payload = {
        "code": "WH-1",
        "name": "Receiving warehouse",
        "phone": "7012033251",
        "address_line_1": "330 Tompkins Ave",
        "address_line_2": "Unit 3623 PMB A3415",
        "city": "Staten Island",
        "state": "NY",
        "postal_code": "10304",
        "country": "USA",
    }
    api_client.force_authenticate(user=staff_user)
    denied = api_client.post("/api/orders/staff/warehouses/", payload, format="json")
    assert denied.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=manager)
    created = api_client.post("/api/orders/staff/warehouses/", payload, format="json")
    assert created.status_code == status.HTTP_201_CREATED
    assert created.json()["code"] == "WH-1"
    assert created.json()["city"] == "Staten Island"
    assert Warehouse.objects.filter(code="WH-1", is_active=True).exists()


def test_staff_can_read_warehouse_but_not_change_it(api_client, staff_user, warehouse):
    api_client.force_authenticate(user=staff_user)
    listed = api_client.get("/api/orders/staff/warehouses/")
    assert listed.status_code == status.HTTP_200_OK
    assert listed.json()[0]["city"] == "Staten Island"

    resp = api_client.patch(
        f"/api/orders/staff/warehouses/{warehouse.id}/",
        {"city": "Brooklyn"},
        format="json",
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    warehouse.refresh_from_db()
    assert warehouse.city == "Staten Island"


def test_manager_and_admin_can_change_the_warehouse_address(api_client, manager, admin_user, warehouse):
    api_client.force_authenticate(user=manager)
    resp = api_client.patch(
        f"/api/orders/staff/warehouses/{warehouse.id}/",
        {
            "name": "Receiving warehouse",
            "address_line_1": "100 New Dock St",
            "address_line_2": "Unit 1",
            "city": "Brooklyn",
            "state": "NY",
            "postal_code": "11201",
            "country": "USA",
            "phone": "7012033251",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["address_line_1"] == "100 New Dock St"
    assert resp.json()["code"] == "WH-1"
    warehouse.refresh_from_db()
    assert warehouse.city == "Brooklyn"

    api_client.force_authenticate(user=admin_user)
    resp = api_client.patch(
        f"/api/orders/staff/warehouses/{warehouse.id}/",
        {"city": "Staten Island", "postal_code": "10304"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    warehouse.refresh_from_db()
    assert warehouse.city == "Staten Island"
    assert warehouse.postal_code == "10304"


def test_customer_cannot_read_or_edit_warehouse(api_client, warehouse):
    customer = CustomUser.objects.create_user(
        email="buyer@example.com",
        password="strongpass",
        is_active=True,
    )
    api_client.force_authenticate(user=customer)
    assert api_client.get("/api/orders/staff/warehouses/").status_code == status.HTTP_403_FORBIDDEN
    assert (
        api_client.post(
            "/api/orders/staff/warehouses/",
            {"code": "WH-2", "name": "Other", "address_line_1": "1 Main", "city": "Boston", "state": "MA", "postal_code": "02101", "country": "USA"},
            format="json",
        ).status_code
        == status.HTTP_403_FORBIDDEN
    )
    assert (
        api_client.patch(
            f"/api/orders/staff/warehouses/{warehouse.id}/",
            {"city": "Boston"},
            format="json",
        ).status_code
        == status.HTTP_403_FORBIDDEN
    )
