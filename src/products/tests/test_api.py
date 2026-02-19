import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from products.models import (
    Category,
    Currency,
    Product,
    ProductVariant,
    Subcategory,
    VariationAttribute,
    VariationOption,
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
def category():
    return Category.objects.create(name="Category A", description="desc")


@pytest.fixture
def subcategory(category):
    return Subcategory.objects.create(name="Sub A", category=category)


@pytest.fixture
def product(subcategory):
    p = Product.objects.create(
        name="Product A",
        description="desc",
        price="10.00",
        stock=5,
        image_urls=["https://example.com/1.png"],
        meta_title="mt",
        meta_description="md",
        slug="product-a",
    )
    p.subcategories.add(subcategory)
    return p


@pytest.fixture
def color_attribute():
    return VariationAttribute.objects.create(name="Color")


@pytest.fixture
def red_option(color_attribute):
    return VariationOption.objects.create(attribute=color_attribute, value="Red")


@pytest.fixture
def variant(product, red_option):
    v = ProductVariant.objects.create(
        product=product,
        sku="SKU-1",
        barcode="BARCODE-1",
        price="12.50",
        stock=2,
        image_urls=["https://example.com/v1.png"],
    )
    v.options.add(red_option)
    return v


def test_urls_resolve():
    assert reverse("products:currency-list") == "/api/products/currencies/"
    assert reverse("products:product-list") == "/api/products/products/"
    assert reverse("products:variant-list") == "/api/products/variants/"
    assert reverse("products:category-list") == "/api/products/categories/"
    assert reverse("products:subcategory-list") == "/api/products/subcategories/"
    assert (
        reverse("products:variation-attribute-list")
        == "/api/products/variation-attributes/"
    )
    assert (
        reverse("products:variation-option-list")
        == "/api/products/variation-options/"
    )


def test_currencies_list_public(api_client):
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    resp = api_client.get("/api/products/currencies/")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["code"] == "USD"
    assert data[0]["usd_rate"] == "1.000000"


def test_currencies_crud_staff_only(api_client, staff_user):
    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        "/api/products/currencies/",
        {"code": "KES", "name": "Kenyan Shilling", "symbol": "KSh", "usd_rate": "160.50"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.json()["code"] == "KES"
    assert resp.json()["usd_rate"] == "160.500000"


def test_products_list_public(api_client, product):
    resp = api_client.get("/api/products/products/")
    assert resp.status_code == status.HTTP_200_OK


def test_variants_list_public(api_client, variant):
    resp = api_client.get("/api/products/variants/")
    assert resp.status_code == status.HTTP_200_OK


def test_product_detail_includes_variants(api_client, product, variant):
    resp = api_client.get(f"/api/products/products/{product.id}/")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["id"] == product.id
    assert "variants" in data
    assert len(data["variants"]) == 1
    assert data["variants"][0]["barcode"] == "BARCODE-1"
    assert data["variants"][0]["options_details"][0]["value"] == "Red"
    assert "cost_price" not in data
    assert "cost_price" not in data["variants"][0]
    assert "image_refs" in data
    assert "image_refs" in data["variants"][0]


def test_product_list_returns_currency_and_symbol(api_client, product, staff_user):
    """Product list includes display_currency and currency_symbol for non-staff and staff."""
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    # Non-staff list
    resp = api_client.get("/api/products/products/")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["display_currency"] == "USD"
    assert data[0]["currency_symbol"] == "$"
    # Staff list
    api_client.force_authenticate(user=staff_user)
    resp = api_client.get("/api/products/products/")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data[0]["display_currency"] == "USD"
    assert data[0]["currency_symbol"] == "$"


def test_product_currency_param_returns_correct_currency_and_symbol(api_client, product, variant):
    """?currency= param returns correct display_currency and currency_symbol."""
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    Currency.objects.create(code="KES", name="Kenyan Shilling", symbol="KSh", usd_rate=160.50, is_active=True)
    Currency.objects.create(code="EUR", name="Euro", symbol="€", usd_rate=0.92, is_active=True)
    # KES
    resp = api_client.get(f"/api/products/products/{product.id}/", {"currency": "KES"})
    data = resp.json()
    assert data["display_currency"] == "KES"
    assert data["currency_symbol"] == "KSh"
    assert data["variants"][0]["display_currency"] == "KES"
    assert data["variants"][0]["currency_symbol"] == "KSh"
    # EUR
    resp = api_client.get(f"/api/products/products/{product.id}/", {"currency": "EUR"})
    data = resp.json()
    assert data["display_currency"] == "EUR"
    assert data["currency_symbol"] == "€"
    # Case insensitive
    resp = api_client.get(f"/api/products/products/{product.id}/", {"currency": "kes"})
    data = resp.json()
    assert data["display_currency"] == "KES"
    assert data["currency_symbol"] == "KSh"


def test_product_invalid_currency_falls_back_to_primary(api_client, product):
    """Invalid ?currency= falls back to primary currency (USD)."""
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    resp = api_client.get(f"/api/products/products/{product.id}/", {"currency": "XXX"})
    assert resp.status_code == status.HTTP_200_OK
    # No XXX currency exists, so falls back to primary USD
    data = resp.json()
    assert data["display_currency"] == "USD"
    assert data["currency_symbol"] == "$"
    assert data["price"] == "10.00"


def test_variant_list_and_detail_return_currency_and_symbol(api_client, variant):
    """Variant list and retrieve include display_currency and currency_symbol."""
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    Currency.objects.create(code="KES", name="Kenyan Shilling", symbol="KSh", usd_rate=160.50, is_active=True)
    # List default (USD)
    resp = api_client.get("/api/products/variants/")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["display_currency"] == "USD"
    assert data[0]["currency_symbol"] == "$"
    # List with ?currency=KES
    resp = api_client.get("/api/products/variants/", {"currency": "KES"})
    data = resp.json()
    assert data[0]["display_currency"] == "KES"
    assert data[0]["currency_symbol"] == "KSh"
    assert data[0]["price"] == "2006.25"  # 12.50 * 160.50
    # Retrieve with ?currency=KES
    resp = api_client.get(f"/api/products/variants/{variant.id}/", {"currency": "KES"})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["display_currency"] == "KES"
    assert data["currency_symbol"] == "KSh"
    assert data["price"] == "2006.25"


def test_product_detail_currency_conversion_non_staff(api_client, product, variant):
    """Non-staff GET with ?currency= returns converted price, display_currency, currency_symbol."""
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)
    Currency.objects.create(code="KES", name="Kenyan Shilling", symbol="KSh", usd_rate=160.50, is_active=True)
    # With ?currency=KES: converted prices
    resp = api_client.get(f"/api/products/products/{product.id}/", {"currency": "KES"})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["price"] == "1605.00"
    assert data["display_currency"] == "KES"
    assert data["currency_symbol"] == "KSh"
    assert data["variants"][0]["price"] == "2006.25"
    assert data["variants"][0]["display_currency"] == "KES"
    assert data["variants"][0]["currency_symbol"] == "KSh"
    # Without ?currency=: default primary (USD), symbol included
    resp2 = api_client.get(f"/api/products/products/{product.id}/")
    assert resp2.status_code == status.HTTP_200_OK
    data2 = resp2.json()
    assert data2["price"] == "10.00"
    assert data2["display_currency"] == "USD"
    assert data2["currency_symbol"] == "$"


def test_cost_price_visible_to_staff(api_client, staff_user, product, variant):
    product.cost_price = "6.00"
    product.save(update_fields=["cost_price"])
    variant.cost_price = "7.00"
    variant.save(update_fields=["cost_price"])
    Currency.objects.create(code="USD", name="US Dollar", symbol="$", usd_rate=1, is_primary=True)

    api_client.force_authenticate(user=staff_user)
    resp = api_client.get(f"/api/products/products/{product.id}/")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["cost_price"] == "6.00"
    assert data["variants"][0]["cost_price"] == "7.00"
    assert data["display_currency"] == "USD"
    assert data["currency_symbol"] == "$"
    assert data["variants"][0]["display_currency"] == "USD"
    assert data["variants"][0]["currency_symbol"] == "$"


def test_writes_are_staff_only(api_client, user, staff_user):
    api_client.force_authenticate(user=user)
    resp = api_client.post("/api/products/categories/", {"name": "X"}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        "/api/products/categories/",
        {"name": "Cat X", "description": "d"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED


def test_staff_can_create_subcategory(api_client, staff_user, category):
    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        "/api/products/subcategories/",
        {"name": "Sub X", "category": category.id},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED


def test_staff_can_create_variation_attribute_and_option(api_client, staff_user):
    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        "/api/products/variation-attributes/",
        {"name": "Size"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    attr_id = resp.json()["id"]

    resp = api_client.post(
        "/api/products/variation-options/",
        {"attribute": attr_id, "value": "XL"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED


def test_staff_can_create_variant_via_api(api_client, staff_user, product, red_option):
    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        "/api/products/variants/",
        {
            "product": product.id,
            "options": [red_option.id],
            "sku": "SKU-NEW",
            "barcode": "BARCODE-NEW",
            "price": "15.00",
            "stock": 9,
            "image_urls": ["https://example.com/v2.png"],
            "is_active": True,
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    assert ProductVariant.objects.filter(barcode="BARCODE-NEW", product=product).exists()


def test_variant_barcode_must_be_unique(api_client, staff_user, product, red_option):
    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        "/api/products/variants/",
        {
            "product": product.id,
            "options": [red_option.id],
            "sku": "SKU-1",
            "barcode": "DUPLICATE",
            "price": "10.00",
            "stock": 1,
            "image_urls": [],
            "is_active": True,
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED

    resp = api_client.post(
        "/api/products/variants/",
        {
            "product": product.id,
            "options": [red_option.id],
            "sku": "SKU-2",
            "barcode": "DUPLICATE",
            "price": "11.00",
            "stock": 2,
            "image_urls": [],
            "is_active": True,
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST

