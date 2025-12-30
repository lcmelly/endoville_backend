"""
API views for user management
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import get_user_model

from .serializers import (
    RegisterSerializer,
    ActivateAccountSerializer,
    ResendOTPSerializer,
    LoginSerializer,
    UserSerializer
)

User = get_user_model()


@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """
    Register a new user account.
    
    POST /api/users/register/
    
    Request Body:
    {
        "email": "user@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "password": "securepassword123"
    }
    
    Response:
    {
        "message": "Registration successful. Please check your email for OTP to activate your account.",
        "user": {
            "id": 1,
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "is_active": false,
            ...
        }
    }
    """
    serializer = RegisterSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.save()
        
        return Response(
            {
                'message': 'Registration successful. Please check your email for OTP to activate your account.',
                'user': UserSerializer(user).data
            },
            status=status.HTTP_201_CREATED
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def activate_account_view(request):
    """
    Activate user account using OTP.
    
    POST /api/users/activate/
    
    Request Body:
    {
        "email": "user@example.com",
        "otp": "123456"
    }
    
    Response:
    {
        "message": "Account activated successfully.",
        "user": {
            "id": 1,
            "email": "user@example.com",
            "is_active": true,
            ...
        }
    }
    """
    serializer = ActivateAccountSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['_user']
        
        # Activate the user account
        user.is_active = True
        user.save()
        
        return Response(
            {
                'message': 'Account activated successfully.',
                'user': UserSerializer(user).data
            },
            status=status.HTTP_200_OK
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def send_otp_view(request):
    """
    Resend OTP for account activation.
    
    POST /api/users/resend-otp/
    
    Request Body:
    {
        "email": "user@example.com"
    }
    
    Response:
    {
        "message": "OTP has been sent to your email address.",
        "email": "user@example.com"
    }
    """
    serializer = ResendOTPSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['_user']
        
        # Create and send new OTP for user account
        from .models import OTP
        from .utils import send_otp_email
        
        otp_instance = OTP.create_otp(email=user.email)
        user_name = user.get_full_name() or user.email
        send_otp_email(
            email=user.email,
            otp_code=otp_instance.otp,
            name=user_name
        )
        
        return Response(
            {
                'message': 'OTP has been sent to your email address.',
                'email': user.email
            },
            status=status.HTTP_200_OK
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Login user with email, password, and OTP. Returns JWT tokens.
    
    POST /api/users/login/
    
    Request Body:
    {
        "email": "user@example.com",
        "password": "securepassword123",
        "otp": "123456"
    }
    
    Response:
    {
        "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
        "user": {
            "id": 1,
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "is_active": true,
            ...
        }
    }
    """
    serializer = LoginSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['_user']
        
        # Generate JWT tokens
        from rest_framework_simplejwt.tokens import RefreshToken
        
        refresh = RefreshToken.for_user(user)
        
        # Update last login if configured
        from django.utils import timezone
        if hasattr(user, 'last_login'):
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
        
        return Response(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data
            },
            status=status.HTTP_200_OK
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def google_login_view(request):
    """
    Sign in/Sign up with Google OAuth.
    
    POST /api/users/google-login/
    
    Request Body:
    {
        "access_token": "google_access_token_from_client"
    }
    
    Response:
    {
        "access": "jwt_access_token",
        "refresh": "jwt_refresh_token",
        "user": {
            "id": 1,
            "email": "user@gmail.com",
            "first_name": "John",
            "last_name": "Doe",
            "is_active": true,
            ...
        }
    }
    
    Note: The client should first complete Google OAuth flow to get access_token,
    then send that token to this endpoint.
    """
    access_token = request.data.get('access_token')
    
    if not access_token:
        return Response(
            {'error': 'access_token is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        import requests
        from allauth.socialaccount.models import SocialAccount
        from rest_framework_simplejwt.tokens import RefreshToken
        from django.utils import timezone
        
        # Verify token and get user info from Google
        user_info_response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        
        if user_info_response.status_code != 200:
            return Response(
                {'error': 'Invalid or expired Google access token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_info = user_info_response.json()
        email = user_info.get('email')
        google_id = user_info.get('id')
        
        if not email:
            return Response(
                {'error': 'Email not provided by Google'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Normalize email
        email = email.lower()
        
        # Try to find existing user by email
        user = None
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Create new user
            user = User.objects.create_user(
                email=email,
                first_name=user_info.get('given_name', ''),
                last_name=user_info.get('family_name', ''),
                is_active=True,  # Google verifies email
                phone=None
            )
            # Set unusable password for OAuth users
            user.set_unusable_password()
            user.save()
        
        # Create or update social account
        social_account, created = SocialAccount.objects.get_or_create(
            user=user,
            provider='google',
            defaults={
                'uid': str(google_id),
                'extra_data': user_info
            }
        )
        
        if not created:
            # Update existing social account
            social_account.uid = str(google_id)
            social_account.extra_data = user_info
            social_account.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # Update last login
        if hasattr(user, 'last_login'):
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
        
        return Response(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data
            },
            status=status.HTTP_200_OK
        )
        
    except requests.exceptions.RequestException as e:
        return Response(
            {'error': f'Failed to verify Google token: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Authentication failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
