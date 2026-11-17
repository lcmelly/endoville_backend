import pytest
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import CustomerMessage, Order
from products.models import Product
from users.models import CustomUser

pytestmark = pytest.mark.django_db

MESSAGES = "/api/orders/messages/"


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return CustomUser.objects.create_user(email="shopper@example.com", password="strongpass", is_active=True)


@pytest.fixture
def staff_user():
    return CustomUser.objects.create_user(
        email="staff@example.com",
        password="strongpass",
        is_active=True,
        is_staff=True,
    )


@pytest.fixture
def product():
    return Product.objects.create(name="Vitamin C", description="Supplement", price="10.00", unit_weight=500)


@pytest.fixture
def order(user, product):
    from orders.models import ShippingAddress

    address = ShippingAddress.objects.create(
        user=user,
        full_name="Amina",
        address_line_1="12 Ngong Road",
        city="Nairobi",
        country="Kenya",
    )
    placed = Order.objects.create(
        user=user,
        shipping_address=address,
        subtotal="10.00",
        shipping_fee="0.00",
        total="10.00",
    )
    return placed


@pytest.fixture
def human(monkeypatch):
    monkeypatch.setattr("orders.customer_messages.verify_human", lambda token, remote_ip: None)


def test_message_requires_a_contact_and_strips_markup(api_client, human, order):
    missing = api_client.post(
        MESSAGES,
        {"message": "The bottle arrived open.", "captcha_token": "ok"},
        format="json",
    )
    assert missing.status_code == status.HTTP_400_BAD_REQUEST

    saved = api_client.post(
        MESSAGES,
        {
            "email": "Amina@Example.com",
            "message": "<script>alert(1)</script>The bottle arrived open.",
            "order_number": order.public_id,
            "captcha_token": "ok",
        },
        format="json",
    )
    assert saved.status_code == status.HTTP_201_CREATED
    body = saved.json()
    assert body["email"] == "amina@example.com"
    assert body["message"] == "alert(1)The bottle arrived open."
    assert body["order_number"] == order.public_id
    assert "<script>" not in body["message"]
    assert CustomerMessage.objects.get().order_id == order.pk


def test_phone_is_accepted_and_a_guessed_order_number_is_refused(api_client, human, order):
    guessed = api_client.post(
        MESSAGES,
        {
            "phone": "+254 712 345 678",
            "message": "Where is my parcel?",
            "order_number": str(order.pk).zfill(8),
            "captcha_token": "ok",
        },
        format="json",
    )
    assert guessed.status_code == status.HTTP_400_BAD_REQUEST
    assert guessed.json()["order_number"] == ["Order number is not valid."]

    saved = api_client.post(
        MESSAGES,
        {
            "phone": "+254 712 345 678",
            "message": "Where is my parcel?",
            "captcha_token": "ok",
        },
        format="json",
    )
    assert saved.status_code == status.HTTP_201_CREATED
    assert saved.json()["phone"] == "+254712345678"
    assert saved.json()["order_number"] is None


def test_message_length_is_limited(api_client, human):
    resp = api_client.post(
        MESSAGES,
        {"email": "amina@example.com", "message": "x" * 501, "captcha_token": "ok"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "500" in str(resp.json()["message"])


def test_local_debug_does_not_call_cloudflare(api_client, monkeypatch):
    from django.test import override_settings
    from rest_framework.serializers import ValidationError

    import orders.customer_messages as customer_messages

    def refuse_network(*args, **kwargs):
        raise AssertionError("Cloudflare should not be called in local debug")

    monkeypatch.setattr(customer_messages.requests, "post", refuse_network)

    with override_settings(DEBUG=True):
        customer_messages.verify_human("local-dev", "127.0.0.1")
        form = api_client.get(MESSAGES)

    assert form.status_code == status.HTTP_200_OK
    assert form.json()["captcha_required"] is False

    with override_settings(DEBUG=False, CUSTOMER_MESSAGE_CAPTCHA_SECRET=""):
        with pytest.raises(ValidationError):
            customer_messages.verify_human("local-dev", "127.0.0.1")
        form = api_client.get(MESSAGES)

    assert form.json()["captcha_required"] is True


def test_failed_human_check_is_rejected(api_client, monkeypatch):
    monkeypatch.setattr(
        "orders.customer_messages.verify_human",
        lambda token, remote_ip: (_ for _ in ()).throw(
            __import__("rest_framework.serializers", fromlist=["ValidationError"]).ValidationError(
                "Human verification failed."
            )
        ),
    )
    resp = api_client.post(
        MESSAGES,
        {"email": "amina@example.com", "message": "Hello", "captcha_token": "bad"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert resp.json()["captcha_token"] == ["Human verification failed."]


def test_messages_are_rate_limited(api_client, human):
    for index in range(5):
        payload = {"email": f"person{index}@example.com", "message": "Hello", "captcha_token": "ok"}
        assert api_client.post(MESSAGES, payload, format="json").status_code == status.HTTP_201_CREATED
    blocked = api_client.post(
        MESSAGES,
        {"email": "sixth@example.com", "message": "Hello", "captcha_token": "ok"},
        format="json",
    )
    assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_the_same_contact_is_limited_across_messages(api_client, human):
    payload = {"phone": "0712345678", "message": "Hello", "captcha_token": "ok"}
    for _ in range(3):
        assert api_client.post(MESSAGES, payload, format="json").status_code == status.HTTP_201_CREATED
    limited = api_client.post(MESSAGES, payload, format="json")
    assert limited.status_code == status.HTTP_400_BAD_REQUEST
    assert "Too many messages" in str(limited.json())


def test_staff_can_list_messages_and_shoppers_cannot(api_client, human, staff_user, user):
    api_client.post(
        MESSAGES,
        {"email": "amina@example.com", "message": "Late delivery", "captcha_token": "ok"},
        format="json",
    )
    api_client.force_authenticate(user=user)
    denied = api_client.get("/api/orders/staff/messages/")
    assert denied.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=staff_user)
    listed = api_client.get("/api/orders/staff/messages/")
    assert listed.status_code == status.HTTP_200_OK
    assert listed.json()[0]["message"] == "Late delivery"


def test_order_urls_use_the_public_id(api_client, user, order):
    api_client.force_authenticate(user=user)
    hidden = api_client.get(f"/api/orders/orders/{order.pk}/")
    assert hidden.status_code == status.HTTP_404_NOT_FOUND

    visible = api_client.get(f"/api/orders/orders/{order.public_id}/")
    assert visible.status_code == status.HTTP_200_OK
    assert visible.json()["id"] == order.public_id
    assert visible.json()["id"] != str(order.pk)
