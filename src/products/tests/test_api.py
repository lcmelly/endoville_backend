import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from products.models import (
    Category,
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

