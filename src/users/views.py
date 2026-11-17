"""
API views for user management
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from django.contrib.auth import get_user_model

from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated, BasePermission

from users.roles import role_names, set_staff_roles

from .serializers import (
    RegisterSerializer,
    ActivateAccountSerializer,
    ResendOTPSerializer,
    RequestLoginOTPSerializer,
    LoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    UserSerializer,
    UserProfileSerializer,
    StaffAccountSerializer,
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
        user_name = user.get_full_name() or otp_instance.email
        send_otp_email(
            email=otp_instance.email,
            otp_code=otp_instance.otp,
            name=user_name,
            action="Activate your account",
            purpose="activation",
        )
        
        return Response(
            {
                'message': 'OTP has been sent to your email address.',
                'email': otp_instance.email
            },
            status=status.HTTP_200_OK
        )
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def request_login_otp_view(request):
    """
    Send a login OTP email for an active account (use before POST /api/users/login/ with otp).

    POST /api/users/request-login-otp/
    Body: { "email": "user@example.com" }
    """
    serializer = RequestLoginOTPSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['_user']
        from .models import OTP
        from .utils import send_otp_email

        otp_instance = OTP.create_otp(email=user.email)
        user_name = user.get_full_name() or otp_instance.email
        send_otp_email(
            email=otp_instance.email,
            otp_code=otp_instance.otp,
            name=user_name,
            action="Sign in to your account",
            purpose="login",
        )
        return Response(
            {
                'message': 'OTP has been sent to your email address.',
                'email': otp_instance.email,
            },
            status=status.HTTP_200_OK,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    Login with email and either password or code (OTP). Returns JWT tokens.

    POST /api/users/login/

    Option A — Password:
        { "email": "user@example.com", "password": "securepassword123" }

    Option B — Code (OTP):
        { "email": "user@example.com", "otp": "123456" }

    Do not send both password and otp.

    Response:
        { "access": "...", "refresh": "...", "user": { ... } }
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


class PasswordResetThrottle(SimpleRateThrottle):
    scope = "password_reset"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetThrottle])
def password_reset_request_view(request):
    """
    Email a password reset link.

    POST /api/users/password-reset/
    Body: { "email": "user@example.com" }

    The message is sent only to an existing active account's own email.
    The response is the same when no account matches, so the call does not
    reveal which addresses are registered.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = serializer.validated_data.get("_user")
    if user is not None and user.is_active and user.email:
        from .utils import send_password_reset_email

        send_password_reset_email(user)

    return Response(
        {"message": "A password reset link has been sent to your email address."},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetThrottle])
def password_reset_confirm_view(request):
    """
    Set a new password from the link in the reset email.

    POST /api/users/password-reset/confirm/
    Body: { "uid": "...", "token": "...", "password": "newpassword123" }
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    return Response(
        {"message": "Password updated. You can sign in with your new password."},
        status=status.HTTP_200_OK,
    )


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
        
        # Get profile picture from Google (userinfo includes 'picture' URL)
        picture_url = user_info.get('picture') or ''

        # Try to find existing user by email
        user = None
        try:
            user = User.objects.get(email=email)
            # Ensure @endovillehealth.com users are staff (e.g. existing account)
            if email.endswith('@endovillehealth.com') and not user.is_staff:
                user.is_staff = True
                user.save(update_fields=['is_staff'])
        except User.DoesNotExist:
            # Create new user with Google profile data (manager sets is_staff for @endovillehealth.com)
            user = User.objects.create_user(
                email=email,
                first_name=user_info.get('given_name', ''),
                last_name=user_info.get('family_name', ''),
                image_url=picture_url,
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

        # Keep profile image in sync with Google when they sign in with Google
        if picture_url and user.image_url != picture_url:
            user.image_url = picture_url
            user.save(update_fields=['image_url'])
        
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


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def me_view(request):
    """
    Get or update the authenticated user's profile.

    GET /api/users/me/
    PATCH /api/users/me/

    Editable fields:
    - first_name
    - last_name
    - image_url
    - image_ref
    - gender
    - date_of_birth

    Read-only (for now):
    - email
    - phone
    """
    user = request.user

    if request.method == "GET":
        return Response(UserProfileSerializer(user).data, status=status.HTTP_200_OK)

    serializer = UserProfileSerializer(user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def is_staff_view(request):
    """
    Check if the authenticated user is staff or a superuser admin.

    GET /api/users/is-staff/
    """
    return Response(
        {
            "is_staff": bool(request.user.is_staff),
            "is_superuser": bool(request.user.is_superuser),
            "roles": role_names(request.user),
        },
        status=status.HTTP_200_OK,
    )


class IsSuperuser(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_superuser)


def _staff_payload(user):
    return {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "roles": role_names(user),
    }


@api_view(["GET", "POST"])
@permission_classes([IsSuperuser])
def staff_users_view(request):
    """
    Admins list staff and add a staff user with ticked roles.

    GET /api/users/staff/
    POST /api/users/staff/
    """
    if request.method == "GET":
        staff = User.objects.filter(is_staff=True).order_by("email", "id")
        return Response([_staff_payload(user) for user in staff])

    serializer = StaffAccountSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if not data.get("password"):
        return Response({"password": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(email__iexact=data["email"]).exists():
        return Response({"email": ["A user with this email already exists."]}, status=status.HTTP_400_BAD_REQUEST)
    phone = data.get("phone")
    if phone and User.objects.filter(phone=phone).exists():
        return Response({"phone": ["A user with this phone already exists."]}, status=status.HTTP_400_BAD_REQUEST)
    from django.core.exceptions import ValidationError

    try:
        user = User.objects.create_user(
            email=data["email"].lower(),
            phone=phone,
            password=data["password"],
            first_name=data.get("first_name") or "",
            last_name=data.get("last_name") or "",
            is_staff=True,
            is_active=data.get("is_active", True),
        )
    except ValidationError as exc:
        return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    set_staff_roles(user, data["roles"])
    return Response(_staff_payload(user), status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH"])
@permission_classes([IsSuperuser])
def staff_user_detail_view(request, user_id):
    """
    Read or change one staff user. Roles replace the previous ticks.

    GET /api/users/staff/{id}/
    PATCH /api/users/staff/{id}/
    """
    try:
        user = User.objects.get(pk=user_id, is_staff=True)
    except User.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "GET":
        return Response(_staff_payload(user))

    serializer = StaffAccountSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if "email" in request.data and data.get("email", "").lower() != (user.email or "").lower():
        return Response({"email": ["Email cannot be changed."]}, status=status.HTTP_400_BAD_REQUEST)
    if "password" in data and data["password"]:
        user.set_password(data["password"])
    if "first_name" in data:
        user.first_name = data["first_name"]
    if "last_name" in data:
        user.last_name = data["last_name"]
    if "phone" in data:
        phone = data["phone"]
        if phone and User.objects.exclude(pk=user.pk).filter(phone=phone).exists():
            return Response({"phone": ["A user with this phone already exists."]}, status=status.HTTP_400_BAD_REQUEST)
        user.phone = phone
    if "is_active" in data:
        user.is_active = data["is_active"]
    user.save()
    if "roles" in data and not user.is_superuser:
        set_staff_roles(user, data["roles"])
    return Response(_staff_payload(user))


@api_view(["GET"])
@permission_classes([IsAdminUser])
def staff_change_log_view(request):
    """
    Staff changes to orders, payments, prices, and refunds.

    GET /api/users/staff-changes/?target_type=&order_id=&action=&limit=
    """
    from users.models import StaffChangeLog

    logs = StaffChangeLog.objects.select_related("actor")
    target_type = request.query_params.get("target_type")
    action = request.query_params.get("action")
    order_id = request.query_params.get("order_id")
    if target_type:
        logs = logs.filter(target_type=target_type)
    if action:
        logs = logs.filter(action=action)
    if order_id:
        logs = logs.filter(order_id=order_id)
    try:
        limit = min(int(request.query_params.get("limit") or 100), 500)
    except (TypeError, ValueError):
        limit = 100
    rows = []
    for log in logs[:limit]:
        rows.append(
            {
                "id": log.pk,
                "actor_id": log.actor_id,
                "actor_email": log.actor.email if log.actor_id else None,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "order_id": log.order_id,
                "summary": log.summary,
                "changes": log.changes,
                "created_at": log.created_at,
            }
        )
    return Response(rows)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def staff_customers_view(request):
    """
    Customers and the shipping addresses saved on their orders.

    GET /api/users/customers/
    """
    from django.db.models import Prefetch

    from orders.models import ShippingAddress

    address_fields = (
        "full_name",
        "phone",
        "email",
        "address_line_1",
        "address_line_2",
        "city",
        "state",
        "postal_code",
        "country",
    )
    customers = (
        User.objects.filter(is_staff=False)
        .prefetch_related(
            Prefetch(
                "shippingaddress_set",
                queryset=ShippingAddress.objects.order_by("-created_at", "-id"),
            )
        )
        .order_by("first_name", "last_name", "email", "id")
    )
    rows = []
    for customer in customers:
        seen = set()
        addresses = []
        for address in customer.shippingaddress_set.all():
            key = tuple((getattr(address, field) or "").strip().lower() for field in address_fields)
            if key in seen:
                continue
            seen.add(key)
            addresses.append({"id": address.id, **{field: getattr(address, field) for field in address_fields}})
        rows.append(
            {
                "id": customer.id,
                "email": customer.email,
                "phone": customer.phone,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "is_active": customer.is_active,
                "created_at": customer.created_at,
                "addresses": addresses,
            }
        )
    return Response(rows)
