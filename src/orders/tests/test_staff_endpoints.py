from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import (
    Order,
    OrderStatus,
    PaymentCredentials,
    PaymentProvider,
    ShippingAddress,
    Shipment,
    ShippingStatus,
)
from users.models import CustomUser


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


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
    o = Order.objects.create(user=user, shipping_address=addr, subtotal="0", total="10.00")
    Shipment.objects.create(order=o)
    return o


def test_payment_credentials_staff_only(api_client, user, staff_user):
    api_client.force_authenticate(user=user)
    resp = api_client.post(
        "/api/orders/payment-credentials/",
        {
            "provider": "intasend",
            "environment": "sandbox",
            "api_key": "pk",
            "private_key": "sk",
            "is_active": True,
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        "/api/orders/payment-credentials/",
        {
            "provider": "intasend",
            "environment": "sandbox",
            "api_key": "pk",
            "private_key": "sk",
            "is_active": True,
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    # private key should never be returned
    assert "private_key" not in data
    assert data["has_private_key"] is True
    assert PaymentCredentials.objects.filter(provider=PaymentProvider.INTASEND, is_active=True).exists()


def test_staff_cannot_record_payment_for_cancelled_or_fully_paid_order(api_client, staff_user, order):
    from orders.models import OrderPayment

    api_client.force_authenticate(user=staff_user)
    payload = {
        "order": order.public_id,
        "provider": PaymentProvider.CASH,
        "status": "completed",
        "amount": "10.00",
        "currency": "USD",
        "transaction_id": "txn-staff-pay-1",
    }

    Order.objects.filter(pk=order.pk).update(status=OrderStatus.CANCELLED)
    cancelled = api_client.post("/api/orders/staff/payments/", payload, format="json")
    assert cancelled.status_code == status.HTTP_400_BAD_REQUEST
    assert cancelled.json()["detail"] == "Cannot record a payment for a cancelled order."
    assert not OrderPayment.objects.filter(order=order).exists()

    Order.objects.filter(pk=order.pk).update(status=OrderStatus.PAYMENT_PENDING)
    first = api_client.post("/api/orders/staff/payments/", payload, format="json")
    assert first.status_code == status.HTTP_201_CREATED
    assert first.json()["transaction_id"] == "txn-staff-pay-1"

    second = api_client.post(
        "/api/orders/staff/payments/",
        {**payload, "transaction_id": "txn-staff-pay-2"},
        format="json",
    )
    assert second.status_code == status.HTTP_400_BAD_REQUEST
    assert second.json()["detail"] == "Order is already fully paid."
    assert OrderPayment.objects.filter(order=order).count() == 1


def test_staff_check_status_marks_a_paid_stripe_session_complete(api_client, staff_user, order, monkeypatch):
    from orders.models import OrderPayment, PaymentStatus
    from orders.payments.stripe import StripeAPI

    payment = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.STRIPE,
        status=PaymentStatus.PENDING,
        amount=order.total,
        currency="USD",
        provider_payment_id="cs_test_open",
    )

    class PaidSession:
        id = "cs_test_open"
        status = "complete"
        payment_status = "paid"

    class FakeStripe:
        class checkout:
            class Session:
                @staticmethod
                def retrieve(session_id):
                    assert session_id == "cs_test_open"
                    return PaidSession()

    class FakeAPI:
        def __init__(self):
            self.stripe = FakeStripe()

        check_payment_status = StripeAPI.check_payment_status

    monkeypatch.setattr("orders.payments.stripe.StripeAPI", FakeAPI)
    api_client.force_authenticate(user=staff_user)
    checked = api_client.post(f"/api/orders/payments/{payment.id}/check-status/")
    assert checked.status_code == status.HTTP_200_OK
    assert checked.json()["status_check"]["is_complete"] is True
    assert checked.json()["payment"]["status"] == PaymentStatus.COMPLETED
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.COMPLETED
    assert payment.provider_state == "paid"


def test_staff_new_payment_checks_open_stripe_sessions(api_client, staff_user, order, monkeypatch):
    from orders.models import OrderPayment, PaymentStatus

    stripe_payment = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.STRIPE,
        status=PaymentStatus.PENDING,
        amount=order.total,
        currency="USD",
        provider_payment_id="cs_test_open",
    )

    class FakeAPI:
        def __init__(self):
            pass

        def check_payment_status(self, payment):
            payment.status = PaymentStatus.COMPLETED
            payment.provider_state = "paid"
            payment.save(update_fields=["status", "provider_state", "updated_at"])
            return {"success": True, "status": payment.status}

    monkeypatch.setattr("orders.payments.stripe.StripeAPI", FakeAPI)
    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        "/api/orders/staff/payments/",
        {
            "order": order.public_id,
            "provider": PaymentProvider.CASH,
            "status": "completed",
            "amount": "10.00",
            "currency": "USD",
            "transaction_id": "txn-after-stripe",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert resp.json()["detail"] == "Order is already fully paid."
    stripe_payment.refresh_from_db()
    assert stripe_payment.status == PaymentStatus.COMPLETED
    assert OrderPayment.objects.filter(order=order).count() == 1


def test_staff_payment_transaction_id_is_optional_and_unique_when_set(api_client, staff_user, order):
    api_client.force_authenticate(user=staff_user)
    payload = {
        "order": order.public_id,
        "provider": PaymentProvider.CASH,
        "status": "pending",
        "amount": "1.00",
        "currency": "USD",
    }
    omitted = api_client.post("/api/orders/staff/payments/", payload, format="json")
    assert omitted.status_code == status.HTTP_201_CREATED
    assert omitted.json()["transaction_id"] is None

    blank = api_client.post("/api/orders/staff/payments/", {**payload, "transaction_id": "   "}, format="json")
    assert blank.status_code == status.HTTP_201_CREATED
    assert blank.json()["transaction_id"] is None

    empty = api_client.post("/api/orders/staff/payments/", {**payload, "transaction_id": None}, format="json")
    assert empty.status_code == status.HTTP_201_CREATED
    assert empty.json()["transaction_id"] is None

    created = api_client.post(
        "/api/orders/staff/payments/",
        {**payload, "transaction_id": "txn-unique-1"},
        format="json",
    )
    assert created.status_code == status.HTTP_201_CREATED
    assert created.json()["transaction_id"] == "txn-unique-1"

    listed = api_client.get("/api/orders/staff/payments/")
    assert listed.status_code == status.HTTP_200_OK
    row = next(item for item in listed.json() if item["id"] == created.json()["id"])
    assert row["transaction_id"] == "txn-unique-1"

    order_body = api_client.get(f"/api/orders/orders/{order.public_id}/")
    assert order_body.status_code == status.HTTP_200_OK
    assert order_body.json()["payments"][0]["transaction_id"] == "txn-unique-1"

    duplicate = api_client.post(
        "/api/orders/staff/payments/",
        {**payload, "transaction_id": "txn-unique-1"},
        format="json",
    )
    assert duplicate.status_code == status.HTTP_400_BAD_REQUEST
    assert "transaction_id" in duplicate.json()


def test_staff_can_update_shipment_and_add_event(api_client, staff_user, order):
    shipment = order.shipment
    api_client.force_authenticate(user=staff_user)

    resp = api_client.patch(
        f"/api/orders/staff/shipments/{shipment.id}/",
        {"status": "DISPATCHED", "carrier": "DHL", "tracking_number": "TRK-1"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK

    resp = api_client.post(
        "/api/orders/staff/shipment-events/",
        {"shipment": shipment.id, "status": "DISPATCHED", "message": "Dispatched", "location": "Warehouse"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED


def test_delivered_shipment_event_sets_order_complete(api_client, staff_user, order):
    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        "/api/orders/staff/shipment-events/",
        {"shipment": order.shipment.id, "status": "DELIVERED", "message": "Delivered"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED

    order.refresh_from_db()
    order.shipment.refresh_from_db()
    assert order.status == OrderStatus.COMPLETE
    assert order.shipment.status == ShippingStatus.DELIVERED
    assert order.shipment.delivered_at is not None


def test_staff_refund_initiated_then_completed_reflects_on_order(api_client, staff_user, order):
    from orders.models import OrderPayment, OrderRefund, PaymentStatus, RefundStatus

    payment = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.CASH,
        status=PaymentStatus.COMPLETED,
        amount=order.total,
        currency="KES",
    )
    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status", "updated_at"])

    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        "/api/orders/staff/refunds/",
        {
            "payment": payment.id,
            "reason": "Customer cancelled after paying",
            "transaction_id": "txn-cancel-1",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    assert body["status"] == RefundStatus.INITIATED
    assert body["amount"] == "10.00"
    assert body["order"] == order.public_id
    assert body["initiated_by"] == staff_user.id
    assert body["transaction_id"] == "txn-cancel-1"
    assert body["reason"] == "Customer cancelled after paying"

    payment.refresh_from_db()
    order.refresh_from_db()
    assert payment.status == PaymentStatus.REFUND_INITIATED
    assert order.status == OrderStatus.CANCELLED
    assert order.is_fully_paid is True

    order_resp = api_client.get(f"/api/orders/orders/{order.public_id}/")
    assert order_resp.status_code == status.HTTP_200_OK
    refunds = order_resp.json()["refunds"]
    assert len(refunds) == 1
    assert refunds[0]["status"] == RefundStatus.INITIATED
    assert order_resp.json()["payments"][0]["status"] == PaymentStatus.REFUND_INITIATED

    done = api_client.patch(
        f"/api/orders/staff/refunds/{body['id']}/",
        {"status": "completed", "provider_refund_id": "re_123"},
        format="json",
    )
    assert done.status_code == status.HTTP_200_OK
    assert done.json()["status"] == RefundStatus.COMPLETED
    assert done.json()["completed_at"]

    payment.refresh_from_db()
    order.refresh_from_db()
    assert payment.status == PaymentStatus.REFUNDED
    assert order.status == OrderStatus.REFUNDED
    assert order.is_fully_paid is False
    assert OrderRefund.objects.filter(payment=payment, status=RefundStatus.COMPLETED).exists()


def test_refund_requires_reason_and_transaction_id(api_client, staff_user, order):
    from orders.models import OrderPayment, PaymentStatus

    payment = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.CASH,
        status=PaymentStatus.COMPLETED,
        amount=order.total,
        currency="KES",
    )
    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    api_client.force_authenticate(user=staff_user)

    missing = api_client.post("/api/orders/staff/refunds/", {"payment": payment.id}, format="json")
    assert missing.status_code == status.HTTP_400_BAD_REQUEST
    assert "reason" in missing.json()
    assert "transaction_id" in missing.json()

    blank = api_client.post(
        "/api/orders/staff/refunds/",
        {"payment": payment.id, "reason": "   ", "transaction_id": "   "},
        format="json",
    )
    assert blank.status_code == status.HTTP_400_BAD_REQUEST


def test_refund_requires_cancelled_order_with_completed_payment(api_client, staff_user, user, order):
    from orders.models import OrderPayment, PaymentStatus

    payment = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.CASH,
        status=PaymentStatus.COMPLETED,
        amount=order.total,
        currency="KES",
    )
    api_client.force_authenticate(user=user)
    denied = api_client.post("/api/orders/staff/refunds/", {"payment": payment.id}, format="json")
    assert denied.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=staff_user)
    not_cancelled = api_client.post(
        "/api/orders/staff/refunds/",
        {"payment": payment.id, "reason": "Customer cancelled", "transaction_id": "txn-open-1"},
        format="json",
    )
    assert not_cancelled.status_code == status.HTTP_400_BAD_REQUEST

    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    pending = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.CASH,
        status=PaymentStatus.PENDING,
        amount="1.00",
        currency="KES",
    )
    unpaid = api_client.post(
        "/api/orders/staff/refunds/",
        {"payment": pending.id, "reason": "Customer cancelled", "transaction_id": "txn-pending-1"},
        format="json",
    )
    assert unpaid.status_code == status.HTTP_400_BAD_REQUEST


def test_partial_refund_of_one_payment_keeps_order_cancelled(api_client, staff_user, order):
    from orders.models import OrderPayment, PaymentStatus

    first = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.CASH,
        status=PaymentStatus.COMPLETED,
        amount="6.00",
        currency="KES",
    )
    second = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.CASH,
        status=PaymentStatus.COMPLETED,
        amount="4.00",
        currency="KES",
    )
    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status", "updated_at"])

    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        "/api/orders/staff/refunds/",
        {
            "payment": first.id,
            "status": "completed",
            "reason": "First payment returned",
            "transaction_id": "txn-partial-1",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    order.refresh_from_db()
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == PaymentStatus.REFUNDED
    assert second.status == PaymentStatus.COMPLETED
    assert order.status == OrderStatus.CANCELLED

    resp = api_client.post(
        "/api/orders/staff/refunds/",
        {
            "payment": second.id,
            "status": "completed",
            "reason": "Second payment returned",
            "transaction_id": "txn-partial-2",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    order.refresh_from_db()
    assert order.status == OrderStatus.REFUNDED


def test_marking_order_refunded_writes_refund_records(api_client, staff_user, order):
    from orders.models import OrderPayment, OrderRefund, PaymentStatus, RefundStatus

    payment = OrderPayment.objects.create(
        order=order,
        provider=PaymentProvider.CASH,
        status=PaymentStatus.COMPLETED,
        amount=order.total,
        currency="KES",
    )
    api_client.force_authenticate(user=staff_user)
    resp = api_client.patch(
        f"/api/orders/orders/{order.public_id}/",
        {"status": "REFUNDED"},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["status"] == OrderStatus.REFUNDED
    assert len(resp.json()["refunds"]) == 1
    assert resp.json()["refunds"][0]["status"] == RefundStatus.COMPLETED
    assert resp.json()["payments"][0]["status"] == PaymentStatus.REFUNDED

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.REFUNDED
    assert OrderRefund.objects.filter(payment=payment, status=RefundStatus.COMPLETED).count() == 1
    recorded = OrderRefund.objects.get(payment=payment)
    assert recorded.reason == "Order marked refunded"
    assert recorded.transaction_id


def test_marking_order_refunded_derives_status_after_every_payment(api_client, staff_user, order):
    from orders.models import OrderPayment, OrderRefund, PaymentStatus, RefundStatus
    from users.models import StaffChangeLog

    OrderPayment.objects.create(
        order=order, provider=PaymentProvider.CASH, status=PaymentStatus.COMPLETED, amount="6.00", currency="KES"
    )
    OrderPayment.objects.create(
        order=order, provider=PaymentProvider.CASH, status=PaymentStatus.COMPLETED, amount="4.00", currency="KES"
    )
    api_client.force_authenticate(user=staff_user)
    resp = api_client.patch(f"/api/orders/orders/{order.public_id}/", {"status": "REFUNDED"}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["status"] == OrderStatus.REFUNDED
    assert len(resp.json()["refunds"]) == 2
    assert {row["status"] for row in resp.json()["refunds"]} == {RefundStatus.COMPLETED}

    order.refresh_from_db()
    assert order.status == OrderStatus.REFUNDED
    assert OrderRefund.objects.filter(order=order, status=RefundStatus.COMPLETED).count() == 2
    status_changes = [
        row["status"]["to"]
        for row in StaffChangeLog.objects.filter(order_id=order.pk, action="order.status_changed").values_list(
            "changes", flat=True
        )
    ]
    assert status_changes == [OrderStatus.REFUNDED]


def test_payments_cannot_be_edited_or_deleted(api_client, staff_user, user, order):
    from orders.models import OrderPayment, PaymentProvider

    payment = OrderPayment.objects.create(order=order, provider=PaymentProvider.CASH, amount="10.00", currency="KES")

    api_client.force_authenticate(user=user)
    resp = api_client.patch(f"/api/orders/payments/{payment.id}/", {"status": "completed"}, format="json")
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    resp = api_client.delete(f"/api/orders/payments/{payment.id}/")
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    api_client.force_authenticate(user=staff_user)
    resp = api_client.patch(
        f"/api/orders/staff/payments/{payment.id}/",
        {"status": "completed", "amount": "9.50"},
        format="json",
    )
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    resp = api_client.delete(f"/api/orders/staff/payments/{payment.id}/")
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    payment.refresh_from_db()
    assert payment.amount == Decimal("10.00")
    assert payment.is_deleted is False


def test_completed_refund_reduces_amount_counted_as_paid(api_client, staff_user, order):
    from orders.models import OrderPayment, PaymentProvider, PaymentStatus, RefundStatus

    api_client.force_authenticate(user=staff_user)
    p1 = OrderPayment.objects.create(
        order=order, provider=PaymentProvider.CASH, status=PaymentStatus.COMPLETED, amount="5.00", currency="KES"
    )
    OrderPayment.objects.create(
        order=order, provider=PaymentProvider.CASH, status=PaymentStatus.COMPLETED, amount="5.00", currency="KES"
    )
    order.refresh_from_db()
    assert order.is_fully_paid is True

    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    resp = api_client.post(
        "/api/orders/staff/refunds/",
        {
            "payment": p1.id,
            "amount": "5.00",
            "status": "completed",
            "reason": "Partial return",
            "transaction_id": "txn-paid-1",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.json()["status"] == RefundStatus.COMPLETED

    order.refresh_from_db()
    p1.refresh_from_db()
    assert p1.status == PaymentStatus.REFUNDED
    assert order.is_fully_paid is False
    assert order.status == OrderStatus.CANCELLED


def test_staff_can_list_background_tasks(api_client, staff_user):
    api_client.force_authenticate(user=staff_user)
    resp = api_client.get("/api/orders/staff/background-tasks/")
    assert resp.status_code == status.HTTP_200_OK
    assert isinstance(resp.json(), list)


def test_staff_can_list_completed_background_tasks(api_client, staff_user):
    api_client.force_authenticate(user=staff_user)
    resp = api_client.get("/api/orders/staff/background-tasks/completed/")
    assert resp.status_code == status.HTTP_200_OK
    assert isinstance(resp.json(), list)


def test_staff_can_create_order_for_customer(api_client, staff_user, user):
    from orders.models import Cart, CartItem

    product = _product("Phone order vitamin", "15.00", 6)
    customer_cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=customer_cart, product=product, quantity=1)
    staff_cart = Cart.objects.create(user=staff_user)
    CartItem.objects.create(cart=staff_cart, product=product, quantity=1)

    api_client.force_authenticate(user=user)
    denied = api_client.post(
        "/api/orders/orders/",
        {
            "user": staff_user.id,
            "shipping_address": {
                "full_name": "John Doe",
                "phone": "0712345678",
                "email": "john@example.com",
                "address_line_1": "Street 1",
                "address_line_2": "",
                "city": "Nairobi",
                "state": "",
                "postal_code": "",
                "country": "Kenya",
            },
            "items": [{"product": product.id, "quantity": 1}],
        },
        format="json",
    )
    assert denied.status_code == status.HTTP_400_BAD_REQUEST

    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        "/api/orders/orders/",
        {
            "user": user.id,
            "shipping_address": {
                "full_name": "John Doe",
                "phone": "0712345678",
                "email": "john@example.com",
                "address_line_1": "Street 1",
                "address_line_2": "",
                "city": "Nairobi",
                "state": "",
                "postal_code": "",
                "country": "Kenya",
            },
            "items": [{"product": product.id, "quantity": 2}],
            "notes": "Placed by phone",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    assert body["user"] == user.id
    assert body["notes"] == "Placed by phone"
    assert body["total"] == "30.00"
    assert body["items"][0]["quantity"] == 2

    from orders.models import Order

    order = Order.objects.get(public_id=body["id"])
    assert order.user_id == user.id
    assert order.shipping_address.user_id == user.id
    customer_cart.refresh_from_db()
    staff_cart.refresh_from_db()
    assert customer_cart.items.count() == 0
    assert staff_cart.items.count() == 1
    product.refresh_from_db()
    assert product.stock == 4


def test_non_staff_cannot_list_background_tasks(api_client, user):
    api_client.force_authenticate(user=user)
    resp = api_client.get("/api/orders/staff/background-tasks/")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_non_staff_cannot_update_staff_payment_endpoint(api_client, user, order):
    from orders.models import OrderPayment, PaymentProvider

    payment = OrderPayment.objects.create(order=order, provider=PaymentProvider.CASH, amount="10.00", currency="KES")
    api_client.force_authenticate(user=user)
    resp = api_client.patch(
        f"/api/orders/staff/payments/{payment.id}/",
        {"status": "completed"},
        format="json",
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_is_fully_paid_uses_only_completed_and_not_deleted(api_client, staff_user, order):
    """
    - pending/failed payments should not count
    - deleted payments should not count
    - status/amount changes should trigger reevaluation
    """
    from orders.models import OrderPayment, PaymentProvider, PaymentStatus

    # pending payment (should not count)
    p1 = OrderPayment.objects.create(
        order=order, provider=PaymentProvider.CASH, status=PaymentStatus.PENDING, amount="10.00", currency="KES"
    )
    order.refresh_from_db()
    assert order.is_fully_paid is False

    # update to completed should trigger tick and start processing
    p1.status = PaymentStatus.COMPLETED
    p1.save(update_fields=["status", "updated_at"])
    order.refresh_from_db()
    assert order.is_fully_paid is True
    assert order.status == OrderStatus.PROCESSING

    api_client.force_authenticate(user=staff_user)
    resp = api_client.delete(f"/api/orders/staff/payments/{p1.id}/")
    assert resp.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    order.refresh_from_db()
    assert order.is_fully_paid is True

    # A stored soft-delete still drops the payment out of the paid sum.
    p1.soft_delete(user=staff_user)
    order.refresh_from_db()
    assert order.is_fully_paid is False
    assert order.status == OrderStatus.PAYMENT_PENDING


def _product(name, price, stock):
    from products.models import Product

    return Product.objects.create(
        name=name,
        description=name,
        price=price,
        stock=stock,
        slug=name.lower().replace(" ", "-"),
    )


def _open_order(user, total):
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
    return Order.objects.create(
        user=user,
        shipping_address=addr,
        subtotal=total,
        total=total,
        status=OrderStatus.PROCESSING,
    )


def test_staff_remove_unavailable_product_issues_partial_refund(api_client, staff_user, user):
    from orders.models import OrderItem, OrderPayment, PaymentStatus, RefundStatus

    kept = _product("Kept vitamin", "20.00", 4)
    gone = _product("Gone powder", "10.00", 3)
    order = _open_order(user, "30.00")
    OrderItem.objects.create(
        order=order, product=kept, product_name=kept.name, quantity=1, unit_price="20.00", line_total="20.00"
    )
    removed = OrderItem.objects.create(
        order=order, product=gone, product_name=gone.name, quantity=1, unit_price="10.00", line_total="10.00"
    )
    OrderPayment.objects.create(
        order=order, provider=PaymentProvider.CASH, status=PaymentStatus.COMPLETED, amount="30.00", currency="USD"
    )

    api_client.force_authenticate(user=user)
    denied = api_client.post(f"/api/orders/orders/{order.public_id}/items/{removed.id}/remove/", format="json")
    assert denied.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(f"/api/orders/orders/{order.public_id}/items/{removed.id}/remove/", format="json")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["total"] == "20.00"
    gone_line = next(item for item in body["items"] if item["product"] == gone.id)
    kept_line = next(item for item in body["items"] if item["product"] == kept.id)
    assert gone_line["availability"] == "unavailable"
    assert gone_line["line_total"] == "10.00"
    assert gone_line["availability_note"] == ""
    assert kept_line["availability"] == "pending"
    assert body["refunds"][0]["amount"] == "10.00"
    assert body["refunds"][0]["status"] == RefundStatus.INITIATED
    assert body["refunds"][0]["reason"] == "Marked Gone powder unavailable"
    assert body["refunds"][0]["transaction_id"]
    assert body["payments"][0]["status"] == PaymentStatus.REFUND_INITIATED
    assert body["is_fully_paid"] is True

    gone.refresh_from_db()
    assert gone.stock == 4
    assert gone.quantity_sold == 0
    kept.refresh_from_db()
    assert kept.quantity_sold == 1
    order.refresh_from_db()
    assert order.status == OrderStatus.PROCESSING


def test_staff_replace_product_refunds_the_price_difference(api_client, staff_user, user):
    from orders.models import OrderItem, OrderPayment, PaymentStatus, RefundStatus

    original = _product("Original tub", "20.00", 2)
    cheaper = _product("Cheaper tub", "12.00", 6)
    order = _open_order(user, "20.00")
    line = OrderItem.objects.create(
        order=order,
        product=original,
        product_name=original.name,
        quantity=1,
        unit_price="20.00",
        line_total="20.00",
    )
    OrderPayment.objects.create(
        order=order, provider=PaymentProvider.CASH, status=PaymentStatus.COMPLETED, amount="20.00", currency="USD"
    )

    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        f"/api/orders/orders/{order.public_id}/items/{line.id}/replace/",
        {"product": cheaper.id},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["total"] == "12.00"
    original_line = next(item for item in body["items"] if item["id"] == line.id)
    replacement = next(item for item in body["items"] if item["product"] == cheaper.id)
    assert original_line["availability"] == "replaced"
    assert original_line["product_name"] == "Original tub"
    assert original_line["replacement"] == replacement["id"]
    assert replacement["availability"] == "confirmed"
    assert replacement["product_name"] == "Cheaper tub"
    assert replacement["replaces"] == line.id
    assert body["refunds"][0]["amount"] == "8.00"
    assert body["refunds"][0]["status"] == RefundStatus.INITIATED

    original.refresh_from_db()
    cheaper.refresh_from_db()
    assert original.stock == 3
    assert cheaper.stock == 5


def test_replacing_with_a_dearer_product_does_not_refund(api_client, staff_user, user):
    from orders.models import OrderItem, OrderPayment, PaymentStatus

    original = _product("Small jar", "20.00", 2)
    dearer = _product("Large jar", "25.00", 4)
    order = _open_order(user, "20.00")
    line = OrderItem.objects.create(
        order=order,
        product=original,
        product_name=original.name,
        quantity=1,
        unit_price="20.00",
        line_total="20.00",
    )
    OrderPayment.objects.create(
        order=order, provider=PaymentProvider.CASH, status=PaymentStatus.COMPLETED, amount="20.00", currency="USD"
    )

    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        f"/api/orders/orders/{order.public_id}/items/{line.id}/replace/",
        {"product": dearer.id},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["total"] == "25.00"
    assert body["refunds"] == []
    assert body["is_fully_paid"] is False
    assert body["payments"][0]["status"] == PaymentStatus.COMPLETED


def test_shipping_waits_until_every_item_is_confirmed_unavailable_or_replaced(api_client, staff_user, user):
    from orders.models import OrderItem

    kept = _product("Ready capsule", "15.00", 4)
    missing = _product("Missing capsule", "5.00", 2)
    replacement = _product("Stand-in capsule", "5.00", 3)
    order = _open_order(user, "20.00")
    ready = OrderItem.objects.create(
        order=order, product=kept, product_name=kept.name, quantity=1, unit_price="15.00", line_total="15.00"
    )
    absent = OrderItem.objects.create(
        order=order, product=missing, product_name=missing.name, quantity=1, unit_price="5.00", line_total="5.00"
    )
    Shipment.objects.create(order=order)

    api_client.force_authenticate(user=staff_user)
    blocked = api_client.post(
        "/api/orders/staff/shipment-events/",
        {"shipment": order.shipment.id, "status": "DISPATCHED", "message": "Too soon"},
        format="json",
    )
    assert blocked.status_code == status.HTTP_400_BAD_REQUEST
    assert "Still unconfirmed" in str(blocked.json())
    order.refresh_from_db()
    assert order.status == OrderStatus.PROCESSING

    confirmed = api_client.post(
        f"/api/orders/orders/{order.public_id}/items/{ready.id}/confirm/",
        {"note": "Packed"},
        format="json",
    )
    assert confirmed.status_code == status.HTTP_200_OK
    assert confirmed.json()["items"][0]["availability"] == "confirmed"
    assert confirmed.json()["items"][0]["availability_note"] == "Packed"

    unavailable = api_client.post(
        f"/api/orders/orders/{order.public_id}/items/{absent.id}/unavailable/",
        {"note": "Supplier is out"},
        format="json",
    )
    assert unavailable.status_code == status.HTTP_200_OK
    body = unavailable.json()
    assert body["total"] == "15.00"
    missing_line = next(item for item in body["items"] if item["id"] == absent.id)
    assert missing_line["availability"] == "unavailable"
    assert missing_line["availability_note"] == "Supplier is out"

    swapped = api_client.post(
        f"/api/orders/orders/{order.public_id}/items/{ready.id}/replace/",
        {"product": replacement.id, "quantity": 1},
        format="json",
    )
    assert swapped.status_code == status.HTTP_200_OK
    shipped = api_client.post(
        "/api/orders/staff/shipment-events/",
        {"shipment": order.shipment.id, "status": "DISPATCHED", "message": "Left the warehouse"},
        format="json",
    )
    assert shipped.status_code == status.HTTP_201_CREATED
    order.refresh_from_db()
    assert order.status == OrderStatus.SHIPPING


def test_completed_order_lines_stay_unchanged(api_client, staff_user, user):
    from orders.models import OrderItem

    product = _product("Sealed bottle", "10.00", 2)
    order = _open_order(user, "10.00")
    order.status = OrderStatus.COMPLETE
    order.save(update_fields=["status", "updated_at"])
    line = OrderItem.objects.create(
        order=order, product=product, product_name=product.name, quantity=1, unit_price="10.00", line_total="10.00"
    )

    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(f"/api/orders/orders/{order.public_id}/items/{line.id}/remove/", format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert OrderItem.objects.filter(pk=line.id).exists()
