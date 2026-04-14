import pytest
from django.utils import timezone

from orders.models import (
    Order,
    OrderPayment,
    PaymentCredentials,
    PaymentProvider,
    PaymentStatus,
    OrderStatus,
    Shipment,
    ShipmentEvent,
    ShippingAddress,
    ShippingStatus,
)
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
def shipping_address(user):
    return ShippingAddress.objects.create(
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


@pytest.fixture
def order(user, shipping_address):
    return Order.objects.create(user=user, shipping_address=shipping_address, subtotal="0", total="0")


def test_shipment_mark_delivered_sets_status_and_timestamp(order):
    shipment = Shipment.objects.create(order=order)
    assert shipment.status == ShippingStatus.ORDER_PLACED
    assert shipment.delivered_at is None

    shipment.mark_delivered()
    shipment.refresh_from_db()
    assert shipment.status == ShippingStatus.DELIVERED
    assert shipment.delivered_at is not None


def test_shipment_dispatched_or_out_for_delivery_sets_order_shipping(order):
    shipment = Shipment.objects.create(order=order)
    assert order.status == OrderStatus.PAYMENT_PENDING

    shipment.status = ShippingStatus.DISPATCHED
    shipment.save(update_fields=["status", "updated_at"])
    order.refresh_from_db()
    assert order.status == OrderStatus.SHIPPING

    shipment.status = ShippingStatus.OUT_FOR_DELIVERY
    shipment.save(update_fields=["status", "updated_at"])
    order.refresh_from_db()
    assert order.status == OrderStatus.SHIPPING


def test_shipment_delivered_sets_order_complete(order):
    shipment = Shipment.objects.create(order=order)
    shipment.status = ShippingStatus.DELIVERED
    shipment.save(update_fields=["status", "updated_at"])

    order.refresh_from_db()
    assert order.status == OrderStatus.COMPLETE


def test_order_shipping_sets_shipment_dispatched(order):
    shipment = Shipment.objects.create(order=order)
    assert shipment.status == ShippingStatus.ORDER_PLACED

    order.status = OrderStatus.SHIPPING
    order.save(update_fields=["status", "updated_at"])

    shipment.refresh_from_db()
    assert shipment.status == ShippingStatus.DISPATCHED


def test_order_complete_sets_shipment_delivered(order):
    shipment = Shipment.objects.create(order=order)
    assert shipment.status == ShippingStatus.ORDER_PLACED
    assert shipment.delivered_at is None

    order.status = OrderStatus.COMPLETE
    order.save(update_fields=["status", "updated_at"])

    shipment.refresh_from_db()
    assert shipment.status == ShippingStatus.DELIVERED
    assert shipment.delivered_at is not None


def test_shipment_event_ordering(order):
    shipment = Shipment.objects.create(order=order)
    t1 = timezone.now()
    t0 = t1 - timezone.timedelta(hours=1)
    e2 = ShipmentEvent.objects.create(shipment=shipment, status=ShippingStatus.DISPATCHED, occurred_at=t1)
    e1 = ShipmentEvent.objects.create(shipment=shipment, status=ShippingStatus.ORDER_PLACED, occurred_at=t0)

    events = list(shipment.events.all())
    assert events[0].id == e1.id
    assert events[1].id == e2.id


def test_payment_credentials_encrypt_decrypt_roundtrip(settings):
    creds = PaymentCredentials(provider=PaymentProvider.INTASEND, environment="sandbox", api_key="pk")
    creds.set_private_key("secret")
    assert creds.encrypted_private_key
    assert creds.get_private_key() == "secret"


def test_payment_credentials_one_active_per_provider_env():
    c1 = PaymentCredentials.objects.create(provider=PaymentProvider.STRIPE, environment="sandbox", is_active=True)
    c2 = PaymentCredentials.objects.create(provider=PaymentProvider.STRIPE, environment="sandbox", is_active=True)
    c1.refresh_from_db()
    c2.refresh_from_db()
    assert c1.is_active is False
    assert c2.is_active is True


def test_order_payment_str(order):
    p = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.INTASEND,
        status=PaymentStatus.PENDING,
        amount="10.00",
        currency="KES",
    )
    assert "Order" in str(p)


def test_cancelling_order_cancels_pending_payments_only(order):
    pending = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.INTASEND,
        status=PaymentStatus.PENDING,
        amount="10.00",
        currency="KES",
    )
    completed = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.CASH,
        status=PaymentStatus.COMPLETED,
        amount="10.00",
        currency="KES",
    )

    order.status = OrderStatus.CANCELLED
    order.save()

    pending.refresh_from_db()
    completed.refresh_from_db()
    assert pending.status == PaymentStatus.CANCELLED
    assert completed.status == PaymentStatus.COMPLETED
