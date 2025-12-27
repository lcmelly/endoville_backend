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

    class Meta:
        model = OTP
        fields = ['email', 'phone']

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


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration
    WHAT THIS DOES:
    - Accepts email, first_name, last_name, and password
    - Creates new user account with is_active=False
    - Prevents is_staff from being set to True
    - Sends OTP for account activation
    """
    password = serializers.CharField(write_only=True, min_length=8, required=True)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'password']
        extra_kwargs = {
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True}
        }

    def validate(self, data):
        """
        Validate registration data.
        RULES:
        - Email is required
        - Password is required (min 8 characters)
        - first_name and last_name are required
        - is_staff cannot be set to True (will be enforced in create)
        """
        email = data.get('email', '').strip().lower()
        
        if not email:
            raise serializers.ValidationError({'email': 'Email is required'})
        
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'email': 'A user with this email already exists.'})
        
        data['email'] = email
        return data

    def create(self, validated_data):
        """
        Create user account with is_active=False and send OTP.
        
        SECURITY:
        - is_active is explicitly set to False
        - is_staff is explicitly set to False (prevents privilege escalation)
        - Password is required and hashed
        - OTP is sent via email for activation
        """
        password = validated_data.pop('password')
        
        # Explicitly set is_active=False and is_staff=False
        user = User.objects.create_user(
            email=validated_data['email'],
            password=password,
            first_name=validated_data.get('first_name'),
            last_name=validated_data.get('last_name'),
            is_active=False,  # Account is inactive until OTP verification
            is_staff=False,   # Prevent setting is_staff=True
            phone=None  # Explicitly set to None for email-based registration
        )
        
        # Create and send OTP for account activation
        from .models import OTP
        from .utils import send_otp_email
        
        otp_instance = OTP.create_otp(email=user.email)
        user_name = user.get_full_name() or user.email
        send_otp_email(
            email=user.email,
            otp_code=otp_instance.otp,
            name=user_name,
            action="Activate your account?"
        )
        
        return user


class ActivateAccountSerializer(serializers.Serializer):
    """
    Serializer for activating user account using OTP.
    
    WHAT THIS DOES:
    - Accepts email and OTP code
    - Verifies OTP is valid
    - Activates user account (sets is_active=True)
    """
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=6, required=True)

    def validate(self, data):
        """Validate OTP and find user"""
        email = data.get('email', '').strip().lower()
        otp_code = data.get('otp')

        if not email:
            raise serializers.ValidationError({'email': 'Email is required'})

        # Find user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({'email': 'User with this email does not exist.'})

        # Check if already activated
        if user.is_active:
            raise serializers.ValidationError({'email': 'Account is already activated.'})

        # Find and verify OTP
        try:
            otp = OTP.objects.get(email=email, is_used=False)
        except OTP.DoesNotExist:
            raise serializers.ValidationError({'otp': 'No valid OTP found. Please request a new one.'})

        # Verify OTP code
        success, message = otp.verify(otp_code)

        if not success:
            raise serializers.ValidationError({'otp': message})

        # Store instances for view to use
        data['_user'] = user
        data['_otp_instance'] = otp
        return data


class ResendOTPSerializer(serializers.Serializer):
    """
    Serializer for resending OTP for user account.
    
    WHAT THIS DOES:
    - Accepts email address
    - Validates user exists
    - Creates a new OTP (deletes old one if exists)
    - Sends new OTP via email
    """
    email = serializers.EmailField(required=True)

    def validate(self, data):
        """Validate user exists and is not activated"""
        email = data.get('email', '').strip().lower()

        if not email:
            raise serializers.ValidationError({'email': 'Email is required'})

        # Find user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({'email': 'User with this email does not exist.'})


        # Store user instance for view to use
        data['_user'] = user
        return data


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login with email, password, and OTP.
    
    WHAT THIS DOES:
    - Accepts email, password, and OTP code
    - Validates email and password credentials
    - Validates OTP code
    - Returns JWT tokens on successful validation
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    otp = serializers.CharField(max_length=6, required=True)

    def validate(self, data):
        """Validate credentials and OTP"""
        email = data.get('email', '').strip().lower()
        password = data.get('password')
        otp_code = data.get('otp')

        if not email:
            raise serializers.ValidationError({'email': 'Email is required'})

        # Find user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({'email': 'Invalid email or password.'})

        # Check if account is active
        if not user.is_active:
            raise serializers.ValidationError({'email': 'Account is not activated. Please activate your account first.'})

        # Validate password
        if not user.check_password(password):
            raise serializers.ValidationError({'password': 'Invalid email or password.'})

        # Find and verify OTP
        try:
            otp = OTP.objects.get(email=email, is_used=False)
        except OTP.DoesNotExist:
            raise serializers.ValidationError({'otp': 'No valid OTP found. Please request a new one.'})

        # Verify OTP code
        success, message = otp.verify(otp_code)

        if not success:
            raise serializers.ValidationError({'otp': message})

        # Store instances for view to use
        data['_user'] = user
        data['_otp_instance'] = otp
        return data


class SignupSerializer(serializers.ModelSerializer):
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