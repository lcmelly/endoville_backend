import pytest
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import OrderItem, OrderStatus, PaymentProvider, ShippingAddress
from products.models import Product, ProductVariant
from users.models import CustomUser, StaffChangeLog


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def staff_user():
    return CustomUser.objects.create_user(
        email="audit-staff@example.com",
        password="strongpass",
        is_active=True,
        is_staff=True,
    )


@pytest.fixture
def user():
    return CustomUser.objects.create_user(
        email="audit-shopper@example.com",
        password="strongpass",
        is_active=True,
    )


def _order(user):
    address = ShippingAddress.objects.create(
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
    from orders.models import Order, Shipment

    order = Order.objects.create(user=user, shipping_address=address, subtotal="10.00", total="10.00")
    Shipment.objects.create(order=order)
    return order


def test_shopper_and_model_saves_are_not_logged(user):
    product = Product.objects.create(
        name="Quiet vitamin",
        description="Quiet",
        price="10.00",
        stock=4,
        slug="quiet-vitamin",
    )
    product.price = "12.00"
    product.save(update_fields=["price", "updated_at"])
    assert StaffChangeLog.objects.count() == 0

    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get("/api/users/staff-changes/")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_staff_changes_to_orders_payments_prices_and_refunds_are_logged(api_client, staff_user, user):
    product = Product.objects.create(
        name="Logged serum",
        description="Serum",
        price="10.00",
        cost_price="4.00",
        stock=5,
        slug="logged-serum",
    )
    variant = ProductVariant.objects.create(product=product, price="10.00", cost_price="4.00", stock=5)
    order = _order(user)
    kept = Product.objects.create(name="Kept capsule", description="Kept", price="6.00", stock=5, slug="kept-capsule")
    OrderItem.objects.create(
        order=order, product=product, product_name=product.name, quantity=1, unit_price="10.00", line_total="10.00"
    )

    api_client.force_authenticate(user=staff_user)
    price = api_client.patch(f"/api/products/products/{product.id}/", {"price": "11.00", "cost_price": "5.00"}, format="json")
    assert price.status_code == status.HTTP_200_OK
    variant_price = api_client.patch(
        f"/api/products/variants/{variant.id}/",
        {"price": "9.00"},
        format="json",
    )
    assert variant_price.status_code == status.HTTP_200_OK
    stock_only = api_client.patch(f"/api/products/products/{product.id}/", {"stock": 4}, format="json")
    assert stock_only.status_code == status.HTTP_200_OK

    payment = api_client.post(
        "/api/orders/staff/payments/",
        {
            "order": order.public_id,
            "provider": PaymentProvider.CASH,
            "status": "completed",
            "amount": "10.00",
            "currency": "USD",
            "transaction_id": "txn-audit-pay-1",
        },
        format="json",
    )
    assert payment.status_code == status.HTTP_201_CREATED
    order.refresh_from_db()
    assert order.status == OrderStatus.PROCESSING

    removed = api_client.post(f"/api/orders/orders/{order.public_id}/items/{order.items.get().id}/remove/", {}, format="json")
    assert removed.status_code == status.HTTP_200_OK

    replaced_item = OrderItem.objects.create(
        order=order, product=kept, product_name=kept.name, quantity=1, unit_price="6.00", line_total="6.00"
    )
    order.recalculate_totals()
    replaced = api_client.post(
        f"/api/orders/orders/{order.public_id}/items/{replaced_item.id}/replace/",
        {"product": product.id, "quantity": 1},
        format="json",
    )
    assert replaced.status_code == status.HTTP_200_OK

    dispatched = api_client.post(
        "/api/orders/staff/shipment-events/",
        {"shipment": order.shipment.id, "status": "DISPATCHED", "message": "Left the warehouse"},
        format="json",
    )
    assert dispatched.status_code == status.HTTP_201_CREATED

    cancelled = api_client.patch(f"/api/orders/orders/{order.public_id}/", {"status": "CANCELLED"}, format="json")
    assert cancelled.status_code == status.HTTP_200_OK
    refund_id = order.refunds.order_by("-id").first().id
    completed = api_client.patch(
        f"/api/orders/staff/refunds/{refund_id}/",
        {"status": "completed"},
        format="json",
    )
    assert completed.status_code == status.HTTP_200_OK

    actions = list(StaffChangeLog.objects.filter(actor=staff_user).values_list("action", flat=True))
    assert "product.price_changed" in actions
    assert "variant.price_changed" in actions
    assert actions.count("product.price_changed") == 1
    assert "payment.recorded" in actions
    assert "order.status_changed" in actions
    assert "order.line_removed" in actions
    assert "order.line_replaced" in actions
    assert "refund.recorded" in actions
    assert "refund.status_changed" in actions

    price_row = StaffChangeLog.objects.get(action="product.price_changed")
    assert price_row.changes["price"] == {"from": "10.00", "to": "11.00"}
    assert price_row.changes["cost_price"] == {"from": "4.00", "to": "5.00"}
    assert price_row.actor_id == staff_user.id

    listing = api_client.get("/api/users/staff-changes/", {"order_id": order.id, "target_type": "order"})
    assert listing.status_code == status.HTTP_200_OK
    body = listing.json()
    assert body
    assert {row["target_type"] for row in body} == {"order"}
    assert {row["order_id"] for row in body} == {order.id}
    assert body[0]["actor_email"] == staff_user.email
