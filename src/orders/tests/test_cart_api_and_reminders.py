from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import Cart, CartItem
from orders.reminders import process_abandoned_cart_reminders
from products.models import Product, ProductVariant
from users.models import CustomUser


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return CustomUser.objects.create_user(
        email="cart-user@example.com",
        password="strongpass",
        is_active=True,
    )


@pytest.fixture
def product():
    return Product.objects.create(
        name="Vitamin C",
        description="Supplement",
        price="10.00",
        stock=100,
    )


@pytest.fixture
def variant(product):
    return ProductVariant.objects.create(
        product=product,
        price="12.00",
        stock=50,
    )


def test_cart_sync_and_fetch(api_client, user, product, variant):
    api_client.force_authenticate(user=user)
    resp = api_client.put(
        "/api/orders/cart/sync/",
        {
            "items": [
                {"product": product.id, "quantity": 2},
                {"variant": variant.id, "quantity": 1},
            ]
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["subtotal"] == 32.0

    me = api_client.get("/api/orders/cart/me/")
    assert me.status_code == status.HTTP_200_OK
    assert len(me.json()["items"]) == 2


def test_order_creation_clears_user_cart(api_client, user, product):
    cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=cart, product=product, quantity=2)

    api_client.force_authenticate(user=user)
    resp = api_client.post(
        "/api/orders/orders/",
        {
            "shipping_address": {
                "full_name": "Cart User",
                "phone": "0700000000",
                "email": "cart-user@example.com",
                "address_line_1": "Street 1",
                "address_line_2": "",
                "city": "Lagos",
                "state": "LA",
                "postal_code": "100001",
                "country": "Nigeria",
            },
            "items": [{"product": product.id, "quantity": 1}],
            "shipping_fee": "0.00",
            "notes": "",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    cart.refresh_from_db()
    assert cart.items.count() == 0


def test_abandoned_cart_reminders_send_in_12_24_48_sequence(monkeypatch, user, product):
    sent_steps = []

    def _fake_send(cart_id, reminder_hours):
        sent_steps.append((cart_id, reminder_hours))
        return True

    monkeypatch.setattr(
        "orders.reminders.send_abandoned_cart_reminder_email",
        _fake_send,
    )

    cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=cart, product=product, quantity=1)
    base_now = timezone.now()
    Cart.objects.filter(pk=cart.pk).update(updated_at=base_now - timedelta(hours=49))
    cart.refresh_from_db()

    assert process_abandoned_cart_reminders(now=base_now) == 1
    cart.refresh_from_db()
    assert cart.reminder_12_sent_at is not None
    assert sent_steps[-1][1] == 12

    assert process_abandoned_cart_reminders(now=base_now + timedelta(minutes=1)) == 1
    cart.refresh_from_db()
    assert cart.reminder_24_sent_at is not None
    assert sent_steps[-1][1] == 24

    assert process_abandoned_cart_reminders(now=base_now + timedelta(minutes=2)) == 1
    cart.refresh_from_db()
    assert cart.reminder_48_sent_at is not None
    assert sent_steps[-1][1] == 48

    assert process_abandoned_cart_reminders(now=base_now + timedelta(minutes=3)) == 0
