"""Password reset emails the account address only."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def active_user(db):
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
        first_name="John",
        last_name="Doe",
        is_active=True,
    )


@override_settings(FRONTEND_URL="https://shop.example.com")
def test_reset_link_is_sent_only_to_the_account_email(api_client, active_user):
    with patch("django.core.mail.send_mail") as mock_mail:
        response = api_client.post(
            "/api/users/password-reset/",
            {"email": "TEST@example.com"},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    mock_mail.assert_called_once()
    assert mock_mail.call_args.kwargs["recipient_list"] == [active_user.email]
    body = mock_mail.call_args.kwargs["message"]
    assert "https://shop.example.com/reset-password?uid=" in body
    assert "token=" in body


def test_reset_link_is_not_sent_when_no_account_exists(api_client, db):
    with patch("django.core.mail.send_mail") as mock_mail:
        response = api_client.post(
            "/api/users/password-reset/",
            {"email": "missing@example.com"},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    mock_mail.assert_not_called()


def test_reset_link_is_not_sent_to_an_inactive_account(api_client, db):
    User.objects.create_user(
        email="inactive@example.com",
        password="testpass123",
        is_active=False,
    )
    with patch("django.core.mail.send_mail") as mock_mail:
        response = api_client.post(
            "/api/users/password-reset/",
            {"email": "inactive@example.com"},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    mock_mail.assert_not_called()


def test_confirm_sets_a_new_password_and_rejects_the_used_link(api_client, active_user):
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    uid = urlsafe_base64_encode(force_bytes(active_user.pk))
    token = default_token_generator.make_token(active_user)
    response = api_client.post(
        "/api/users/password-reset/confirm/",
        {"uid": uid, "token": token, "password": "fresh-pass-4821"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    active_user.refresh_from_db()
    assert active_user.check_password("fresh-pass-4821")

    reuse = api_client.post(
        "/api/users/password-reset/confirm/",
        {"uid": uid, "token": token, "password": "another-pass-4821"},
        format="json",
    )
    assert reuse.status_code == status.HTTP_400_BAD_REQUEST
    active_user.refresh_from_db()
    assert active_user.check_password("fresh-pass-4821")


def test_confirm_rejects_a_token_for_a_different_account(api_client, active_user, db):
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    other = User.objects.create_user(
        email="other@example.com",
        password="testpass123",
        is_active=True,
    )
    uid = urlsafe_base64_encode(force_bytes(other.pk))
    token = default_token_generator.make_token(active_user)
    response = api_client.post(
        "/api/users/password-reset/confirm/",
        {"uid": uid, "token": token, "password": "fresh-pass-4821"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    other.refresh_from_db()
    assert other.check_password("testpass123")
