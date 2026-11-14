from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from orders.models import Order, OrderItem, OrderStatus, ShippingAddress
from products.models import Brand, Category, Product, Subcategory
from users.models import CustomUser


pytestmark = pytest.mark.django_db


def _product(name, brand, stock=5):
    return Product.objects.create(
        name=name,
        description=name,
        brand=brand,
        price="10.00",
        stock=stock,
        slug=name.lower().replace(" ", "-"),
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
    return Order.objects.create(user=user, shipping_address=address, subtotal="20.00", total="20.00")


def test_brand_and_category_counts_follow_products_and_sales():
    user = CustomUser.objects.create_user(email="shopper@example.com", password="strongpass", is_active=True)
    brand = Brand.objects.create(name="North")
    other = Brand.objects.create(name="South")
    category = Category.objects.create(name="Vitamins")
    daily = Subcategory.objects.create(name="Daily", category=category)
    minerals = Subcategory.objects.create(name="Minerals", category=category)
    other_category = Category.objects.create(name="Care")
    treatment = Subcategory.objects.create(name="Treatment", category=other_category)

    product = _product("Serum", brand)
    product.subcategories.add(daily, minerals)
    brand.refresh_from_db()
    category.refresh_from_db()
    assert brand.products_count == 1
    assert category.products_count == 1

    product.subcategories.add(treatment)
    other_category.refresh_from_db()
    category.refresh_from_db()
    assert other_category.products_count == 1
    assert category.products_count == 1

    product.brand = other
    product.save(update_fields=["brand"])
    brand.refresh_from_db()
    other.refresh_from_db()
    assert brand.products_count == 0
    assert other.products_count == 1

    order = _order(user)
    OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        quantity=2,
        unit_price="10.00",
        line_total="20.00",
    )
    other.refresh_from_db()
    category.refresh_from_db()
    other_category.refresh_from_db()
    product.refresh_from_db()
    assert other.products_sold == 2
    assert category.products_sold == 2
    assert other_category.products_sold == 2
    assert product.quantity_sold == 2
    assert product.revenue == Decimal("20.00")

    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    other.refresh_from_db()
    category.refresh_from_db()
    product.refresh_from_db()
    assert other.products_sold == 0
    assert category.products_sold == 0
    assert product.quantity_sold == 0
    assert product.revenue == Decimal("0.00")

    order.status = OrderStatus.PROCESSING
    order.save(update_fields=["status", "updated_at"])
    kept = _product("Capsule", brand)
    kept.subcategories.add(daily)
    line = order.items.get()
    line.product = kept
    line.quantity = 1
    line.line_total = "10.00"
    line.save()
    other.refresh_from_db()
    brand.refresh_from_db()
    category.refresh_from_db()
    other_category.refresh_from_db()
    product.refresh_from_db()
    kept.refresh_from_db()
    assert other.products_sold == 0
    assert brand.products_sold == 1
    assert category.products_sold == 1
    assert other_category.products_sold == 0
    assert product.quantity_sold == 0
    assert product.revenue == Decimal("0.00")
    assert kept.quantity_sold == 1
    assert kept.revenue == Decimal("10.00")

    line.delete()
    brand.refresh_from_db()
    category.refresh_from_db()
    kept.refresh_from_db()
    assert brand.products_sold == 0
    assert category.products_sold == 0
    assert kept.quantity_sold == 0
    assert kept.revenue == Decimal("0.00")

    daily.category = other_category
    daily.save()
    category.refresh_from_db()
    other_category.refresh_from_db()
    assert category.products_count == 1
    assert other_category.products_count == 2

    product.delete()
    other.refresh_from_db()
    other_category.refresh_from_db()
    category.refresh_from_db()
    assert other.products_count == 0
    assert other_category.products_count == 1
    assert category.products_count == 0


def test_sold_units_follow_the_product_when_its_brand_or_category_changes():
    user = CustomUser.objects.create_user(email="mover@example.com", password="strongpass", is_active=True)
    north = Brand.objects.create(name="North sold")
    south = Brand.objects.create(name="South sold")
    vitamins = Category.objects.create(name="Vitamins sold")
    care = Category.objects.create(name="Care sold")
    daily = Subcategory.objects.create(name="Daily sold", category=vitamins)
    minerals = Subcategory.objects.create(name="Minerals sold", category=vitamins)
    product = _product("Moving serum", north)
    product.subcategories.add(daily, minerals)

    order = _order(user)
    OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        quantity=2,
        unit_price="10.00",
        line_total="20.00",
    )

    product.brand = south
    product.save(update_fields=["brand"])
    north.refresh_from_db()
    south.refresh_from_db()
    product.refresh_from_db()
    assert north.products_sold == 0
    assert south.products_sold == 2
    assert product.quantity_sold == 2

    product.subcategories.remove(daily)
    vitamins.refresh_from_db()
    assert vitamins.products_sold == 2

    product.subcategories.remove(minerals)
    vitamins.refresh_from_db()
    assert vitamins.products_sold == 0

    product.subcategories.add(daily)
    daily.category = care
    daily.save()
    vitamins.refresh_from_db()
    care.refresh_from_db()
    assert vitamins.products_sold == 0
    assert care.products_sold == 2

    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    north.refresh_from_db()
    south.refresh_from_db()
    vitamins.refresh_from_db()
    care.refresh_from_db()
    assert north.products_sold == 0
    assert south.products_sold == 0
    assert vitamins.products_sold == 0
    assert care.products_sold == 0

    order.status = OrderStatus.PROCESSING
    order.save(update_fields=["status", "updated_at"])
    south.refresh_from_db()
    care.refresh_from_db()
    assert south.products_sold == 2
    assert care.products_sold == 2

    product.delete()
    south.refresh_from_db()
    care.refresh_from_db()
    assert south.products_count == 0
    assert south.products_sold == 0
    assert care.products_count == 0
    assert care.products_sold == 0


def test_brand_and_category_responses_include_stored_counts():
    brand = Brand.objects.create(name="Listed")
    category = Category.objects.create(name="Listed care")
    client = APIClient()

    brands = client.get("/api/products/brands/").json()
    categories = client.get("/api/products/categories/").json()
    listed_brand = next(row for row in brands if row["id"] == brand.id)
    listed_category = next(row for row in categories if row["id"] == category.id)
    assert listed_brand["products_count"] == 0
    assert listed_brand["products_sold"] == 0
    assert listed_category["products_count"] == 0
    assert listed_category["products_sold"] == 0


def test_quantity_sold_is_public_and_revenue_is_staff_only():
    from users.models import CustomUser

    brand = Brand.objects.create(name="Private")
    product = _product("Private serum", brand)
    product.quantity_sold = 3
    product.revenue = "30.00"
    product.save(update_fields=["quantity_sold", "revenue"])
    shopper = CustomUser.objects.create_user(email="buyer@example.com", password="strongpass", is_active=True)
    staff = CustomUser.objects.create_user(
        email="staff-sales@example.com", password="strongpass", is_active=True, is_staff=True
    )
    client = APIClient()

    public = client.get(f"/api/products/products/{product.id}/")
    assert public.status_code == 200
    assert public.json()["quantity_sold"] == 3
    assert "revenue" not in public.json()

    client.force_authenticate(user=shopper)
    hidden = client.get(f"/api/products/products/{product.id}/")
    assert hidden.json()["quantity_sold"] == 3
    assert "revenue" not in hidden.json()

    client.force_authenticate(user=staff)
    visible = client.get(f"/api/products/products/{product.id}/")
    body = visible.json()
    assert body["quantity_sold"] == 3
    assert body["revenue"] == "30.00"
