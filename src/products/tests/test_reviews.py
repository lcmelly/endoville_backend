import pytest
from rest_framework import status
from rest_framework.test import APIClient

from orders.models import LineAvailability, Order, OrderItem, OrderStatus, ShippingAddress
from products.models import Product, ProductReview, ReviewFlagReason
from users.models import CustomUser

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def customer():
    return CustomUser.objects.create_user(
        email="buyer@example.com",
        password="strongpass",
        first_name="Ada",
        is_active=True,
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
def product():
    return Product.objects.create(
        name="Vitamin D3",
        description="Daily vitamin",
        price="20.00",
        stock=10,
        slug="vitamin-d3-review",
    )


def _order(user, product, status=OrderStatus.COMPLETE, paid=True, include_product=True):
    address = ShippingAddress.objects.create(
        user=user,
        full_name="Ada Okonkwo",
        phone="+2348011100101",
        email=user.email,
        address_line_1="15 Admiralty Way",
        city="Lagos",
        country="Nigeria",
    )
    order = Order.objects.create(
        user=user,
        shipping_address=address,
        status=status,
        is_fully_paid=paid,
        subtotal="20.00",
        total="20.00",
    )
    if include_product:
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            quantity=1,
            unit_price="20.00",
            line_total="20.00",
            availability=LineAvailability.CONFIRMED,
        )
    return order


def test_review_requires_completed_order_containing_the_product(api_client, customer, product):
    pending = _order(customer, product, status=OrderStatus.PROCESSING)
    api_client.force_authenticate(user=customer)
    resp = api_client.post(
        "/api/products/product-reviews/",
        {"product": product.id, "order": pending.public_id, "rating": 5, "body": "Too soon"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "completed" in " ".join(resp.json()["order"])

    other = _order(customer, product, include_product=False)
    resp = api_client.post(
        "/api/products/product-reviews/",
        {"product": product.id, "order": other.public_id, "rating": 5, "body": "Wrong order"},
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST

    completed = _order(customer, product)
    resp = api_client.post(
        "/api/products/product-reviews/",
        {"product": product.id, "order": completed.public_id, "rating": 4, "body": "Good"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.json()["order"] == completed.public_id
    product.refresh_from_db()
    assert product.review_count == 1
    assert str(product.avg_rating) == "4.00"


def test_staff_flag_hides_review_and_drops_it_from_the_rating(api_client, customer, staff_user, product):
    other = CustomUser.objects.create_user(
        email="other@example.com",
        password="strongpass",
        is_active=True,
    )
    other_order = _order(other, product)
    api_client.force_authenticate(user=other)
    other_review = api_client.post(
        "/api/products/product-reviews/",
        {"product": product.id, "order": other_order.public_id, "rating": 5, "body": "Fine"},
        format="json",
    )
    assert other_review.status_code == status.HTTP_201_CREATED

    order = _order(customer, product)
    api_client.force_authenticate(user=customer)
    created = api_client.post(
        "/api/products/product-reviews/",
        {"product": product.id, "order": order.public_id, "rating": 1, "body": "abuse"},
        format="json",
    )
    review_id = created.json()["id"]

    api_client.force_authenticate(user=staff_user)
    deleted = api_client.delete(f"/api/products/product-reviews/{review_id}/")
    assert deleted.status_code == status.HTTP_403_FORBIDDEN
    assert "Flag" in deleted.json()["detail"]
    assert ProductReview.objects.filter(pk=review_id).exists()

    edited = api_client.patch(
        f"/api/products/product-reviews/{review_id}/",
        {"body": "rewritten by staff"},
        format="json",
    )
    assert edited.status_code == status.HTTP_403_FORBIDDEN

    missing_note = api_client.post(
        f"/api/products/product-reviews/{review_id}/flag/",
        {"reason": ReviewFlagReason.OTHER},
        format="json",
    )
    assert missing_note.status_code == status.HTTP_400_BAD_REQUEST

    flagged = api_client.post(
        f"/api/products/product-reviews/{review_id}/flag/",
        {"reason": ReviewFlagReason.PROFANITY, "note": ""},
        format="json",
    )
    assert flagged.status_code == status.HTTP_200_OK
    assert flagged.json()["flag_reason"] == ReviewFlagReason.PROFANITY
    assert flagged.json()["flag_note"] == ""

    product.refresh_from_db()
    assert product.review_count == 1
    assert str(product.avg_rating) == "5.00"

    public = APIClient().get("/api/products/product-reviews/", {"product": product.id})
    assert public.status_code == status.HTTP_200_OK
    assert [item["id"] for item in public.json()] == [other_review.json()["id"]]
    assert "flag_reason" not in public.json()[0]
    assert "is_flagged" not in public.json()[0]

    public_product = APIClient().get(f"/api/products/products/{product.id}/").json()
    assert [item["id"] for item in public_product["reviews"]] == [other_review.json()["id"]]
    assert public_product["review_count"] == 1
    assert public_product["avg_rating"] == "5.00"

    api_client.force_authenticate(user=other)
    hidden = api_client.get(f"/api/products/product-reviews/{review_id}/")
    assert hidden.status_code == status.HTTP_404_NOT_FOUND

    api_client.force_authenticate(user=customer)
    refused_flag = api_client.post(
        f"/api/products/product-reviews/{review_id}/flag/",
        {"reason": ReviewFlagReason.MALICIOUS},
        format="json",
    )
    assert refused_flag.status_code == status.HTTP_403_FORBIDDEN
    kept = api_client.patch(
        f"/api/products/product-reviews/{review_id}/",
        {"flag_reason": "", "is_flagged": False, "body": "still mine"},
        format="json",
    )
    assert kept.status_code == status.HTTP_200_OK
    assert kept.json()["flag_reason"] == ReviewFlagReason.PROFANITY
    assert kept.json()["is_flagged"] is True
    assert kept.json()["flagged_at"]
    assert kept.json()["body"] == "still mine"
    assert "flag_note" not in kept.json()

    own_product = api_client.get(f"/api/products/products/{product.id}/").json()
    own_line = next(item for item in own_product["reviews"] if item["id"] == review_id)
    assert own_line["is_flagged"] is True
    assert own_line["flag_reason"] == ReviewFlagReason.PROFANITY
    assert "flag_note" not in own_line

    api_client.force_authenticate(user=staff_user)
    staff_product = api_client.get(f"/api/products/products/{product.id}/").json()
    staff_line = next(item for item in staff_product["reviews"] if item["id"] == review_id)
    assert staff_line["is_flagged"] is True
    assert staff_line["flag_reason"] == ReviewFlagReason.PROFANITY
    assert staff_line["flag_note"] == ""

    api_client.force_authenticate(user=staff_user)
    restored = api_client.post(f"/api/products/product-reviews/{review_id}/unflag/", format="json")
    assert restored.status_code == status.HTTP_200_OK
    assert restored.json()["flag_reason"] == ""
    assert restored.json()["is_flagged"] is False
    product.refresh_from_db()
    assert product.review_count == 2
    assert str(product.avg_rating) == "3.00"


def test_review_author_can_delete_their_own_review(api_client, customer, product):
    order = _order(customer, product)
    api_client.force_authenticate(user=customer)
    created = api_client.post(
        "/api/products/product-reviews/",
        {"product": product.id, "order": order.public_id, "rating": 5, "body": "Great"},
        format="json",
    )
    review_id = created.json()["id"]
    resp = api_client.delete(f"/api/products/product-reviews/{review_id}/")
    assert resp.status_code == status.HTTP_204_NO_CONTENT
    product.refresh_from_db()
    assert product.review_count == 0


def test_review_follows_the_product_that_was_shipped(api_client, customer, staff_user, product):
    missing = Product.objects.create(
        name="Missing powder",
        description="Gone",
        price="8.00",
        stock=2,
        slug="missing-powder-review",
    )
    stand_in = Product.objects.create(
        name="Stand in",
        description="Shipped instead",
        price="8.00",
        stock=2,
        slug="stand-in-review",
    )
    order = _order(customer, product, status=OrderStatus.PROCESSING, paid=True)
    kept = order.items.get()
    kept.availability = LineAvailability.PENDING
    kept.save(update_fields=["availability"])
    absent = OrderItem.objects.create(
        order=order,
        product=missing,
        product_name=missing.name,
        quantity=1,
        unit_price="8.00",
        line_total="8.00",
    )
    order.mark_line_unavailable(absent, staff_user, note="Out of stock")
    order.replace_line(kept, stand_in, None, 1, staff_user)
    order.status = OrderStatus.COMPLETE
    order.is_fully_paid = True
    order.save(update_fields=["status", "is_fully_paid", "updated_at"])

    api_client.force_authenticate(user=customer)
    for skipped in (product, missing):
        refused = api_client.post(
            "/api/products/product-reviews/",
            {"product": skipped.id, "order": order.public_id, "rating": 5, "body": "Did not arrive"},
            format="json",
        )
        assert refused.status_code == status.HTTP_400_BAD_REQUEST
        assert "shipped" in " ".join(refused.json()["order"])

    accepted = api_client.post(
        "/api/products/product-reviews/",
        {"product": stand_in.id, "order": order.public_id, "rating": 4, "body": "This one arrived"},
        format="json",
    )
    assert accepted.status_code == status.HTTP_201_CREATED
    stand_in.refresh_from_db()
    assert stand_in.review_count == 1
