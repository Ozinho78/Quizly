import pytest
from rest_framework.exceptions import ValidationError
from django.contrib.auth.models import User
from core.utils.validators import (
    validate_email_format,
    validate_email_unique,
    validate_non_empty,
)


@pytest.mark.parametrize(
    'email',
    [
        'user@example.com',
        'user.name+tag@example.co.uk',
        'USER_123@example.io',
    ],
)
def test_validate_email_format_accepts_valid(email):
    """Valid emails should pass without error"""
    validate_email_format(email)


@pytest.mark.django_db
def test_validate_email_unique_accepts_new_email():
    """A fresh email (not in DB) should not raise an error"""
    User.objects.create_user(username='any', email='any@example.com', password='Xx1!xxxx')
    validate_email_unique('fresh@example.com')


@pytest.mark.parametrize('value', ['', '   ', None, 123])
def test_validate_non_empty_rejects_blank_or_nonstring(value):
    """validate_non_empty should reject blank/whitespace or non-string values"""
    with pytest.raises(ValidationError):
        validate_non_empty(value, field_name='testfield')


def test_validate_non_empty_returns_stripped_value():
    """validate_non_empty should return the stripped string"""
    result = validate_non_empty('   hello  ', field_name='name')
    assert result == 'hello'
