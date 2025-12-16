# users/tests/test_utils.py
"""Tests for utility functions"""

import pytest
import requests
from unittest.mock import patch, Mock
from users.utils import send_template_email, send_otp_email, send_otp_sms


def pytest_addoption(parser):
    """Add custom pytest command line option"""
    parser.addoption(
        "--run-real-email",
        action="store_true",
        default=False,
        help="Run real email tests (sends actual emails)"
    )


# send_template_email Tests
@pytest.mark.django_db
@patch('users.utils.requests.post')
def test_send_template_email_success(mock_post):
    """send_template_email returns True on success"""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    result = send_template_email(
        to_email='test@example.com',
        template_key='test-key',
        merge_data={'name': 'John', 'OTP': '123456'}
    )

    assert result is True
    assert mock_post.called


@pytest.mark.django_db
@patch('users.utils.requests.post')
def test_send_template_email_with_to_name(mock_post):
    """send_template_email includes to_name in payload"""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    result = send_template_email(
        to_email='test@example.com',
        template_key='test-key',
        merge_data={'OTP': '123456'},
        to_name='John Doe'
    )

    assert result is True
    call_args = mock_post.call_args
    payload = call_args[1]['json']
    assert payload['to'][0]['email_address']['name'] == 'John Doe'


@pytest.mark.django_db
@patch('users.utils.requests.post')
def test_send_template_email_payload_structure(mock_post):
    """send_template_email sends correct payload structure"""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    send_template_email(
        to_email='test@example.com',
        template_key='template-123',
        merge_data={'name': 'John', 'OTP': '456789'}
    )

    call_args = mock_post.call_args
    payload = call_args[1]['json']

    assert payload['mail_template_key'] == 'template-123'
    assert payload['to'][0]['email_address']['address'] == 'test@example.com'
    assert payload['merge_info']['name'] == 'John'
    assert payload['merge_info']['OTP'] == '456789'


@pytest.mark.django_db
@patch('users.utils.requests.post')
def test_send_template_email_headers(mock_post):
    """send_template_email includes correct headers"""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    send_template_email(
        to_email='test@example.com',
        template_key='test-key',
        merge_data={'OTP': '123456'}
    )

    call_args = mock_post.call_args
    headers = call_args[1]['headers']

    assert headers['accept'] == 'application/json'
    assert headers['content-type'] == 'application/json'
    assert 'Zoho-enczapikey' in headers['authorization']


@pytest.mark.django_db
@patch('users.utils.requests.post')
def test_send_template_email_failure(mock_post):
    """send_template_email returns False on failure"""
    mock_post.side_effect = requests.exceptions.RequestException('API Error')

    result = send_template_email(
        to_email='test@example.com',
        template_key='test-key',
        merge_data={'OTP': '123456'}
    )

    assert result is False


@pytest.mark.django_db
@patch('users.utils.requests.post')
def test_send_template_email_http_error(mock_post):
    """send_template_email handles HTTP errors"""
    import requests
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError('400 Bad Request')
    mock_response.text = 'Invalid template key'
    mock_post.return_value = mock_response

    result = send_template_email(
        to_email='test@example.com',
        template_key='invalid-key',
        merge_data={'OTP': '123456'}
    )

    assert result is False


# send_otp_email Tests
@pytest.mark.django_db
@patch('users.utils.send_template_email')
@patch('users.utils.settings')
def test_send_otp_email_calls_template_function(mock_settings, mock_send):
    """send_otp_email calls send_template_email"""
    mock_settings.ZEPTOMAIL_OTP_TEMPLATE_KEY = 'test-template-key'
    mock_send.return_value = True

    result = send_otp_email('test@example.com', '123456', 'John')

    assert result is True
    assert mock_send.called


@pytest.mark.django_db
@patch('users.utils.send_template_email')
@patch('users.utils.settings')
def test_send_otp_email_passes_correct_data(mock_settings, mock_send):
    """send_otp_email passes correct parameters"""
    mock_settings.ZEPTOMAIL_OTP_TEMPLATE_KEY = 'test-template-key'
    mock_send.return_value = True

    send_otp_email('test@example.com', '123456', 'John')

    call_args = mock_send.call_args
    assert call_args[1]['to_email'] == 'test@example.com'
    assert call_args[1]['merge_data']['OTP'] == '123456'
    assert call_args[1]['merge_data']['name'] == 'John'
    assert call_args[1]['to_name'] == 'John'


@pytest.mark.django_db
@patch('users.utils.send_template_email')
@patch('users.utils.settings')
def test_send_otp_email_uses_settings_template_key(mock_settings, mock_send):
    """send_otp_email uses ZEPTOMAIL_OTP_TEMPLATE_KEY from settings"""
    mock_settings.ZEPTOMAIL_OTP_TEMPLATE_KEY = 'my-otp-template'
    mock_send.return_value = True

    send_otp_email('test@example.com', '999999', 'Jane')

    call_args = mock_send.call_args
    assert call_args[1]['template_key'] == 'my-otp-template'


@pytest.mark.django_db
@patch('users.utils.send_template_email')
@patch('users.utils.settings')
def test_send_otp_email_returns_result(mock_settings, mock_send):
    """send_otp_email returns send_template_email result"""
    mock_settings.ZEPTOMAIL_OTP_TEMPLATE_KEY = 'test-template-key'
    mock_send.return_value = False

    result = send_otp_email('test@example.com', '123456', 'John')

    assert result is False


# send_otp_sms Tests
def test_send_otp_sms_placeholder():
    """send_otp_sms returns True (placeholder)"""
    result = send_otp_sms('+1234567890', '123456')
    assert result is True


def test_send_otp_sms_with_different_phone():
    """send_otp_sms works with different phone formats"""
    result = send_otp_sms('+254712345678', '654321')
    assert result is True


# Integration-style Tests
@pytest.mark.django_db
@patch('users.utils.requests.post')
@patch('users.utils.settings')
def test_full_otp_flow(mock_settings, mock_post):
    """Full OTP email sending flow works"""
    mock_settings.ZEPTOMAIL_OTP_TEMPLATE_KEY = 'test-template'
    mock_settings.DEFAULT_FROM_EMAIL = 'noreply@endovillehealth.com'
    mock_settings.ZOHO_ZEPTOMAIL_API_KEY_TOKEN = 'test-key'

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    # Send OTP email
    result = send_otp_email('user@example.com', '777888', 'Test User')

    # Verify success
    assert result is True

    # Verify API was called
    assert mock_post.called

    # Verify payload structure
    payload = mock_post.call_args[1]['json']
    assert payload['to'][0]['email_address']['address'] == 'user@example.com'
    assert payload['merge_info']['OTP'] == '777888'
    assert payload['merge_info']['name'] == 'Test User'


@pytest.mark.django_db
@patch('users.utils.requests.post')
def test_template_email_with_multiple_merge_fields(mock_post):
    """send_template_email handles multiple merge fields"""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    result = send_template_email(
        to_email='user@example.com',
        template_key='welcome-template',
        merge_data={
            'name': 'John Doe',
            'OTP': '123456',
            'link': 'https://example.com',
            'product_name': 'Endoville Health',
            'team': 'Support Team'
        },
        to_name='John Doe'
    )

    assert result is True
    payload = mock_post.call_args[1]['json']
    assert len(payload['merge_info']) == 5
    assert payload['merge_info']['link'] == 'https://example.com'


# Real Email Test (No Mocking)
@pytest.mark.django_db
def test_send_real_otp_email(request):
    """
    REAL EMAIL TEST - Sends actual email to cheruiyotfabian@gmail.com

    This test:
    - Makes real API call to ZeptoMail
    - Sends actual email
    - Requires valid ZeptoMail credentials in .env

    Run with: pytest users/tests/test_utils.py::test_send_real_otp_email --run-real-email

    Skip by default to avoid:
    - Hitting API rate limits
    - Sending spam emails during normal test runs
    - Using API quota
    """
    if not request.config.getoption("--run-real-email"):
        pytest.skip("Skipped - use --run-real-email flag to run real email test")

    result = send_otp_email(
        email='cheruiyotfabian@gmail.com',
        otp_code='123456',
        name='Fabian'
    )

    assert result is True
    print("\n✓ Real email sent to cheruiyotfabian@gmail.com")
    print("  Check your inbox for OTP: 123456")