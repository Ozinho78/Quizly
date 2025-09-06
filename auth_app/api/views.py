from django.conf import settings # access Django settings for lifetimes/flags
from rest_framework.views import APIView # DRF base API view
from rest_framework.response import Response # DRF HTTP response wrapper
from rest_framework import status # symbolic HTTP status codes
from rest_framework_simplejwt.tokens import RefreshToken # token issuer for JWTs
from auth_app.api.serializers import RegisterSerializer, LoginSerializer


class RegisterView(APIView):
    """
    API endpoint for registering a new user.
    """

    def post(self, request):
        """
        Handle POST requests to create a new user.
        """
        serializer = RegisterSerializer(data=request.data)  # init serializer with request data
        # Request-Data:  {'username': 'RudiSchaus71', 'password': 'Password123%', 'email': 'rudi.schaus@schwimmbecken.swolf'}
        print("Data: ", request.data)

        if serializer.is_valid():  # validate input
            serializer.save()  # create user
            # Serializer:  {'username': 'RudiSchaus71', 'email': 'rudi.schaus@schwimmbecken.swolf'}
            print("Serializer: ", serializer.data)
            return Response({'detail': 'User created successfully!'}, status=status.HTTP_201_CREATED)

        # return validation errors
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """API endpoint to authenticate a user and set JWT cookies."""

    def post(self, request):
        """Authenticate credentials and set `access_token` and `refresh_token` as HttpOnly cookies."""
        serializer = LoginSerializer(data=request.data) # bind incoming JSON payload to serializer
        serializer.is_valid(raise_exception=True) # validate; raises 401 on bad creds via AuthenticationFailed
        user = serializer.validated_data['user'] # get authenticated user instance from serializer

        refresh = RefreshToken.for_user(user) # create a refresh token bound to the user
        access_token = str(refresh.access_token) # derive an access token from the refresh token
        refresh_token = str(refresh) # string version of the refresh token itself

        # Prepare response payload per the spec
        data = {
            'detail': 'Login successfully!', # confirmation message
            'user': { # include minimal user info back to the client
                'id': user.id, # database primary key
                'username': user.username, # chosen username
                'email': user.email, # email address (may be blank if not enforced elsewhere)
            }
        }
        response = Response(data, status=status.HTTP_200_OK) # 200 OK with payload

        # Determine cookie lifetimes from SIMPLE_JWT settings when available
        access_seconds = None # default to session cookie unless configured
        refresh_seconds = None # default to session cookie unless configured
        try:
            access_lifetime = settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME')
            if access_lifetime:
                access_seconds = int(access_lifetime.total_seconds())
                refresh_lifetime = settings.SIMPLE_JWT.get('REFRESH_TOKEN_LIFETIME')
            if refresh_lifetime:
                refresh_seconds = int(refresh_lifetime.total_seconds())
        except Exception:
            pass

        secure_flag = not getattr(settings, 'DEBUG', False) # True on production, False in dev

        # Set HttpOnly cookies
        response.set_cookie(
            key='access_token',
            value=access_token,
            httponly=True,
            secure=secure_flag,
            samesite='Lax',
            max_age=access_seconds,
            path='/',
        )
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            httponly=True,
            secure=secure_flag,
            samesite='Lax',
            max_age=refresh_seconds,
            path='/',
        )

        return response