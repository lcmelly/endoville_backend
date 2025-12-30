"""Tests for Login Serializers"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from users.serializers import LoginSerializer
from users.models import OTP

User = get_user_model()


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


@pytest.fixture
def expired_otp(db, active_user):
    """Create an expired OTP"""
    otp = OTP.create_otp(email=active_user.email)
    otp.expires_at = timezone.now() - timedelta(minutes=1)
    otp.save()
    return otp


@pytest.fixture
def used_otp(db, active_user):
    """Create a used OTP"""
    otp = OTP.create_otp(email=active_user.email)
    otp.is_used = True
    otp.save()
    return otp


# LoginSerializer Tests
@pytest.mark.django_db
def test_login_serializer_valid_data(active_user, valid_otp):
    """LoginSerializer validates correct credentials and OTP"""
    data = {
        'email': 'test@example.com',
        'password': 'testpass123',
        'otp': valid_otp.otp
    }
    serializer = LoginSerializer(data=data)
    
    assert serializer.is_valid()
    assert '_user' in serializer.validated_data
    assert '_otp_instance' in serializer.validated_data
    assert serializer.validated_data['_user'] == active_user
    assert serializer.validated_data['_otp_instance'] == valid_otp


@pytest.mark.django_db
def test_login_serializer_email_lowercase(active_user, valid_otp):
    """LoginSerializer converts email to lowercase"""
    data = {
        'email': 'TEST@EXAMPLE.COM',
        'password': 'testpass123',
        'otp': valid_otp.otp
    }
    serializer = LoginSerializer(data=data)
    
    assert serializer.is_valid()
    assert serializer.validated_data['_user'].email == 'test@example.com'


@pytest.mark.django_db
def test_login_serializer_email_strips_whitespace(active_user, valid_otp):
    """LoginSerializer strips whitespace from email"""
    data = {
        'email': '  test@example.com  ',
        'password': 'testpass123',
        'otp': valid_otp.otp
    }
    serializer = LoginSerializer(data=data)
    
    assert serializer.is_valid()
    assert serializer.validated_data['_user'].email == 'test@example.com'


@pytest.mark.django_db
def test_login_serializer_user_not_found(valid_otp):
    """LoginSerializer rejects non-existent user"""
    data = {
        'email': 'nonexistent@example.com',
        'password': 'testpass123',
        'otp': valid_otp.otp
    }
    serializer = LoginSerializer(data=data)
    
    assert not serializer.is_valid()
    assert 'email' in serializer.errors
    assert 'Invalid email or password' in str(serializer.errors['email'])


@pytest.mark.django_db
def test_login_serializer_inactive_user(inactive_user):
    """LoginSerializer rejects inactive user"""
    otp = OTP.create_otp(email=inactive_user.email)
    data = {
        'email': 'inactive@example.com',
        'password': 'testpass123',
        'otp': otp.otp
    }
    serializer = LoginSerializer(data=data)
    
    assert not serializer.is_valid()
    assert 'email' in serializer.errors
    assert 'Account is not activated' in str(serializer.errors['email'])


@pytest.mark.django_db
def test_login_serializer_wrong_password(active_user, valid_otp):
    """LoginSerializer rejects wrong password"""
    data = {
        'email': 'test@example.com',
        'password': 'wrongpassword',
        'otp': valid_otp.otp
    }
    serializer = LoginSerializer(data=data)
    
    assert not serializer.is_valid()
    assert 'password' in serializer.errors
    assert 'Invalid email or password' in str(serializer.errors['password'])


@pytest.mark.django_db
def test_login_serializer_no_otp_found(active_user):
    """LoginSerializer rejects when no OTP exists"""
    data = {
        'email': 'test@example.com',
        'password': 'testpass123',
        'otp': '123456'
    }
    serializer = LoginSerializer(data=data)
    
    assert not serializer.is_valid()
    assert 'otp' in serializer.errors
    assert 'No valid OTP found' in str(serializer.errors['otp'])


@pytest.mark.django_db
def test_login_serializer_invalid_otp_code(active_user, valid_otp):
    """LoginSerializer rejects invalid OTP code"""
    data = {
        'email': 'test@example.com',
        'password': 'testpass123',
        'otp': '000000'  # Wrong OTP
    }
    serializer = LoginSerializer(data=data)
    
    assert not serializer.is_valid()
    assert 'otp' in serializer.errors


@pytest.mark.django_db
def test_login_serializer_expired_otp(active_user, expired_otp):
    """LoginSerializer rejects expired OTP"""
    data = {
        'email': 'test@example.com',
        'password': 'testpass123',
        'otp': expired_otp.otp
    }
    serializer = LoginSerializer(data=data)
    
    assert not serializer.is_valid()
    assert 'otp' in serializer.errors
    assert 'expired' in str(serializer.errors['otp']).lower()


@pytest.mark.django_db
def test_login_serializer_used_otp(active_user, used_otp):
    """LoginSerializer rejects already used OTP"""
    data = {
        'email': 'test@example.com',
        'password': 'testpass123',
        'otp': used_otp.otp
    }
    serializer = LoginSerializer(data=data)
    
    assert not serializer.is_valid()
    assert 'otp' in serializer.errors
    assert 'No valid OTP found' in str(serializer.errors['otp'])


@pytest.mark.django_db
def test_login_serializer_otp_max_attempts(active_user):
    """LoginSerializer rejects OTP after max attempts"""
    otp = OTP.create_otp(email=active_user.email)
    otp.attempt_count = 3
    otp.save()
    
    data = {
        'email': 'test@example.com',
        'password': 'testpass123',
        'otp': otp.otp
    }
    serializer = LoginSerializer(data=data)
    
    assert not serializer.is_valid()
    assert 'otp' in serializer.errors


@pytest.mark.django_db
def test_login_serializer_missing_email(valid_otp):
    """LoginSerializer requires email"""
    data = {
        'password': 'testpass123',
        'otp': valid_otp.otp
    }
    serializer = LoginSerializer(data=data)
    
    assert not serializer.is_valid()
    assert 'email' in serializer.errors


@pytest.mark.django_db
def test_login_serializer_missing_password(active_user, valid_otp):
    """LoginSerializer requires password"""
    data = {
        'email': 'test@example.com',
        'otp': valid_otp.otp
    }
    serializer = LoginSerializer(data=data)
    
    assert not serializer.is_valid()
    assert 'password' in serializer.errors


@pytest.mark.django_db
def test_login_serializer_missing_otp(active_user):
    """LoginSerializer requires OTP"""
    data = {
        'email': 'test@example.com',
        'password': 'testpass123'
    }
    serializer = LoginSerializer(data=data)
    
    assert not serializer.is_valid()
    assert 'otp' in serializer.errors


@pytest.mark.django_db
def test_login_serializer_invalid_email_format(valid_otp):
    """LoginSerializer validates email format"""
    data = {
        'email': 'not-an-email',
        'password': 'testpass123',
        'otp': valid_otp.otp
    }
    serializer = LoginSerializer(data=data)
    
    assert not serializer.is_valid()
    assert 'email' in serializer.errors


@pytest.mark.django_db
def test_login_serializer_otp_too_long(active_user, valid_otp):
    """LoginSerializer validates OTP length"""
    data = {
        'email': 'test@example.com',
        'password': 'testpass123',
        'otp': '1234567'  # Too long
    }
    serializer = LoginSerializer(data=data)
    
    assert not serializer.is_valid()
    assert 'otp' in serializer.errors


@pytest.mark.django_db
def test_login_serializer_empty_email(valid_otp):
    """LoginSerializer rejects empty email"""
    data = {
        'email': '',
        'password': 'testpass123',
        'otp': valid_otp.otp
    }
    serializer = LoginSerializer(data=data)
    
    assert not serializer.is_valid()
    assert 'email' in serializer.errors


@pytest.mark.django_db
def test_login_serializer_password_write_only(active_user, valid_otp):
    """LoginSerializer password field is write-only"""
    data = {
        'email': 'test@example.com',
        'password': 'testpass123',
        'otp': valid_otp.otp
    }
    serializer = LoginSerializer(data=data)
    serializer.is_valid()
    
    # Password should not be in serialized data
    assert 'password' not in serializer.data

