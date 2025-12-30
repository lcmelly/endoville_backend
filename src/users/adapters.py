"""
Custom adapters for django-allauth to work with CustomUser model
"""
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for django-allauth
    Handles account creation and validation for CustomUser model
    """
    
    def is_open_for_signup(self, request):
        """
        Check if signup is open for registration
        """
        return True
    
    def save_user(self, request, user, form, commit=True):
        """
        Override save_user to handle CustomUser model properly
        """
        # Get email from form
        email = form.cleaned_data.get('email')
        
        # Set email if provided
        if email:
            user.email = email
        
        # Set password if provided
        password = form.cleaned_data.get('password1')
        if password:
            user.set_password(password)
        elif not user.has_usable_password():
            # For OAuth users, set unusable password
            user.set_unusable_password()
        
        # Save user
        if commit:
            user.save()
        
        return user


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter for django-allauth
    Handles social account creation and linking for CustomUser model
    """
    
    def is_open_for_signup(self, request, sociallogin):
        """
        Check if signup is open for social registration
        """
        return True
    
    def pre_social_login(self, request, sociallogin):
        """
        Invoked just after a user successfully authenticates via a
        social provider, but before the login is actually processed
        (and before the pre_social_login signal is emitted).
        
        We can use this to link social accounts to existing users by email.
        """
        # If the user is already logged in, link the social account
        if request.user.is_authenticated:
            sociallogin.connect(request, request.user)
            return
        
        # Check if a user with this email already exists
        email = sociallogin.account.extra_data.get('email')
        if email:
            try:
                user = User.objects.get(email=email)
                # Link the social account to the existing user
                sociallogin.connect(request, user)
            except User.DoesNotExist:
                # User doesn't exist, will be created
                pass
    
    def populate_user(self, request, sociallogin, data):
        """
        Populate user fields from social account data
        """
        user = sociallogin.user
        
        # Set email (required for CustomUser)
        email = data.get('email')
        if email:
            user.email = email.lower()  # Normalize email
        
        # Set name fields from social account
        first_name = data.get('first_name') or data.get('given_name', '')
        last_name = data.get('last_name') or data.get('family_name', '')
        
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        
        # Set user as active (since OAuth providers verify email)
        user.is_active = True
        
        # Set unusable password for OAuth users
        user.set_unusable_password()
        
        return user

