"""
Pytest module for testing user-related functionalities.
- Uses pytest fixtures for setup and teardown.
- Tests user creation, authentication, and profile updates.
- Covers edge cases and error handling.
- pytest-django is required for Django integration.
- use pytest.raises for exception testing.
"""

import pytest
import datetime
from django.contrib.auth import get_user_model
from users.models import OTP
from django.core.exceptions import ValidationError
from datetime import date, timedelta
from django.utils import timezone

# Get the custom user model
User = get_user_model()

############################ | FIXTURES | #################################
@pytest.fixture
def email_user(db):
    """Fixture to create a user with email."""
    user = User.objects.create_user(
        email = 'testuser@example.com',
        password = 'securepassword123',
        first_name = 'Test',
        last_name = 'User',
        gender = 'M'
    )

    return user


@pytest.fixture
def phone_user(db):
    """Fixture to create a user with phone number."""
    user = User.objects.create_user(
        phone = '+12345678901',
        password = 'securepassword123',
        first_name = 'Phone',
        last_name = 'User',
        gender = 'N'
    )

    return user

@pytest.fixture
def email_otp(db):
    """Create OTP with email"""
    return OTP.create_otp(email='test@example.com')


@pytest.fixture
def phone_otp(db):
    """Create OTP with phone"""
    return OTP.create_otp(phone='+1234567890')


############################ | USER MODEL TESTS | #################################
@pytest.mark.django_db
def test_create_user_with_email_only(email_user):
    """Test creating a user with email and password."""
    # Create user
    user = User.objects.create_user(email='email@example.com', password='securepass123')

    # Assertions
    assert user.email == 'email@example.com'
    assert user.phone is None
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False

    # Check password is hashed
    assert user.password != 'securepass123'  # Password should be hashed
    assert user.check_password('securepass123') is True

    # Verify Identifier
    assert user.identifier == 'email@example.com'

@pytest.mark.django_db
def test_create_user_with_phone_only(phone_user):
    """Tests creating user with phone and password """
    # Create use
    user = User.objects.create_user(phone='+12345678902', password='securepass123')

    # Assertions
    assert user.phone == '+12345678902'
    assert user.email is None
    assert user.is_active is True

    # Verify password hashing
    assert user.check_password('securepass123') is True

    # Verify identifier property returns phone
    assert user.identifier == '+12345678902'


@pytest.mark.django_db
def test_create_user_with_both_email_phone():
    """Tests creating user with both phone and password"""
    user = User.objects.create_user(
        email='both@example.com',
        phone='+1555555555',
        password='securepass123',
        first_name='Both',
        last_name='User'
    )

    # Assert both fields are set
    assert user.email == 'both@example.com'
    assert user.phone == '+1555555555'
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False

    # Verify identifier property prioritizes email
    assert user.identifier == 'both@example.com'

@pytest.mark.django_db
def test_create_user_without_identifiers_fails():
    """Tests creating user without email/phone"""
    with pytest.raises(ValueError) as exc_info:
        User.objects.create_user(
            email=None,
            phone=None,
            password='testpass123'
        )

    #Verify error message
    assert 'The Email or Phone number must be set' in str(exc_info.value)

@pytest.mark.django_db
def test_model_validation_without_identifiers():
    """Test that model.clean() raises ValidationError without identifiers."""
    # Verify clean raises validationError
    with pytest.raises(ValidationError) as exc_info:
        # Create instance without verifiers
        user = User.objects.create(password='testpass123')
        user.clean()

    assert 'Either email or phone number must be provided' in str(exc_info.value)

@pytest.mark.django_db
def test_email_must_be_unique(email_user):
    """Test that duplicate emails are rejected"""
    with pytest.raises(ValidationError):
        User.objects.create_user(
            email='testuser@example.com',  # Same as fixture
            password='anotherpass123'
        )


@pytest.mark.django_db
def test_phone_must_be_unique(phone_user):
    """"Test that duplicate phone numbers are rejected"""
    with pytest.raises(ValidationError):
        User.objects.create_user(
            phone='+12345678901',  # Same as fixture
            password='anotherpass123'
        )


@pytest.mark.django_db
def test_invalid_phone_format_raises_error():
    """Test that invalid phone formats are rejected"""
    with pytest.raises(ValidationError):
        user = User.objects.create_user(
            phone='invalid',  # Invalid format
            password='testpass123'
        )

@pytest.mark.django_db
def test_create_superuser():
    """Test creating a superuser with admin permissions."""
    # Create superuser
    admin = User.objects.create_superuser(
        email='admin@example.com',
        phone='+1111111111',
        password='adminpass123'
    )

    # Assert superuser flags are set
    assert admin.is_staff is True
    assert admin.is_superuser is True
    assert admin.is_active is True

    # Verify password is hashed
    assert admin.check_password('adminpass123') is True

@pytest.mark.django_db
def test_password_change(email_user):
    """Test that password can be changed and is re-hashed."""
    # Change password
    email_user.set_password('newpass123')
    email_user.save()

    # Old password should not work
    assert email_user.check_password('testpass123') is False

    # New password should work
    assert email_user.check_password('newpass123') is True


@pytest.mark.django_db
def test_get_full_name_with_names(email_user):
    """Test get_full_name returns first + last name"""
    # Test with names
    assert email_user.get_full_name() == 'Test User'


@pytest.mark.django_db
def test_get_full_name_without_names():
    """Test get_full_name falls back to email/phone"""
    # Create user without names
    user = User.objects.create_user(
        email='noname@example.com',
        password='pass123'
    )

    # Should return email as fallback
    assert user.get_full_name() == 'noname@example.com'


@pytest.mark.django_db
def test_get_short_name(email_user):
    """Test get_short_name returns first name or identifier."""
    # Test with first name
    assert email_user.get_short_name() == 'Test'

    # Test without first name
    email_user.first_name = ''
    assert email_user.get_short_name() == 'testuser@example.com'


@pytest.mark.django_db
def test_str_method(email_user, phone_user):
    """Test __str__ returns email or phone"""
    # User with email shows email
    assert str(email_user) == 'Test User (testuser@example.com)'

    # User with phone shows phone
    assert str(phone_user) == 'Phone User (+12345678901)'


@pytest.mark.django_db
def test_identifier_property(email_user, phone_user):
    """Test identifier property returns email or phone"""
    # Email user shows email
    assert email_user.identifier == 'testuser@example.com'

    # Phone user shows phone
    assert phone_user.identifier == '+12345678901'


@pytest.mark.django_db
def test_get_age_calculates_correctly():
    """Test get_age() calculates age from date_of_birth"""
    # Create a user born 25 years ago
    birth_date = date.today() - timedelta(days=365 * 25 + 6)  # ~25 years

    user = User.objects.create_user(
        email='aged@example.com',
        password='pass123',
        date_of_birth=birth_date
    )

    # Age should be approximately 25
    assert user.get_age() == 25


@pytest.mark.django_db
def test_get_age_returns_none_without_dob(email_user):
    """Test get_age() returns None when date_of_birth is not set"""
    # User without DOB returns None
    assert email_user.get_age() is None

@pytest.mark.django_db
def test_get_age_on_birthday(monkeypatch):
    """Age should increment on the user's birthday."""
    fixed_today = date(2025, 6, 15)
    fixed_now = timezone.make_aware(
        datetime.datetime(2025, 6, 15, 12, 0, 0),
        timezone.get_current_timezone(),
    )
    monkeypatch.setattr(timezone, "now", lambda: fixed_now)

    user = User.objects.create_user(
        email="bday@example.com",
        password="pass123",
        date_of_birth=date(2000, 6, 15),
    )

    assert user.get_age() == 25


@pytest.mark.django_db
def test_get_age_before_birthday(monkeypatch):
    """Age should not increment yet if birthday hasn't occurred this year."""
    fixed_today = date(2025, 6, 14)
    fixed_now = timezone.make_aware(
        datetime.datetime(2025, 6, 14, 12, 0, 0),
        timezone.get_current_timezone(),
    )
    monkeypatch.setattr(timezone, "now", lambda: fixed_now)

    user = User.objects.create_user(
        email="beforebday@example.com",
        password="pass123",
        date_of_birth=date(2000, 6, 15),
    )

    assert user.get_age() == 24


@pytest.mark.django_db
def test_get_age_leap_day_non_leap_year(monkeypatch):
    """
    User born on Feb 29:
    Ensure age calculation behaves consistently on non-leap years.
    (With the current algorithm, Mar 1 counts as "after birthday".)
    """
    fixed_today = date(2025, 3, 1)  # 2025 is not a leap year
    fixed_now = timezone.make_aware(
        datetime.datetime(2025, 3, 1, 12, 0, 0),
        timezone.get_current_timezone(),
    )
    monkeypatch.setattr(timezone, "now", lambda: fixed_now)

    user = User.objects.create_user(
        email="leap@example.com",
        password="pass123",
        date_of_birth=date(2004, 2, 29),
    )

    assert user.get_age() == 21


############################ | OTP MODEL TESTS | #################################
# Creation Tests
@pytest.mark.django_db
def test_create_otp_with_email():
    """OTP created with email"""
    otp = OTP.create_otp(email='user@example.com')

    assert otp.email == 'user@example.com'
    assert otp.phone is None
    assert len(otp.otp) == 6
    assert not otp.is_used


@pytest.mark.django_db
def test_create_otp_with_phone():
    """OTP created with phone"""
    otp = OTP.create_otp(phone='+1234567890')

    assert otp.phone == '+1234567890'
    assert otp.email is None
    assert len(otp.otp) == 6


@pytest.mark.django_db
def test_create_otp_requires_identifier():
    """OTP creation requires email or phone"""
    with pytest.raises(ValueError):
        OTP.create_otp()


@pytest.mark.django_db
def test_email_normalized_to_lowercase():
    """Email is lowercased"""
    otp = OTP.create_otp(email='Test@EXAMPLE.COM')
    assert otp.email == 'test@example.com'


@pytest.mark.django_db
def test_create_otp_deletes_old_otp():
    """Creating new OTP deletes old one for same identifier"""
    otp1 = OTP.create_otp(email='test@example.com')
    otp2 = OTP.create_otp(email='test@example.com')

    assert not OTP.objects.filter(id=otp1.id).exists()
    assert OTP.objects.filter(id=otp2.id).exists()


# Code Generation Tests
@pytest.mark.django_db
def test_generate_code_returns_six_digits():
    """Generated code is 6 digits"""
    otp = OTP.create_otp(email='test@example.com')
    code = otp.generate_code()

    assert len(code) == 6
    assert code.isdigit()


# Expiration Tests
@pytest.mark.django_db
def test_otp_expires_after_5_minutes(email_otp):
    """OTP expires after 5 minutes"""
    expected_expiry = email_otp.created_at + timedelta(minutes=5)

    assert abs((email_otp.expires_at - expected_expiry).total_seconds()) < 1


@pytest.mark.django_db
def test_is_expired_returns_false_for_new_otp(email_otp):
    """New OTP is not expired"""
    assert not email_otp.is_expired()


@pytest.mark.django_db
def test_is_expired_returns_true_for_old_otp(email_otp):
    """Old OTP is expired"""
    email_otp.expires_at = timezone.now() - timedelta(minutes=1)
    email_otp.save()

    assert email_otp.is_expired()


# Verification Tests
@pytest.mark.django_db
def test_verify_correct_code(email_otp):
    """Correct code verifies successfully"""
    success, message = email_otp.verify(email_otp.otp)

    assert success is True
    assert message == "OTP verified successfully"
    assert email_otp.is_used is True


@pytest.mark.django_db
def test_verify_incorrect_code(email_otp):
    """Incorrect code fails verification"""
    success, message = email_otp.verify('000000')

    assert success is False
    assert "Invalid OTP" in message
    assert email_otp.attempt_count == 1


@pytest.mark.django_db
def test_verify_increments_attempts(email_otp):
    """Failed verification increments attempts"""
    email_otp.verify('000000')
    assert email_otp.attempt_count == 1

    email_otp.verify('000000')
    assert email_otp.attempt_count == 2


@pytest.mark.django_db
def test_verify_fails_after_3_attempts(email_otp):
    """Verification fails after 3 attempts"""
    email_otp.verify('000000')
    email_otp.verify('000000')
    email_otp.verify('000000')

    success, message = email_otp.verify(email_otp.otp)
    assert success is False


@pytest.mark.django_db
def test_verify_fails_if_already_used(email_otp):
    """Cannot verify already used OTP"""
    email_otp.verify(email_otp.otp)
    success, message = email_otp.verify(email_otp.otp)

    assert success is False


@pytest.mark.django_db
def test_verify_fails_if_expired(email_otp):
    """Cannot verify expired OTP"""
    email_otp.expires_at = timezone.now() - timedelta(minutes=1)
    email_otp.save()

    success, message = email_otp.verify(email_otp.otp)
    assert success is False


# Validity Tests
@pytest.mark.django_db
def test_is_valid_for_new_otp(email_otp):
    """New OTP is valid"""
    assert email_otp.is_valid()


@pytest.mark.django_db
def test_is_valid_false_if_used(email_otp):
    """Used OTP is invalid"""
    email_otp.is_used = True
    email_otp.save()

    assert not email_otp.is_valid()


@pytest.mark.django_db
def test_is_valid_false_if_expired(email_otp):
    """Expired OTP is invalid"""
    email_otp.expires_at = timezone.now() - timedelta(minutes=1)
    email_otp.save()

    assert not email_otp.is_valid()


@pytest.mark.django_db
def test_is_valid_false_if_max_attempts(email_otp):
    """OTP with max attempts is invalid"""
    email_otp.attempt_count = 3
    email_otp.save()

    assert not email_otp.is_valid()


# Cleanup Tests
@pytest.mark.django_db
def test_cleanup_expired_otp_deletes_old():
    """Cleanup deletes expired OTPs"""
    # Create expired OTP
    old_otp = OTP.create_otp(email='old@example.com')
    old_otp.expires_at = timezone.now() - timedelta(minutes=10)
    old_otp.save()

    # Create valid OTP
    new_otp = OTP.create_otp(email='new@example.com')

    count = OTP.cleanup_expired_otp()

    assert count == 1
    assert not OTP.objects.filter(id=old_otp.id).exists()
    assert OTP.objects.filter(id=new_otp.id).exists()


@pytest.mark.django_db
def test_cleanup_expired_otp_keeps_valid():
    """Cleanup keeps valid OTPs"""
    otp1 = OTP.create_otp(email='test1@example.com')
    otp2 = OTP.create_otp(email='test2@example.com')

    count = OTP.cleanup_expired_otp()

    assert count == 0
    assert OTP.objects.count() == 2


# String Representation Tests
@pytest.mark.django_db
def test_str_with_email(email_otp):
    """String shows email identifier"""
    assert 'test@example.com' in str(email_otp)
    assert 'Pending' in str(email_otp)


@pytest.mark.django_db
def test_str_with_phone(phone_otp):
    """String shows phone identifier"""
    assert '+1234567890' in str(phone_otp)


@pytest.mark.django_db
def test_str_shows_verified_status(email_otp):
    """String shows verified status"""
    email_otp.is_used = True
    email_otp.save()

    assert 'Verified' in str(email_otp)