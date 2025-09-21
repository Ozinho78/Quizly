from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework import serializers
from core.utils.validators import (
    validate_email_format,
    validate_email_unique,
    validate_password_strength,
)

class RegisterSerializer(serializers.ModelSerializer):
    """ Serializer for user registration. Field 'email' is required, 'password' is validated for strength and stored hashed"""
    email = serializers.EmailField(required=True, allow_blank=False)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password')

    def validate_email(self, value: str) -> str:
        """Validates email format and uniqueness using custom validators"""
        validate_email_format(value)
        validate_email_unique(value)
        return value

    def validate_password(self, value: str) -> str:
        """Validates the password strength using custom validator"""
        validate_password_strength(value)
        return value

    def create(self, validated_data: dict) -> User:
        """Creates a new User instance with a hashed password"""
        user = User(
            username=validated_data['username'],
            email=validated_data['email'],
        )
        user.set_password(validated_data['password'])
        user.save()
        return user
    
    
class LoginSerializer(serializers.Serializer):
    """Validates username/password for login. Ensures that the fields are present and correct"""
    username = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    def validate(self, attrs):
        """Returns the authenticated user instance or raises a validation error"""
        username = attrs.get('username')
        password = attrs.get('password')
        user_obj = User.objects.filter(username=username).first()
        if user_obj is not None and not user_obj.is_active:
            if user_obj.check_password(password):
                raise serializers.ValidationError('User account is disabled.')

        user = authenticate(username=username, password=password)

        if user is None:
            raise serializers.ValidationError('Invalid credentials.')

        attrs['user'] = user
        return attrs