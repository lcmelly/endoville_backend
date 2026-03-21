from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from orders.emails import send_order_confirmation_email
from orders.serializers import CreateOrderSerializer
from orders.models import Order, PaymentProvider, PaymentStatus, ShippingAddress
from products.models import Product
from users.models import CustomUser


pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return CustomUser.objects.create_user(
        email="user@example.com",
        password="strongpass",
        first_name="John",
        is_active=True,
    )


@pytest.fixture
def product():
    return Product.objects.create(
        name="Vitamin C 1000mg",
        description="High-strength Vitamin C",
        price="19.99",
        stock=20,
        image_urls=["https://cdn.example.com/products/vitamin-c.png"],
    )


def test_send_order_confirmation_email_uses_zeptomail_template(user, product, settings):
    settings.ZEPTOMAIL_ORDER_CONFIRMATION_TEMPLATE_KEY = "order-template-key"
    settings.DEFAULT_FROM_EMAIL = "noreply@endovillehealth.com"
    settings.DEFAULT_FROM_NAME = "Endoville Health"
    settings.SUPPORT_EMAIL = "support@endovillehealth.com"
    settings.SUPPORT_PHONE = "+254700000000"

    shipping_address = ShippingAddress.objects.create(
        user=user,
        full_name="John Doe",
        phone="0712345678",
        email="john@example.com",
        address_line_1="Street 1",
        address_line_2="Apt 2",
        city="Nairobi",
        state="Nairobi",
        postal_code="00100",
        country="Kenya",
    )
    order = Order.objects.create(
        user=user,
        shipping_address=shipping_address,
        subtotal="19.99",
        shipping_fee="2.00",
        total="21.99",
    )
    order.items.create(
        product=product,
        product_name=product.name,
        variant_description="",
        barcode="",
        quantity=1,
        unit_price="19.99",
        line_total="19.99",
    )
    order.payments.create(
        provider=PaymentProvider.INTASEND,
        status=PaymentStatus.PENDING,
        amount="21.99",
        currency="USD",
        checkout_url="https://example.com/checkout",
        provider_invoice_id="INV-123",
    )

    with patch("orders.emails.send_template_email", return_value=True) as mock_send:
        result = send_order_confirmation_email(order.id)

    assert result is True
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["to_email"] == "john@example.com"
    assert call_kwargs["template_key"] == "order-template-key"
    assert call_kwargs["to_name"] == "John Doe"
    assert call_kwargs["merge_data"]["order_id"] == str(order.id)
    assert call_kwargs["merge_data"]["checkout_url"] == "https://example.com/checkout"
    assert call_kwargs["merge_data"]["payment_invoice_id"] == "INV-123"
    assert call_kwargs["merge_data"]["shipping_address"]["full_name"] == "John Doe"
    assert call_kwargs["merge_data"]["item"]["product_name"] == "Vitamin C 1000mg"
    assert call_kwargs["merge_data"]["item"]["image_url"] == "https://cdn.example.com/products/vitamin-c.png"
    assert call_kwargs["merge_data"]["image_url"] == "https://cdn.example.com/products/vitamin-c.png"


def test_create_order_serializer_queues_confirmation_email(user, product, monkeypatch):
    request = SimpleNamespace(user=user)
    serializer = CreateOrderSerializer(
        data={
            "shipping_address": {
                "full_name": "John Doe",
                "phone": "0712345678",
                "email": "john@example.com",
                "address_line_1": "Street 1",
                "address_line_2": "",
                "city": "Nairobi",
                "state": "",
                "postal_code": "00100",
                "country": "Kenya",
            },
            "items": [{"product": product.id, "quantity": 2}],
            "shipping_fee": "3.00",
            "notes": "Handle with care",
        },
        context={"request": request},
    )
    assert serializer.is_valid(), serializer.errors

    callback_holder = {}

    def run_immediately(callback):
        callback_holder["callback"] = callback
        callback()

    mocked_send = Mock(return_value=True)
    monkeypatch.setattr("orders.serializers.transaction.on_commit", run_immediately)
    monkeypatch.setattr("orders.serializers.send_order_confirmation_email", mocked_send)

    order = serializer.save()

    assert Order.objects.filter(pk=order.pk).exists()
    mocked_send.assert_called_once_with(order.id)
