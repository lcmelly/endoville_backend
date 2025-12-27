# users/utils.py
"""
Utility functions for user operations
"""

import json
import requests
from django.conf import settings


def send_template_email(to_email, template_key, merge_data, to_name=None, action=None):
    """
    Send email using ZeptoMail template API.

    WHAT THIS DOES:
    - Sends email using ZeptoMail template endpoint
    - Accepts dynamic merge_info variables
    - Uses direct API call (not Django email backend)

    Args:
        to_email (str): Recipient email address
        template_key (str): ZeptoMail template key
        merge_data (dict): Template merge variables as key-value pairs
        to_name (str): Recipient name (optional)
        action (str): Action to be taken by the user (optional)

    Returns:
        bool: True if sent successfully, False otherwise

    Example:
        send_template_email(
            to_email='user@example.com',
            template_key='2d6f.123456.k1.abc123',
            merge_data={
                'name': 'John Doe',
                'OTP': '123456',
                'link': 'https://example.com'
            },
            to_name='John Doe'
        )
    """
    url = "https://api.zeptomail.com/v1.1/email/template"

    payload = {
        "mail_template_key": template_key,
        "from": {
            "address": settings.DEFAULT_FROM_EMAIL,
            "name": getattr(settings, 'DEFAULT_FROM_NAME', 'Endoville Health')
        },
        "to": [{
            "email_address": {
                "address": to_email,
                "name": to_name or to_email
            }
        }],
        "merge_info": merge_data
    }

    headers = {
        'accept': "application/json",
        'content-type': "application/json",
        'authorization': f"{settings.ZOHO_ZEPTOMAIL_API_KEY_TOKEN}",
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to send template email: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return False


def send_otp_email(email, otp_code, name=None, template_key=None, action=None):
    """
    Send OTP email using template or HTML fallback.

    WHAT THIS DOES:
    - If template_key provided: uses that template via API
    - If template_key not provided but ZEPTOMAIL_OTP_TEMPLATE_KEY set: uses default
    - Otherwise: uses HTML email via Django backend

    Args:
        email (str): Recipient email address
        otp_code (str): 6-digit OTP code
        name (str): Recipient name (optional)
        template_key (str): ZeptoMail template key (optional)

    Returns:
        bool: True if sent successfully, False otherwise

    Examples:
        # Use specific template
        send_otp_email('user@example.com', '123456', 'John',
                       template_key='2d6f.123.k1.abc')

        # Use default template from settings
        send_otp_email('user@example.com', '123456', 'John')

        # Force HTML email (no template)
        send_otp_email('user@example.com', '123456', 'John', template_key=False)
    """
    recipient_name = name if name else "User"

    # Determine which template to use
    use_template_key = None

    if template_key:
        # Use provided template key
        use_template_key = template_key
    elif template_key is None and hasattr(settings,
                                          'ZEPTOMAIL_OTP_TEMPLATE_KEY') and settings.ZEPTOMAIL_OTP_TEMPLATE_KEY:
        # Use default template from settings
        use_template_key = settings.ZEPTOMAIL_OTP_TEMPLATE_KEY

    # Send using template or HTML
    if use_template_key:
        # Use ZeptoMail template API
        return send_template_email(
            to_email=email,
            template_key=use_template_key,
            merge_data={
                'name': recipient_name,
                'OTP': otp_code,
                'product_name': 'Endoville Health',
                'action': action,
                'team': 'Endoville Health Team'
            },
            to_name=recipient_name
        )
    else:
        # Use HTML email fallback via Django backend
        return _send_otp_html_email(email, otp_code, recipient_name)


def _send_otp_html_email(email, otp_code, name):
    """
    Send OTP using HTML email via Django backend (no template).

    Internal function - use send_otp_email() instead.
    """
    html_message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Your OTP Code</h2>
        <p>Hello {name},</p>
        <p>Your One-Time Password is:</p>
        <div style="background-color: #f4f4f4; padding: 15px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 5px;">
            {otp_code}
        </div>
        <p>This code will expire in 5 minutes.</p>
        <p>If you didn't request this code, please ignore this email.</p>
        <br>
        <p>Best regards,<br>Endoville Health</p>
    </div>
    """

    message = f"""
    Hello {name},

    Your One-Time Password is: {otp_code}

    This code will expire in 5 minutes.

    If you didn't request this code, please ignore this email.

    Best regards,
    Endoville Health
    """

    try:
        from django.core.mail import send_mail
        send_mail(
            subject='Your OTP Code',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Failed to send OTP HTML email: {e}")
        return False


def send_otp_sms(phone, otp_code):
    """
    Send OTP via SMS.

    TODO: Integrate SMS provider (Africa's Talking, Twilio, etc.)

    Args:
        phone (str): Recipient phone number
        otp_code (str): 6-digit OTP code

    Returns:
        bool: True if sent successfully, False otherwise
    """
    # Placeholder - integrate your SMS provider
    print(f"SMS to {phone}: Your OTP code is {otp_code}")
    return True