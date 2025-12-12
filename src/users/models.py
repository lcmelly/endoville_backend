"""
This module defines a Custom User Model with Email OR Phone Number Authentication
:users can login with either email or phone number.
"""
from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.core.validators import EmailValidator, RegexValidator
from django.core.exceptions import ValidationError

class CustomUserManager(BaseUserManager):
    """
        Manager for CustomUser model.
        Handles creation of users with email OR phone number.
    """
    def create_user(self, email=None, phone=None, password=None, **extra_fields):
        """
        Create and save a User with the given email or phone and password.
        Args:
            email (str): The email of the user.
            phone (str): The phone number of the user.
            password (str): The password of the user.
            **extra_fields: Additional fields for the user.
        """
        # Ensure that at least one of email or phone is provided
        if not email and not phone:
            raise ValueError('The Email or Phone number must be set')

        # Remove email and phone from extra fields
        if email in extra_fields.keys():
            extra_fields.pop(email)
        if phone in extra_fields.keys():
            extra_fields.pop(phone)

        # Normalize and set email and phone if provided
        if email:
            email = self.normalize_email(email)
        if phone:
            phone_validator = RegexValidator(regex=r'^\+?1?\d{9,17}$', message="Phone number must be entered in the format: '+1299999999'. Up to 17 digits allowed.")
            phone_validator(phone)


        # Set default fields to False
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        user = self.model(email=email, phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, phone, password, **extra_fields):
        """
        Create and save a SuperUser with the given email, phone and password.
        Args:
            email (str): The email of the superuser.
            phone (str): The phone number of the superuser.
            password (str): The password of the superuser.
            **extra_fields: Additional fields for the superuser.
        """
        extra_fields['is_staff'] = True
        extra_fields['is_superuser'] = True

        if not extra_fields.get('is_staff'):
            raise ValueError('Superuser must have is_staff=True.')
        if not extra_fields.get('is_superuser'):
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, phone, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
        Custom User Model that supports using email or phone number for authentication.
    """
    username = None # Remove username
    email = models.EmailField('email address', unique=True, null=True, blank=True, validators=[EmailValidator()])
    phone = models.CharField('phone number', unique=True, max_length=17, null=True, blank=True, validators=[RegexValidator(regex=r'^\+?1?\d{9,17}$', message="Phone number must be entered in the format: '+129999999'. Up to 17 digits allowed.")])
    first_name = models.CharField('first name', max_length=30, null=True, blank=True)
    last_name = models.CharField('last name', max_length=30, null=True, blank=True)
    date_of_birth = models.DateField('date of birth', null=True, blank=True)
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('N', 'Prefer not to say')
    ]
    gender = models.CharField('gender', max_length=1, choices=GENDER_CHOICES, null=True, blank=True)

    is_staff = models.BooleanField('staff status', default=False)
    is_active = models.BooleanField('active', default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'  # Use email as the unique identifier
    REQUIRED_FIELDS = []  # No additional required fields

    objects = CustomUserManager() # Assign the custom user manager

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def clean(self):
        """Ensure that either email or phone is provided."""
        super().clean()
        if not self.email and not self.phone:
            raise ValidationError('Either email or phone number must be provided.')

    def save(self, *args, **kwargs):
        """Override save to ensure clean is called."""
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        """Return email or phone, name if available and is_active, is_staff flags."""
        user_str = f"{self.get_full_name()} ({self.identifier})" if self.first_name else self.identifier + f"Active: {self.is_active}, Staff: {self.is_staff}"
        return user_str

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        if self.first_name is None and self.last_name is None:
            return self.email if self.email else self.phone
        else:
            return f'{self.first_name} {self.last_name}'.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name if self.first_name else (self.email if self.email else self.phone)

    @property
    def identifier(self):
        """Return the identifier used for login (email or phone)."""
        return self.email if self.email else self.phone

    def get_age(self):
        """Calculate the age of the user based on date_of_birth."""
        if self.date_of_birth:
            today = timezone.now().date()
            age = today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
            return age
        return None

