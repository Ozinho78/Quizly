from django.contrib.auth.models import User
from django.contrib.auth import authenticate # import Django's authenticate helper
from rest_framework import serializers # DRF serializer base classes
from rest_framework.exceptions import AuthenticationFailed # standardized 401 error
from core.utils.validators import (
    validate_email_format,
    validate_email_unique,
    validate_password_strength,
    validate_non_empty,
)


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.

    This serializer enforces that:
    - 'email' is required (Django's default User.email is optional, so we make it required here),
    - 'password' is validated for strength and stored hashed,
    - and 'email' is validated for format and uniqueness.
    """

    # Make email explicitly required, because Django's default User.email has blank=True.
    email = serializers.EmailField(required=True, allow_blank=False)  # ensure 'email' must be provided
    # Make password write-only so it never appears in serialized responses.
    password = serializers.CharField(write_only=True)  # hide password in output

    class Meta:
        model = User  # tell DRF which model this serializer maps to
        fields = ('username', 'email', 'password')  # expose only the fields we need

    def validate_email(self, value: str) -> str:
        """
        Validates email format and uniqueness using your custom validators.
        """
        validate_email_format(value)  # check syntactic correctness of the email
        validate_email_unique(value)  # ensure no user with this email exists
        return value  # return the cleaned value

    def validate_password(self, value: str) -> str:
        """
        Validates the password strength using your custom validator.
        """
        validate_password_strength(value)  # enforce length, upper/lowercase, digits, special chars
        return value  # return the cleaned value

    def create(self, validated_data: dict) -> User:
        """
        Creates a new User instance with a hashed password.
        """
        user = User(  # construct a new User object
            username=validated_data['username'],  # set the username from validated data
            email=validated_data['email'],  # set the email from validated data
        )
        user.set_password(validated_data['password'])  # hash and set the password securely
        user.save()  # persist the user to the database
        return user  # return the created instance
    
    
class LoginSerializer(serializers.Serializer):
    """Validate user login credentials and resolve the authenticated user instance.
    This serializer enforces that both `username` and `password` are provided,
    then authenticates against Django's auth backends. On success, it attaches
    the authenticated `User` to `validated_data['user']` for the view layer.
    """
    username = serializers.CharField() # plain text username provided by the client
    password = serializers.CharField(write_only=True) # plain text password; never serialized back

    def validate_username(self, value: str) -> str:
        """Validate that username is a non-empty string using shared validators."""
        validate_non_empty(value, field_name='username') # call project validator
        return value.strip() # return trimmed username

    def validate_password(self, value: str) -> str:
        """Validate that password is a non-empty string using shared validators."""
        validate_non_empty(value, field_name='password') # call project validator
        return value # return password unchanged (no trimming to avoid issues)

    def validate(self, attrs: dict) -> dict:
        """Perform authentication and attach the authenticated user on success.
            If authentication fails, raise `AuthenticationFailed`, which DRF maps to HTTP 401.
        """
        username = attrs.get('username') # read raw username from input
        password = attrs.get('password') # read raw password from input
        user = authenticate(username=username, password=password) # try to authenticate via backends
        if user is None: # no matching user + password
            raise AuthenticationFailed('Invalid credentials.') # DRF-standard 401 error
        attrs['user'] = user # attach the authenticated user for use in the view
        return attrs # return the enriched, validated data