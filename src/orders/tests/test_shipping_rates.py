from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from products.models import Product, ProductVariant
from users.models import CustomUser

pytestmark = pytest.mark.django_db

RATES = "/api/orders/shipping-rates/"
QUOTE = "/api/orders/shipping-rates/quote/"
ORDERS = "/api/orders/orders/"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user():
    return CustomUser.objects.create_superuser(
        email="admin@example.com",
        password="strongpass",
    )


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
        email="shopper@example.com",
        password="strongpass",
        is_active=True,
    )


@pytest.fixture
def product():
    return Product.objects.create(
        name="Vitamin C",
        description="Supplement",
        price="10.00",
        unit_weight=500,
    )


def _address(country="Kenya"):
    return {
        "full_name": "Amina Otieno",
        "phone": "0712345678",
        "email": "amina@example.com",
        "address_line_1": "12 Ngong Road",
        "city": "Nairobi",
        "state": "Nairobi",
        "postal_code": "00100",
        "country": country,
    }


def test_admin_sets_country_rate_and_a_lighter_basket_pays_the_unit_fee(
    api_client, admin_user, staff_user, user, product
):
    api_client.force_authenticate(user=staff_user)
    denied = api_client.put(
        RATES,
        {"countries": [{"country": "Kenya", "unit_weight": 1000, "fee": "20.00"}]},
        format="json",
    )
    assert denied.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=admin_user)
    saved = api_client.put(
        RATES,
        {"countries": [{"country": "Kenya", "unit_weight": 1000, "fee": "20.00"}]},
        format="json",
    )
    assert saved.status_code == status.HTTP_200_OK
    assert saved.json() == {
        "countries": [{"country": "Kenya", "unit_weight": 1000, "fee": "20.00"}],
    }

    api_client.force_authenticate(user=None)
    public = api_client.get(RATES)
    assert public.status_code == status.HTTP_200_OK
    assert public.json()["countries"][0]["fee"] == "20.00"

    quote = api_client.post(
        QUOTE,
        {"country": "kenya", "items": [{"product": product.id, "quantity": 1}]},
        format="json",
    )
    assert quote.status_code == status.HTTP_200_OK
    assert quote.json() == {"country": "kenya", "weight_grams": 500, "shipping_fee": "20.00"}

    api_client.force_authenticate(user=user)
    order = api_client.post(
        ORDERS,
        {
            "shipping_address": _address(),
            "items": [{"product": product.id, "quantity": 1}],
            "shipping_fee": "0.00",
        },
        format="json",
    )
    assert order.status_code == status.HTTP_201_CREATED
    body = order.json()
    assert body["shipping_fee"] == "20.00"
    assert Decimal(body["total"]) == Decimal("30.00")

    missing = api_client.post(
        ORDERS,
        {
            "shipping_address": _address("Nigeria"),
            "items": [{"product": product.id, "quantity": 1}],
        },
        format="json",
    )
    assert missing.status_code == status.HTTP_400_BAD_REQUEST
    assert missing.json()["shipping_address"]["country"] == "Shipping to this country is not set."


def test_variant_line_uses_the_product_weight(api_client, admin_user, user, product):
    variant = ProductVariant.objects.create(product=product, price="8.00")
    product.unit_weight = 250
    product.save(update_fields=["unit_weight"])

    api_client.force_authenticate(user=admin_user)
    api_client.put(
        RATES,
        {"countries": [{"country": "Kenya", "unit_weight": 1000, "fee": "20.00"}]},
        format="json",
    )

    api_client.force_authenticate(user=user)
    order = api_client.post(
        ORDERS,
        {
            "shipping_address": _address(),
            "items": [{"variant": variant.id, "quantity": 2}],
        },
        format="json",
    )
    assert order.status_code == status.HTTP_201_CREATED
    assert order.json()["shipping_fee"] == "20.00"


def test_a_heavier_basket_is_charged_by_weight(api_client, admin_user, user, product):
    product.unit_weight = 1500
    product.save(update_fields=["unit_weight"])

    api_client.force_authenticate(user=admin_user)
    api_client.put(
        RATES,
        {"countries": [{"country": "Kenya", "unit_weight": 1000, "fee": "20.00"}]},
        format="json",
    )

    api_client.force_authenticate(user=user)
    order = api_client.post(
        ORDERS,
        {
            "shipping_address": _address(),
            "items": [{"product": product.id, "quantity": 1}],
        },
        format="json",
    )
    assert order.status_code == status.HTTP_201_CREATED
    assert order.json()["shipping_fee"] == "30.00"


def test_replacing_the_schedule_drops_a_country_that_is_left_out(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    api_client.put(
        RATES,
        {
            "countries": [
                {"country": "Kenya", "unit_weight": 1000, "fee": "20.00"},
                {"country": "Nigeria", "unit_weight": 500, "fee": "15.00"},
            ],
        },
        format="json",
    )
    replaced = api_client.put(
        RATES,
        {"countries": [{"country": "Kenya", "unit_weight": 1000, "fee": "20.00"}]},
        format="json",
    )
    assert replaced.status_code == status.HTTP_200_OK
    assert replaced.json()["countries"] == [{"country": "Kenya", "unit_weight": 1000, "fee": "20.00"}]


def test_cart_shows_the_shipping_fee_for_the_shopper(api_client, admin_user, user, product):
    api_client.force_authenticate(user=admin_user)
    api_client.put(
        RATES,
        {"countries": [{"country": "Kenya", "unit_weight": 1000, "fee": "20.00"}]},
        format="json",
    )

    api_client.force_authenticate(user=user)
    synced = api_client.put(
        "/api/orders/cart/sync/",
        {"country": "Kenya", "items": [{"product": product.id, "quantity": 1}]},
        format="json",
    )
    assert synced.status_code == status.HTTP_200_OK
    assert synced.json()["weight_grams"] == 500
    assert synced.json()["shipping_fee"] == "20.00"
    assert synced.json()["shipping_fees"] == [{"country": "Kenya", "shipping_fee": "20.00"}]

    me = api_client.get("/api/orders/cart/me/", {"country": "Kenya"})
    assert me.json()["shipping_fee"] == "20.00"

    unknown = api_client.get("/api/orders/cart/me/", {"country": "Nigeria"})
    assert unknown.status_code == status.HTTP_200_OK
    assert unknown.json()["shipping_fee"] is None
    assert unknown.json()["items"]


def test_without_country_rates_checkout_charges_nothing(api_client, admin_user, user, product):
    api_client.force_authenticate(user=admin_user)
    api_client.put(RATES, {"countries": []}, format="json")

    api_client.force_authenticate(user=user)
    order = api_client.post(
        ORDERS,
        {
            "shipping_address": _address("Nigeria"),
            "items": [{"product": product.id, "quantity": 1}],
            "shipping_fee": "9.00",
        },
        format="json",
    )
    assert order.status_code == status.HTTP_201_CREATED
    assert order.json()["shipping_fee"] == "0.00"
