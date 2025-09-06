import re
from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError

EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
SPECIAL_CHARACTER_REGEX = r"[!@#$%^&*(),.?\":{}|<>]"


def validate_email_format(email: str):
    """Checks the email format"""
    if not re.match(EMAIL_REGEX, email):
        raise ValidationError({"email": "Invalid E-Mail-Address."})


def validate_email_unique(email: str):
    """Checks if email already exists"""
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({"email": "E-Mail-Address already in use."})


def validate_password_strength(password: str):
    """Checks the password strength"""
    if len(password) < 8:
        raise ValidationError(
            {"password": "Password must be at least 8 characters long."})
    if not re.search(r"[A-Z]", password):
        raise ValidationError(
            {"password": "At least one capital letter is required."})
    if not re.search(r"[a-z]", password):
        raise ValidationError(
            {"password": "At least one lowercase letter is required."})
    if not re.search(r"\d", password):
        raise ValidationError(
            {"password": "At least one number required."})
    if not re.search(SPECIAL_CHARACTER_REGEX, password):
        raise ValidationError(
            {"password": "At least one special character is required."})


def validate_non_empty(value: str, field_name: str = 'field') -> str:
    """Ensure a string field is non-empty and not just whitespace."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError({field_name: f'{field_name.capitalize()} may not be blank.'})
    return value.strip()