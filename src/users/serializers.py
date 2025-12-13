"""
Serializers for User and OTP models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import OTP

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user data"""

    class Meta:
        model = User
        fields = ['id', 'email', 'phone', 'first_name', 'last_name', 'gender', 'date_of_birth', 'is_active', 'created_at']
        read_only_fields = ['id', 'is_active', 'created_at']


class OTPSerializer(serializers.ModelSerializer):
    """Simple serializer for OTP model"""

    class Meta:
        model = OTP
        fields = ['id', 'email', 'phone', 'otp', 'is_used', 'attempt_count', 'created_at', 'expires_at']
        read_only_fields = ['id', 'is_used', 'attempt_count', 'created_at', 'expires_at']

class RequestOTPSerializer(serializers.ModelSerializer):
    """ Serializer for requesting OTP
    WHAT THIS DOES:
    - Accepts email OR phone number from user
    - Validates that at least one identifier is provided
    - Validates email/phone format
    - Does NOT check if account exists (allows both new and existing users to request OTP)
    """
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=17)

    def validate(self, data):
        """Validate at least one identifier provided"""
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()

        if not email and not phone:
            raise serializers.ValidationError({'error': 'Either email or phone is required'})

        if email:
            data['email'] = email
        if phone:
            data['phone'] = phone

        return data


class VerifyOTPSerializer(serializers.Serializer):
    """
    Serializer for verifying OTP only (no user creation).

    WHAT THIS DOES:
    - Accepts identifier (email/phone) and OTP code
    - Verifies OTP is valid, not expired, and within attempt limits
    - Returns success/failure
    """

    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=17)
    otp = serializers.CharField(max_length=6)

    def validate(self, data):
        """Validate OTP is valid"""
        email = data.get('email', '').strip().lower()
        phone = data.get('phone', '').strip()
        otp_code = data.get('otp')

        if not email and not phone:
            raise serializers.ValidationError({'error': 'Either email or phone is required'})

        # Find OTP record
        try:
            if email:
                otp = OTP.objects.get(email=email, is_used=False)
            else:
                otp = OTP.objects.get(phone=phone, is_used=False)
        except OTP.DoesNotExist:
            raise serializers.ValidationError({'otp': 'No OTP found. Request a new one.'})

        # Verify OTP code
        success, message = otp.verify(otp_code)

        if not success:
            raise serializers.ValidationError({'otp': message})

        # Store OTP instance for view to use
        data['_otp_instance'] = otp
        return data


class SignupSerializer(serializers.Serializer):
    """Serializer for user signup
    WHAT THIS DOES:
    - Accepts user details (identifier, password, profile fields)
    - Creates new user account
    - Returns created user
    """
    password = serializers.CharField(write_only=True, min_length=8, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['email', 'phone', 'password', 'first_name', 'last_name', 'gender', 'date_of_birth']
        extra_kwargs = {
            'email': {'required': False},
            'phone': {'required': False}
        }

    def validate(self, data):
        """
        Validate signup data.
        RULES:
        - At least one identifier (email or phone) required
        - Password is optional (for OTP/OAuth signups)
        """
        email = data.get('email')
        phone = data.get('phone')

        if not email and not phone:
            raise serializers.ValidationError({'error': 'Either email or phone is required'})

        return data

    def create(self, validated_data):
        """
        Create user account.

        HANDLES TWO CASES:

        Case 1 - With password:
        password = validated_data.pop('password')
        User.create_user(password=password, ...)

        Case 2 - Without password (OTP/OAuth):
        User.create_user(password=None, ...)
        Django sets unusable password - user can't login with password
        User must use OTP or OAuth to login

        PASSWORD CAN BE SET LATER:
        user.set_password('new_password')
        user.save()
        """
        password = validated_data.pop('password', None)

        if password:
            # Traditional signup with password
            user = User.objects.create_user(password=password, **validated_data)
        else:
            # OTP/OAuth signup without password
            user = User.objects.create_user(password=None, **validated_data)

        return user