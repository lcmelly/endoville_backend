import pytest

from orders.models import (
    Order,
    OrderPayment,
    PaymentProvider,
    PaymentStatus,
    Shipment,
    ShipmentEvent,
    ShippingAddress,
    ShippingStatus,
)
from orders.serializers import OrderPaymentSerializer, ShipmentSerializer
from users.models import CustomUser


pytestmark = pytest.mark.django_db


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
    return Order.objects.create(user=user, shipping_address=addr, subtotal="0", total="0")


def test_shipment_serializer_includes_events(order):
    shipment = Shipment.objects.create(order=order, status=ShippingStatus.ORDER_PLACED)
    ShipmentEvent.objects.create(shipment=shipment, status=ShippingStatus.ORDER_PLACED, message="Placed")

    data = ShipmentSerializer(instance=shipment).data
    assert data["status"] == ShippingStatus.ORDER_PLACED
    assert "events" in data
    assert len(data["events"]) == 1
    assert data["events"][0]["message"] == "Placed"


def test_order_payment_serializer_shape(order):
    payment = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.INTASEND,
        status=PaymentStatus.PENDING,
        amount="10.00",
        currency="KES",
        checkout_url="https://example.com/pay",
    )
    data = OrderPaymentSerializer(instance=payment).data
    assert data["provider"] == PaymentProvider.INTASEND
    assert data["checkout_url"] == "https://example.com/pay"
