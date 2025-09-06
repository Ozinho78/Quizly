import re
from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError

EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
SPECIAL_CHARACTER_REGEX = r"[!@#$%^&*(),.?\":{}|<>]"


def validate_email_format(email: str):
    """Checks the email format"""
    if not re.match(EMAIL_REGEX, email):
        raise ValidationError({"email": "Ungültige E-Mail-Adresse."})


def validate_email_unique(email: str):
    """Checks if email already exists"""
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({"email": "E-Mail-Adresse wird bereits verwendet."})


def validate_password_strength(password: str):
    """Checks the password strength"""
    if len(password) < 8:
        raise ValidationError(
            {"password": "Passwort muss mindestens 8 Zeichen lang sein."})
    if not re.search(r"[A-Z]", password):
        raise ValidationError(
            {"password": "Mindestens ein Großbuchstabe erforderlich."})
    if not re.search(r"[a-z]", password):
        raise ValidationError(
            {"password": "Mindestens ein Kleinbuchstabe erforderlich."})
    if not re.search(r"\d", password):
        raise ValidationError(
            {"password": "Mindestens eine Zahl erforderlich."})
    if not re.search(SPECIAL_CHARACTER_REGEX, password):
        raise ValidationError(
            {"password": "Mindestens ein Sonderzeichen erforderlich."})
