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


def test_dispatched_event_sets_order_shipping(order):
    shipment = Shipment.objects.create(order=order)

    ShipmentEvent.objects.create(shipment=shipment, status=ShippingStatus.DISPATCHED, message="Dispatched")

    shipment.refresh_from_db()
    order.refresh_from_db()
    assert shipment.status == ShippingStatus.DISPATCHED
    assert order.status == OrderStatus.SHIPPING


def test_out_for_delivery_event_sets_order_shipping(order):
    shipment = Shipment.objects.create(order=order)

    ShipmentEvent.objects.create(shipment=shipment, status=ShippingStatus.OUT_FOR_DELIVERY)

    shipment.refresh_from_db()
    order.refresh_from_db()
    assert shipment.status == ShippingStatus.OUT_FOR_DELIVERY
    assert order.status == OrderStatus.SHIPPING


def test_delivered_event_sets_order_complete(order):
    shipment = Shipment.objects.create(order=order)
    occurred_at = timezone.now() - timezone.timedelta(hours=2)

    ShipmentEvent.objects.create(
        shipment=shipment,
        status=ShippingStatus.DELIVERED,
        message="Delivered",
        occurred_at=occurred_at,
    )

    shipment.refresh_from_db()
    order.refresh_from_db()
    assert shipment.status == ShippingStatus.DELIVERED
    assert shipment.delivered_at == occurred_at
    assert order.status == OrderStatus.COMPLETE


def test_earlier_shipment_event_does_not_rewind_order(order):
    shipment = Shipment.objects.create(order=order)
    ShipmentEvent.objects.create(shipment=shipment, status=ShippingStatus.DELIVERED)

    ShipmentEvent.objects.create(shipment=shipment, status=ShippingStatus.DISPATCHED)

    shipment.refresh_from_db()
    order.refresh_from_db()
    assert shipment.status == ShippingStatus.DELIVERED
    assert order.status == OrderStatus.COMPLETE


def test_shipment_and_order_move_back_together(order):
    order.total = "10.00"
    order.save(update_fields=["total", "updated_at"])
    shipment = Shipment.objects.create(order=order)

    order.status = OrderStatus.COMPLETE
    order.save(update_fields=["status", "updated_at"])
    shipment.refresh_from_db()
    assert shipment.status == ShippingStatus.DELIVERED
    assert order.shipment.status == ShippingStatus.DELIVERED

    order.status = OrderStatus.SHIPPING
    order.save(update_fields=["status", "updated_at"])
    shipment.refresh_from_db()
    assert order.status == OrderStatus.SHIPPING
    assert shipment.status == ShippingStatus.DISPATCHED

    shipment.status = ShippingStatus.ORDER_PLACED
    shipment.save(update_fields=["status", "updated_at"])
    assert shipment.order.status == OrderStatus.PAYMENT_PENDING
    order.refresh_from_db()
    assert order.status == OrderStatus.PAYMENT_PENDING
    assert shipment.status == ShippingStatus.ORDER_PLACED


def test_paid_order_returns_to_processing_when_parcel_is_placed_again(order):
    order.total = "10.00"
    order.save(update_fields=["total", "updated_at"])
    OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.CASH,
        status=PaymentStatus.COMPLETED,
        amount="10.00",
        currency="USD",
    )
    shipment = Shipment.objects.create(order=order)
    shipment.status = ShippingStatus.DELIVERED
    shipment.save(update_fields=["status", "updated_at"])

    shipment.status = ShippingStatus.DISPATCHED
    shipment.save(update_fields=["status", "updated_at"])
    order.refresh_from_db()
    assert order.status == OrderStatus.SHIPPING
    assert shipment.status == ShippingStatus.DISPATCHED

    shipment.status = ShippingStatus.ORDER_PLACED
    shipment.save(update_fields=["status", "updated_at"])
    order.refresh_from_db()
    assert order.status == OrderStatus.PROCESSING


def test_cancelling_a_shipped_order_leaves_the_parcel(order):
    shipment = Shipment.objects.create(order=order)
    shipment.status = ShippingStatus.DISPATCHED
    shipment.save(update_fields=["status", "updated_at"])

    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    shipment.refresh_from_db()
    assert shipment.status == ShippingStatus.DISPATCHED
    assert order.status == OrderStatus.CANCELLED


def test_saving_other_fields_does_not_apply_a_dirty_status(order):
    order.total = "10.00"
    order.save(update_fields=["total", "updated_at"])
    shipment = Shipment.objects.create(order=order)
    pending = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.INTASEND,
        status=PaymentStatus.PENDING,
        amount="10.00",
        currency="KES",
    )
    order.status = OrderStatus.CANCELLED
    order.notes = "Keep the status"
    order.save(update_fields=["notes", "updated_at"])

    order.refresh_from_db()
    pending.refresh_from_db()
    shipment.refresh_from_db()
    assert order.status == OrderStatus.PAYMENT_PENDING
    assert order.notes == "Keep the status"
    assert pending.status == PaymentStatus.PENDING
    assert shipment.status == ShippingStatus.ORDER_PLACED


def test_order_placed_event_leaves_order_status(order):
    shipment = Shipment.objects.create(order=order)

    ShipmentEvent.objects.create(shipment=shipment, status=ShippingStatus.ORDER_PLACED, message="Order placed")

    shipment.refresh_from_db()
    order.refresh_from_db()
    assert shipment.status == ShippingStatus.ORDER_PLACED
    assert order.status == OrderStatus.PAYMENT_PENDING


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


def test_paid_processing_shipping_and_complete_stay_distinct(order):
    order.total = "10.00"
    order.save(update_fields=["total", "updated_at"])
    shipment = Shipment.objects.create(order=order)
    payment = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.CASH,
        status=PaymentStatus.COMPLETED,
        amount="10.00",
        currency="USD",
    )
    order.refresh_from_db()
    assert order.is_fully_paid is True
    assert order.status == OrderStatus.PROCESSING
    assert shipment.status == ShippingStatus.ORDER_PLACED

    shipment.status = ShippingStatus.DISPATCHED
    shipment.save(update_fields=["status", "updated_at"])
    order.refresh_from_db()
    assert order.status == OrderStatus.SHIPPING
    assert order.is_fully_paid is True

    shipment.status = ShippingStatus.DELIVERED
    shipment.save(update_fields=["status", "updated_at"])
    order.refresh_from_db()
    shipment.refresh_from_db()
    assert order.status == OrderStatus.COMPLETE
    assert shipment.status == ShippingStatus.DELIVERED
    assert order.is_fully_paid is True

    payment.soft_delete()
    order.refresh_from_db()
    shipment.refresh_from_db()
    assert order.is_fully_paid is False
    assert order.status == OrderStatus.COMPLETE
    assert shipment.status == ShippingStatus.DELIVERED


def test_refund_amount_change_reopens_the_paid_state(order):
    from decimal import Decimal

    from orders.models import OrderRefund, RefundStatus

    order.total = "10.00"
    order.save(update_fields=["total", "updated_at"])
    payment = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.CASH,
        status=PaymentStatus.COMPLETED,
        amount="10.00",
        currency="USD",
    )
    order.refresh_from_db()
    assert order.status == OrderStatus.PROCESSING
    refund = OrderRefund.objects.create(
        order=order,
        payment=payment,
        amount=Decimal("4.00"),
        currency="USD",
        status=RefundStatus.COMPLETED,
        reason="Partial return",
    )
    order.refresh_from_db()
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.COMPLETED
    assert order.is_fully_paid is False
    assert order.status == OrderStatus.PAYMENT_PENDING

    refund.amount = Decimal("10.00")
    refund.save(update_fields=["amount", "updated_at"])
    order.refresh_from_db()
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.REFUNDED
    assert order.is_fully_paid is False
    assert order.status == OrderStatus.PAYMENT_PENDING


def test_shipping_fee_recalculates_total_and_paid_state(order):
    from decimal import Decimal

    order.subtotal = "10.00"
    order.total = "10.00"
    order.save(update_fields=["subtotal", "total", "updated_at"])
    OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.CASH,
        status=PaymentStatus.COMPLETED,
        amount="10.00",
        currency="USD",
    )
    order.refresh_from_db()
    assert order.status == OrderStatus.PROCESSING
    assert order.is_fully_paid is True

    order.shipping_fee = Decimal("5.00")
    order.save(update_fields=["shipping_fee", "updated_at"])
    order.refresh_from_db()
    assert order.total == Decimal("15.00")
    assert order.is_fully_paid is False
    assert order.status == OrderStatus.PAYMENT_PENDING


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
