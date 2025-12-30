"""Tests for Serializers"""

import pytest
from django.contrib.auth import get_user_model
from users.serializers import (
    UserSerializer,
    OTPSerializer,
    RequestOTPSerializer,
    VerifyOTPSerializer,
    SignupSerializer,
    LoginSerializer
)
from users.models import OTP

User = get_user_model()


# UserSerializer Tests
@pytest.mark.django_db
def test_user_serializer_fields():
    """UserSerializer has correct fields"""
    user = User.objects.create_user(email='test@example.com', password='test123')
    serializer = UserSerializer(user)

    assert 'id' in serializer.data
    assert 'email' in serializer.data
    assert 'phone' in serializer.data
    assert 'first_name' in serializer.data
    assert 'password' not in serializer.data


@pytest.mark.django_db
def test_user_serializer_read_only_fields():
    """UserSerializer read-only fields cannot be updated"""
    user = User.objects.create_user(email='test@example.com', password='test123')
    data = {'id': 999, 'is_active': False, 'created_at': '2020-01-01'}

    serializer = UserSerializer(user, data=data, partial=True)
    serializer.is_valid()
    serializer.save()

    user.refresh_from_db()
    assert user.id != 999
    assert user.is_active is True


################ OTPSerializer Tests  ################
@pytest.mark.django_db
def test_otp_serializer_fields():
    """OTPSerializer has correct fields"""
    otp = OTP.create_otp(email='test@example.com')
    serializer = OTPSerializer(otp)

    assert 'id' in serializer.data
    assert 'email' in serializer.data
    assert 'otp' in serializer.data
    assert 'is_used' in serializer.data


@pytest.mark.django_db
def test_otp_serializer_read_only_fields():
    """OTPSerializer read-only fields cannot be updated"""
    otp = OTP.create_otp(email='test@example.com')
    data = {'is_used': True, 'attempt_count': 5}

    serializer = OTPSerializer(otp, data=data, partial=True)
    serializer.is_valid()
    serializer.save()

    otp.refresh_from_db()
    assert otp.is_used is False
    assert otp.attempt_count == 0


## RequestOTPSerializer Tests
@pytest.mark.django_db
def test_request_otp_with_email():
    """RequestOTPSerializer accepts email"""
    data = {'email': 'test@example.com'}
    serializer = RequestOTPSerializer(data=data)

    assert serializer.is_valid()
    assert serializer.validated_data['email'] == 'test@example.com'


@pytest.mark.django_db
def test_request_otp_with_phone():
    """RequestOTPSerializer accepts phone"""
    data = {'phone': '+1234567890'}
    serializer = RequestOTPSerializer(data=data)

    assert serializer.is_valid()
    assert serializer.validated_data['phone'] == '+1234567890'


@pytest.mark.django_db
def test_request_otp_requires_identifier():
    """RequestOTPSerializer requires email or phone"""
    data = {}
    serializer = RequestOTPSerializer(data=data)

    assert not serializer.is_valid()
    assert 'error' in serializer.errors


@pytest.mark.django_db
def test_request_otp_strips_whitespace():
    """RequestOTPSerializer strips whitespace"""
    data = {'email': '  test@example.com  '}
    serializer = RequestOTPSerializer(data=data)

    assert serializer.is_valid()
    assert serializer.validated_data['email'] == 'test@example.com'


# # VerifyOTPSerializer Tests
@pytest.mark.django_db
def test_verify_otp_with_valid_code():
    """VerifyOTPSerializer validates correct OTP"""
    otp = OTP.create_otp(email='test@example.com')
    data = {'email': 'test@example.com', 'otp': otp.otp}

    serializer = VerifyOTPSerializer(data=data)

    assert serializer.is_valid()
    assert '_otp_instance' in serializer.validated_data


@pytest.mark.django_db
def test_verify_otp_with_invalid_code():
    """VerifyOTPSerializer rejects incorrect OTP"""
    OTP.create_otp(email='test@example.com')
    data = {'email': 'test@example.com', 'otp': '000000'}

    serializer = VerifyOTPSerializer(data=data)

    assert not serializer.is_valid()
    assert 'otp' in serializer.errors


@pytest.mark.django_db
def test_verify_otp_without_otp_record():
    """VerifyOTPSerializer fails when no OTP found"""
    data = {'email': 'noexist@example.com', 'otp': '123456'}

    serializer = VerifyOTPSerializer(data=data)

    assert not serializer.is_valid()
    assert 'No OTP found' in str(serializer.errors['otp'])


@pytest.mark.django_db
def test_verify_otp_requires_identifier():
    """VerifyOTPSerializer requires email or phone"""
    data = {'otp': '123456'}
    serializer = VerifyOTPSerializer(data=data)

    assert not serializer.is_valid()
    assert 'error' in serializer.errors


@pytest.mark.django_db
def test_verify_otp_email_lowercase():
    """VerifyOTPSerializer converts email to lowercase"""
    otp = OTP.create_otp(email='test@example.com')
    data = {'email': 'TEST@EXAMPLE.COM', 'otp': otp.otp}

    serializer = VerifyOTPSerializer(data=data)

    assert serializer.is_valid()


@pytest.mark.django_db
def test_verify_otp_with_used_otp():
    """VerifyOTPSerializer rejects already used OTP"""
    otp = OTP.create_otp(email='test@example.com')
    otp.is_used = True
    otp.save()

    data = {'email': 'test@example.com', 'otp': otp.otp}
    serializer = VerifyOTPSerializer(data=data)

    assert not serializer.is_valid()
    assert 'No OTP found' in str(serializer.errors['otp'])


## SignupSerializer Tests
@pytest.mark.django_db
def test_signup_with_email_and_password():
    """SignupSerializer creates user with email and password"""
    data = {
        'email': 'test@example.com',
        'password': 'testpass123',
        'first_name': 'John'
    }
    serializer = SignupSerializer(data=data)

    assert serializer.is_valid()
    user = serializer.save()

    assert user.email == 'test@example.com'
    assert user.first_name == 'John'
    assert user.check_password('testpass123')


@pytest.mark.django_db
def test_signup_with_phone_and_password():
    """SignupSerializer creates user with phone and password"""
    data = {
        'phone': '+1234567890',
        'password': 'testpass123'
    }
    serializer = SignupSerializer(data=data)

    assert serializer.is_valid()
    user = serializer.save()

    assert user.phone == '+1234567890'
    assert user.check_password('testpass123')


@pytest.mark.django_db
def test_signup_without_password():
    """SignupSerializer creates user without password (passwordless)"""
    data = {
        'email': 'test@example.com',
        'first_name': 'John'
    }
    serializer = SignupSerializer(data=data)

    assert serializer.is_valid()
    user = serializer.save()

    assert user.email == 'test@example.com'
    assert not user.has_usable_password()


@pytest.mark.django_db
def test_signup_requires_identifier():
    """SignupSerializer requires email or phone"""
    data = {'password': 'testpass123'}
    serializer = SignupSerializer(data=data)

    assert not serializer.is_valid()
    assert 'error' in serializer.errors


@pytest.mark.django_db
def test_signup_password_min_length():
    """SignupSerializer enforces password minimum length"""
    data = {
        'email': 'test@example.com',
        'password': 'short'
    }
    serializer = SignupSerializer(data=data)

    assert not serializer.is_valid()
    assert 'password' in serializer.errors


@pytest.mark.django_db
def test_signup_with_all_fields():
    """SignupSerializer accepts all optional fields"""
    data = {
        'email': 'test@example.com',
        'password': 'testpass123',
        'first_name': 'John',
        'last_name': 'Doe',
        'gender': 'M',
        'date_of_birth': '1990-01-01'
    }
    serializer = SignupSerializer(data=data)

    assert serializer.is_valid()
    user = serializer.save()

    assert user.first_name == 'John'
    assert user.last_name == 'Doe'
    assert user.gender == 'M'
    assert str(user.date_of_birth) == '1990-01-01'


@pytest.mark.django_db
def test_signup_password_not_in_output():
    """SignupSerializer doesn't expose password in serialized data"""
    data = {
        'email': 'test@example.com',
        'password': 'testpass123'
    }
    serializer = SignupSerializer(data=data)
    serializer.is_valid()
    user = serializer.save()

    output_serializer = UserSerializer(user)
    assert 'password' not in output_serializer.data


@pytest.mark.django_db
def test_signup_with_blank_password():
    """SignupSerializer treats blank password as no password"""
    data = {
        'email': 'test@example.com',
        'password': ''
    }
    serializer = SignupSerializer(data=data)

    assert serializer.is_valid()
    user = serializer.save()

    assert not user.has_usable_password()
