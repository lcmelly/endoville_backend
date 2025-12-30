"""Tests for Login API Views"""

import pytest
import json
from unittest.mock import patch, Mock
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
from users.models import OTP
from allauth.socialaccount.models import SocialAccount

User = get_user_model()


@pytest.fixture
def api_client():
    """Create API client"""
    return APIClient()


@pytest.fixture
def active_user(db):
    """Create an active user with password"""
    return User.objects.create_user(
        email='test@example.com',
        password='testpass123',
        first_name='John',
        last_name='Doe',
        is_active=True
    )


@pytest.fixture
def inactive_user(db):
    """Create an inactive user"""
    return User.objects.create_user(
        email='inactive@example.com',
        password='testpass123',
        is_active=False
    )


@pytest.fixture
def valid_otp(db, active_user):
    """Create a valid OTP for active user"""
    return OTP.create_otp(email=active_user.email)


# Login View Tests
@pytest.mark.django_db
def test_login_view_success(api_client, active_user, valid_otp):
    """Login view returns JWT tokens on successful login"""
    url = '/api/users/login/'
    data = {
        'email': 'test@example.com',
        'password': 'testpass123',
        'otp': valid_otp.otp
    }
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_200_OK
    assert 'access' in response.data
    assert 'refresh' in response.data
    assert 'user' in response.data
    assert response.data['user']['email'] == 'test@example.com'
    assert response.data['user']['id'] == active_user.id


@pytest.mark.django_db
def test_login_view_updates_last_login(api_client, active_user, valid_otp):
    """Login view updates user's last_login timestamp"""
    url = '/api/users/login/'
    data = {
        'email': 'test@example.com',
        'password': 'testpass123',
        'otp': valid_otp.otp
    }
    
    initial_last_login = active_user.last_login
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_200_OK
    active_user.refresh_from_db()
    if hasattr(active_user, 'last_login'):
        assert active_user.last_login is not None
        if initial_last_login:
            assert active_user.last_login > initial_last_login


@pytest.mark.django_db
def test_login_view_invalid_credentials(api_client, active_user, valid_otp):
    """Login view rejects invalid password"""
    url = '/api/users/login/'
    data = {
        'email': 'test@example.com',
        'password': 'wrongpassword',
        'otp': valid_otp.otp
    }
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'password' in response.data


@pytest.mark.django_db
def test_login_view_invalid_otp(api_client, active_user):
    """Login view rejects invalid OTP"""
    OTP.create_otp(email=active_user.email)
    url = '/api/users/login/'
    data = {
        'email': 'test@example.com',
        'password': 'testpass123',
        'otp': '000000'
    }
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'otp' in response.data


@pytest.mark.django_db
def test_login_view_inactive_user(api_client, inactive_user):
    """Login view rejects inactive user"""
    otp = OTP.create_otp(email=inactive_user.email)
    url = '/api/users/login/'
    data = {
        'email': 'inactive@example.com',
        'password': 'testpass123',
        'otp': otp.otp
    }
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'email' in response.data
    assert 'not activated' in str(response.data['email']).lower()


@pytest.mark.django_db
def test_login_view_user_not_found(api_client, valid_otp):
    """Login view rejects non-existent user"""
    url = '/api/users/login/'
    data = {
        'email': 'nonexistent@example.com',
        'password': 'testpass123',
        'otp': valid_otp.otp
    }
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'email' in response.data


@pytest.mark.django_db
def test_login_view_missing_fields(api_client):
    """Login view requires all fields"""
    url = '/api/users/login/'
    
    # Missing email
    response = api_client.post(url, {'password': 'test', 'otp': '123456'}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    # Missing password
    response = api_client.post(url, {'email': 'test@example.com', 'otp': '123456'}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    # Missing OTP
    response = api_client.post(url, {'email': 'test@example.com', 'password': 'test'}, format='json')
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_login_view_email_case_insensitive(api_client, active_user, valid_otp):
    """Login view handles email case insensitivity"""
    url = '/api/users/login/'
    data = {
        'email': 'TEST@EXAMPLE.COM',
        'password': 'testpass123',
        'otp': valid_otp.otp
    }
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data['user']['email'] == 'test@example.com'


@pytest.mark.django_db
def test_login_view_expired_otp(api_client, active_user):
    """Login view rejects expired OTP"""
    otp = OTP.create_otp(email=active_user.email)
    otp.expires_at = timezone.now() - timedelta(minutes=1)
    otp.save()
    
    url = '/api/users/login/'
    data = {
        'email': 'test@example.com',
        'password': 'testpass123',
        'otp': otp.otp
    }
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'otp' in response.data


# Google Login View Tests
@pytest.mark.django_db
@patch('requests.get')
def test_google_login_view_success_new_user(mock_get, api_client):
    """Google login view creates new user and returns JWT tokens"""
    # Mock Google API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'id': '123456789',
        'email': 'googleuser@gmail.com',
        'given_name': 'Google',
        'family_name': 'User',
        'verified_email': True
    }
    mock_get.return_value = mock_response
    
    url = '/api/users/google-login/'
    data = {
        'access_token': 'valid_google_token'
    }
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_200_OK
    assert 'access' in response.data
    assert 'refresh' in response.data
    assert 'user' in response.data
    assert response.data['user']['email'] == 'googleuser@gmail.com'
    assert response.data['user']['first_name'] == 'Google'
    assert response.data['user']['last_name'] == 'User'
    assert response.data['user']['is_active'] is True
    
    # Verify user was created
    user = User.objects.get(email='googleuser@gmail.com')
    assert user is not None
    assert not user.has_usable_password()
    
    # Verify social account was created
    social_account = SocialAccount.objects.get(user=user, provider='google')
    assert social_account.uid == '123456789'


@pytest.mark.django_db
@patch('requests.get')
def test_google_login_view_existing_user(mock_get, api_client, active_user):
    """Google login view links to existing user by email"""
    # Mock Google API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'id': '123456789',
        'email': active_user.email,
        'given_name': 'Updated',
        'family_name': 'Name',
        'verified_email': True
    }
    mock_get.return_value = mock_response
    
    url = '/api/users/google-login/'
    data = {
        'access_token': 'valid_google_token'
    }
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data['user']['id'] == active_user.id
    assert response.data['user']['email'] == active_user.email
    
    # Verify social account was created
    social_account = SocialAccount.objects.get(user=active_user, provider='google')
    assert social_account.uid == '123456789'


@pytest.mark.django_db
@patch('requests.get')
def test_google_login_view_updates_last_login(mock_get, api_client, active_user):
    """Google login view updates user's last_login"""
    # Mock Google API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'id': '123456789',
        'email': active_user.email,
        'given_name': 'Test',
        'family_name': 'User',
        'verified_email': True
    }
    mock_get.return_value = mock_response
    
    url = '/api/users/google-login/'
    data = {
        'access_token': 'valid_google_token'
    }
    
    initial_last_login = active_user.last_login
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_200_OK
    active_user.refresh_from_db()
    if hasattr(active_user, 'last_login'):
        assert active_user.last_login is not None
        if initial_last_login:
            assert active_user.last_login > initial_last_login


@pytest.mark.django_db
@patch('requests.get')
def test_google_login_view_invalid_token(mock_get, api_client):
    """Google login view rejects invalid access token"""
    # Mock Google API error response
    mock_response = Mock()
    mock_response.status_code = 401
    mock_get.return_value = mock_response
    
    url = '/api/users/google-login/'
    data = {
        'access_token': 'invalid_token'
    }
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'error' in response.data
    assert 'Invalid' in response.data['error'] or 'expired' in response.data['error'].lower()


@pytest.mark.django_db
@patch('requests.get')
def test_google_login_view_no_email_from_google(mock_get, api_client):
    """Google login view rejects when Google doesn't provide email"""
    # Mock Google API response without email
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'id': '123456789',
        'given_name': 'Test',
        'family_name': 'User',
        # No email field
    }
    mock_get.return_value = mock_response
    
    url = '/api/users/google-login/'
    data = {
        'access_token': 'valid_google_token'
    }
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'error' in response.data
    assert 'email' in response.data['error'].lower()


@pytest.mark.django_db
def test_google_login_view_missing_access_token(api_client):
    """Google login view requires access_token"""
    url = '/api/users/google-login/'
    data = {}
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'error' in response.data
    assert 'access_token' in response.data['error']


@pytest.mark.django_db
@patch('requests.get')
def test_google_login_view_google_api_error(mock_get, api_client):
    """Google login view handles Google API errors"""
    # Mock Google API exception
    mock_get.side_effect = Exception('Network error')
    
    url = '/api/users/google-login/'
    data = {
        'access_token': 'valid_google_token'
    }
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert 'error' in response.data


@pytest.mark.django_db
@patch('requests.get')
def test_google_login_view_updates_existing_social_account(mock_get, api_client, active_user):
    """Google login view updates existing social account"""
    # Create existing social account
    social_account = SocialAccount.objects.create(
        user=active_user,
        provider='google',
        uid='old_uid',
        extra_data={}
    )
    
    # Mock Google API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'id': 'new_uid',
        'email': active_user.email,
        'given_name': 'Test',
        'family_name': 'User',
        'verified_email': True
    }
    mock_get.return_value = mock_response
    
    url = '/api/users/google-login/'
    data = {
        'access_token': 'valid_google_token'
    }
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_200_OK
    
    # Verify social account was updated
    social_account.refresh_from_db()
    assert social_account.uid == 'new_uid'
    assert 'given_name' in social_account.extra_data


@pytest.mark.django_db
@patch('requests.get')
def test_google_login_view_email_normalization(mock_get, api_client):
    """Google login view normalizes email to lowercase"""
    # Mock Google API response with uppercase email
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'id': '123456789',
        'email': 'TEST@GMAIL.COM',
        'given_name': 'Test',
        'family_name': 'User',
        'verified_email': True
    }
    mock_get.return_value = mock_response
    
    url = '/api/users/google-login/'
    data = {
        'access_token': 'valid_google_token'
    }
    
    response = api_client.post(url, data, format='json')
    
    assert response.status_code == status.HTTP_200_OK
    assert response.data['user']['email'] == 'test@gmail.com'
    
    # Verify user was created with lowercase email
    user = User.objects.get(email='test@gmail.com')
    assert user is not None

