"""Validate, sanitize, and verify customer messages."""

import re

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.utils.html import strip_tags
from rest_framework import serializers

from .models import CustomerMessage, Order

MESSAGE_MAX_LENGTH = 500
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PHONE = re.compile(r"^\+?[0-9]{8,15}$")
_ORDER_NUMBER = re.compile(r"^[A-Za-z0-9_-]{8,32}$")


def clean_message(value: str) -> str:
    text = strip_tags(value or "")
    text = _CONTROL.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    if not text:
        raise serializers.ValidationError("Enter a message.")
    if len(text) > MESSAGE_MAX_LENGTH:
        raise serializers.ValidationError(f"Message must be {MESSAGE_MAX_LENGTH} characters or fewer.")
    return text


def clean_phone(value: str) -> str:
    raw = strip_tags(value or "")
    raw = re.sub(r"[\s().-]", "", raw)
    if not _PHONE.match(raw):
        raise serializers.ValidationError("Enter a valid phone number.")
    return raw


def clean_email(value: str) -> str:
    email = strip_tags(value or "").strip().lower()
    try:
        validate_email(email)
    except DjangoValidationError as exc:
        raise serializers.ValidationError("Enter a valid email address.") from exc
    return email


def verify_human(token: str, remote_ip: str) -> None:
    """Ask the captcha provider whether this token was solved by a person."""
    secret = (getattr(settings, "CUSTOMER_MESSAGE_CAPTCHA_SECRET", "") or "").strip()
    if not secret:
        raise serializers.ValidationError("Human verification is not configured.")
    url = getattr(
        settings,
        "CUSTOMER_MESSAGE_CAPTCHA_VERIFY_URL",
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    )
    try:
        response = requests.post(
            url,
            data={"secret": secret, "response": token, "remoteip": remote_ip or ""},
            timeout=5,
        )
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise serializers.ValidationError("Human verification failed.") from exc
    if response.status_code != 200 or not payload.get("success"):
        raise serializers.ValidationError("Human verification failed.")


def remember_contact(contact: str) -> None:
    """Allow three successful messages per email or phone each day."""
    key = f"customer-message:{contact}"
    count = cache.get(key, 0)
    if count >= 3:
        raise serializers.ValidationError("Too many messages from this contact. Try again later.")
    cache.set(key, count + 1, 60 * 60 * 24)


class CustomerMessageSerializer(serializers.Serializer):
    email = serializers.CharField(required=False, allow_blank=True, max_length=254)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    message = serializers.CharField(max_length=4000)
    order_number = serializers.CharField(required=False, allow_blank=True, max_length=32)
    captcha_token = serializers.CharField(max_length=2048)

    def validate_message(self, value):
        return clean_message(value)

    def validate_email(self, value):
        if not (value or "").strip():
            return ""
        return clean_email(value)

    def validate_phone(self, value):
        if not (value or "").strip():
            return ""
        return clean_phone(value)

    def validate_order_number(self, value):
        number = strip_tags(value or "").strip()
        if not number:
            return ""
        if not _ORDER_NUMBER.match(number):
            raise serializers.ValidationError("Order number is not valid.")
        return number

    def validate(self, attrs):
        if not attrs.get("email") and not attrs.get("phone"):
            raise serializers.ValidationError("Enter an email address or a phone number.")
        request = self.context.get("request")
        remote_ip = ""
        if request is not None:
            remote_ip = request.META.get("REMOTE_ADDR", "")
        try:
            verify_human(attrs["captcha_token"], remote_ip)
        except serializers.ValidationError as exc:
            detail = exc.detail
            message = detail[0] if isinstance(detail, list) else detail
            raise serializers.ValidationError({"captcha_token": message}) from exc

        order = None
        number = attrs.get("order_number") or ""
        if number:
            order = Order.objects.filter(public_id=number).first()
            if order is None:
                raise serializers.ValidationError({"order_number": "Order number is not valid."})
        attrs["order"] = order
        return attrs

    def create(self, validated_data):
        contact = validated_data.get("email") or validated_data.get("phone")
        remember_contact(contact)
        return CustomerMessage.objects.create(
            email=validated_data.get("email") or "",
            phone=validated_data.get("phone") or "",
            message=validated_data["message"],
            order=validated_data.get("order"),
        )


class CustomerMessageReadSerializer(serializers.ModelSerializer):
    order_number = serializers.SerializerMethodField()

    class Meta:
        model = CustomerMessage
        fields = ["id", "email", "phone", "message", "order_number", "created_at"]
        read_only_fields = fields

    def get_order_number(self, obj):
        if obj.order_id is None:
            return None
        return obj.order.public_id
