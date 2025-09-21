import pytest
from rest_framework.exceptions import ValidationError
from core.utils.validators import (
    validate_email_format,
    validate_email_unique,
    validate_password_strength,
)
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_validate_email_format_rejects_invalid():
    """Ensures validate_email_format raises ValidationError for syntactically invalid emails"""
    with pytest.raises(ValidationError):
        validate_email_format('not-an-email')


@pytest.mark.django_db
def test_validate_email_unique_rejects_duplicate():
    """Ensures validate_email_unique raises ValidationError when email already exists."""
    User.objects.create_user(username='u1', email='used@example.com', password='Xx1!xxxx')
    with pytest.raises(ValidationError):
        validate_email_unique('used@example.com')


@pytest.mark.parametrize(
    'pwd',
    [
        'Short1!',
        'nouppercase1!',
        'NOLOWERCASE1!',
        'NoDigits!!!!',
        'NoSpecials111',
    ],
)
def test_validate_password_strength_rejects_weak(pwd):
    """Ensures each individual password rule in validate_password_strength is enforced"""
    with pytest.raises(ValidationError):
        validate_password_strength(pwd)


def test_validate_password_strength_accepts_strong():
    """Sanity check that a strong password passes validation without raising"""
    validate_password_strength('Str0ng!Pass')
