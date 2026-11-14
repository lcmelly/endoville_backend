import pytest
from django.core.management import call_command

from orders.models import Cart, Order, OrderStatus, ShippingStatus
from products.models import Product
from users.models import CustomUser

pytestmark = pytest.mark.django_db


def test_seed_sandbox_is_idempotent():
    call_command("seed_sandbox")
    call_command("seed_sandbox")

    staff = CustomUser.objects.get(email="sandbox.staff@endovillehealth.com")
    assert staff.is_staff
    assert staff.is_superuser

    assert Product.objects.filter(slug="vitamin-d3").exists()
    assert Product.objects.filter(slug="specialist-serum").exists()
    assert Order.objects.filter(notes__startswith="sandbox:").count() == 4

    pending = Order.objects.get(notes="sandbox:payment-pending")
    assert pending.status == OrderStatus.PAYMENT_PENDING
    assert pending.is_fully_paid is False

    processing = Order.objects.get(notes="sandbox:processing")
    assert processing.status == OrderStatus.PROCESSING
    assert processing.is_fully_paid is True
    assert processing.shipment.status == ShippingStatus.ORDER_PLACED

    shipping = Order.objects.get(notes="sandbox:shipping")
    assert shipping.status == OrderStatus.SHIPPING
    assert shipping.shipment.tracking_number == "SBX998877"

    complete = Order.objects.get(notes="sandbox:complete")
    assert complete.status == OrderStatus.COMPLETE
    assert complete.shipment.status == ShippingStatus.DELIVERED

    bola = CustomUser.objects.get(email="bola.sandbox@example.com")
    assert Cart.objects.get(user=bola).items.count() == 2
