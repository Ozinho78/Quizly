from django.contrib.auth.models import User
from rest_framework import serializers
from core.utils.validators import (
    validate_email_format,
    validate_email_unique,
    validate_password_strength
)


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    Handles validation of username, email, and password.
    """

    class Meta:
        model = User
        fields = ('username', 'email', 'password')

    def validate_email(self, value):
        """Validate email format and uniqueness"""
        validate_email_format(value)  # check format
        validate_email_unique(value)  # check uniqueness
        return value

    def validate_password(self, value):
        """Validate password strength"""
        validate_password_strength(value)
        return value

    def create(self, validated_data):
        """Create new user with hashed password"""
        user = User(
            username=validated_data['username'],
            email=validated_data['email']
        )
        user.set_password(validated_data['password'])  # hash password
        user.save()
        return user