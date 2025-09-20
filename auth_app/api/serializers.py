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
    """
    Validate username/password for login.
    
    This serializer simply ensures the fields are present and authenticates the user.
    It does not generate tokens; the view handles token creation so that cookie logic stays in the view.
    """
    # define username field as a required CharField
    username = serializers.CharField(write_only=True, required=True)
    # define password field as a required CharField
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    def validate(self, attrs):
        """
        Perform credential validation via Django's authenticate().
        Returns the authenticated user instance or raises a validation error.
        """
        # extract username and password from validated input
        username = attrs.get('username')
        password = attrs.get('password')
        
        # --- Pre-check: inactive user with correct password -> show specific message ---
        # fetch user by username without raising (avoids user enumeration behavior change)
        user_obj = User.objects.filter(username=username).first()  # get user or None
        if user_obj is not None and not user_obj.is_active:        # if user exists but is inactive
            if user_obj.check_password(password):                   # only when password is correct
                # explicitly raise the "disabled" message expected by the test
                raise serializers.ValidationError('User account is disabled.')

        # call Django's authenticate to verify credentials against the configured auth backend(s)
        user = authenticate(username=username, password=password) # returns User or None

        # if authenticate() returns None, credentials are invalid
        if user is None:
            # raise a DRF ValidationError; the view will map this to a 401 response
            raise serializers.ValidationError('Invalid credentials.')

        # place the user object into the serializer context for easy access in the view
        attrs['user'] = user # stash the authenticated user
        # return the attrs dict including the user
        return attrs # return validated data