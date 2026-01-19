import pytest
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return CustomUser.objects.create_user(
        email="user@example.com",
        password="strongpass",
        is_active=True,
        phone="+254700000000",
        first_name="John",
        last_name="Doe",
    )


def test_me_requires_auth(api_client):
    resp = api_client.get("/api/users/me/")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_me_patch_updates_names_and_image_only(api_client, user):
    api_client.force_authenticate(user=user)
    resp = api_client.patch(
        "/api/users/me/",
        {
            "first_name": "Jane",
            "last_name": "Roe",
            "image_url": "https://cdn.example.com/u/1.png",
            "gender": "F",
            "date_of_birth": "1998-02-25",
            "email": "new@example.com",
            "phone": "+254799999999",
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK

    user.refresh_from_db()
    assert user.first_name == "Jane"
    assert user.last_name == "Roe"
    assert user.image_url == "https://cdn.example.com/u/1.png"
    assert user.gender == "F"
    assert str(user.date_of_birth) == "1998-02-25"
    # email/phone unchanged
    assert user.email == "user@example.com"
    assert user.phone == "+254700000000"
