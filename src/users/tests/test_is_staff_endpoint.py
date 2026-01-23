import pytest
from rest_framework import status
from rest_framework.test import APIClient

from users.models import CustomUser


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def test_is_staff_requires_auth(api_client):
    resp = api_client.get("/api/users/is-staff/")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_is_staff_false_for_normal_user(api_client):
    user = CustomUser.objects.create_user(email="u@example.com", password="pass", is_active=True)
    api_client.force_authenticate(user=user)
    resp = api_client.get("/api/users/is-staff/")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {"is_staff": False}


def test_is_staff_true_for_staff_user(api_client):
    user = CustomUser.objects.create_user(
        email="staff@example.com", password="pass", is_active=True, is_staff=True
    )
    api_client.force_authenticate(user=user)
    resp = api_client.get("/api/users/is-staff/")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json() == {"is_staff": True}

