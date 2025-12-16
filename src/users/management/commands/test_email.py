"""
Django management command to test ZeptoMail email

Run: python manage.py test_email your@email.com
"""

from django.core.management.base import BaseCommand
from users.utils import send_otp_email
from users.models import OTP


class Command(BaseCommand):
    help = 'Test ZeptoMail email functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            'email',
            type=str,
            help='Email address to send test OTP'
        )
        parser.add_argument(
            '--name',
            type=str,
            default='Test User',
            help='Name for personalized email'
        )

    def handle(self, *args, **options):
        email = options['email']
        name = options['name']

        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("Testing ZeptoMail Email"))
        self.stdout.write("=" * 60)
        self.stdout.write("")

        # Create OTP
        self.stdout.write("Creating OTP...")
        try:
            otp = OTP.create_otp(email=email)
            self.stdout.write(self.style.SUCCESS(f"✓ OTP Created: {otp.otp}"))
            self.stdout.write(f"  Expires at: {otp.expires_at}")
            self.stdout.write("")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Failed to create OTP: {e}"))
            return

        # Send email
        self.stdout.write(f"Sending OTP to {email}...")
        try:
            success = send_otp_email(email, otp.otp, name)

            if success:
                self.stdout.write(self.style.SUCCESS(f"✓ Email sent successfully!"))
                self.stdout.write(f"  Recipient: {email}")
                self.stdout.write(f"  OTP Code: {otp.otp}")
                self.stdout.write("")
                self.stdout.write(self.style.WARNING("Check your inbox!"))
            else:
                self.stdout.write(self.style.ERROR("✗ Failed to send email"))
                self.stdout.write("")
                self.stdout.write("Check your settings:")
                self.stdout.write("  - ZOHO_ZEPTOMAIL_API_KEY_TOKEN")
                self.stdout.write("  - DEFAULT_FROM_EMAIL")
                self.stdout.write("  - ZOHO_ZEPTOMAIL_HOSTED_REGION")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error: {e}"))
            self.stdout.write("")
            self.stdout.write("Common issues:")
            self.stdout.write("1. Check ZOHO_ZEPTOMAIL_API_KEY_TOKEN in .env")
            self.stdout.write("2. Verify DEFAULT_FROM_EMAIL domain in ZeptoMail")
            self.stdout.write("3. Ensure django-zoho-zeptomail is installed")

        self.stdout.write("")
        self.stdout.write("=" * 60)