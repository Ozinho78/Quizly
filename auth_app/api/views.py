from django.conf import settings # access Django settings for lifetimes/flags
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.serializers import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView # DRF base API view
from rest_framework.request import Request
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


@method_decorator(csrf_exempt, name='dispatch')   # <-- neu: komplette View von CSRF befreien
class LoginView(APIView):
    """
    Handle user login and set JWT cookies.

    On success:
      - returns 200 with user payload and a 'detail' message
      - sets 'access_token' and 'refresh_token' as HttpOnly cookies

    On failure:
      - returns 401 for invalid credentials
      - returns 500 for unexpected server errors
    """
    # allow unauthenticated access
    permission_classes = [AllowAny]
    # IMPORTANT: disable SessionAuthentication to avoid CSRF 403 on POST
    authentication_classes = []  # wichtig: verhindert CSRF via SessionAuthentication

    def post(self, request: Request):
        """
        Validate credentials, generate JWT tokens, and set them in HttpOnly cookies.
        """
        # instantiate the serializer with incoming JSON payload
        serializer = LoginSerializer(data=request.data)
        try:
            # trigger validation; raises ValidationError on invalid input/credentials
            serializer.is_valid(raise_exception=True)
            # retrieve the authenticated user injected by serializer.validate()
            user = serializer.validated_data['user']

            # create a refresh token for the user via SimpleJWT
            refresh = RefreshToken.for_user(user)
            # derive the access token from the refresh
            access = refresh.access_token

            # prepare the response body following the required schema
            response_data = {
                'detail': 'Login successfully!',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                },
            }

            # build the DRF Response with a 200 OK status
            resp = Response(response_data, status=status.HTTP_200_OK)

            # read cookie/security flags from settings with sensible defaults
            cookie_secure = getattr(settings, 'JWT_COOKIE_SECURE', True)  # True in production
            cookie_httponly = True  # MUST be HttpOnly per requirement
            cookie_samesite = getattr(settings, 'JWT_COOKIE_SAMESITE', 'Lax')  # 'Lax' is a good default
            access_cookie_name = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')  # cookie name for access
            refresh_cookie_name = getattr(settings, 'JWT_REFRESH_COOKIE_NAME', 'refresh_token')  # cookie name for refresh

            # determine max_age for cookies from SIMPLE_JWT lifetimes if available
            access_lifetime = getattr(settings, 'SIMPLE_JWT', {}).get('ACCESS_TOKEN_LIFETIME')
            # compute access cookie max_age in seconds if lifetime is provided, else default to 5 minutes
            access_max_age = int(access_lifetime.total_seconds()) if access_lifetime else 300

            refresh_lifetime = getattr(settings, 'SIMPLE_JWT', {}).get('REFRESH_TOKEN_LIFETIME')
            # compute refresh cookie max_age in seconds if lifetime is provided, else default to 1 day
            refresh_max_age = int(refresh_lifetime.total_seconds()) if refresh_lifetime else 86400

            # set the access token cookie on the response
            resp.set_cookie(
                key=access_cookie_name,                  # cookie key/name
                value=str(access),                       # JWT access token as string
                max_age=access_max_age,                  # lifetime in seconds
                secure=cookie_secure,                    # send only over HTTPS when True
                httponly=cookie_httponly,                # prevent JS access to the cookie
                samesite=cookie_samesite,                # CSRF mitigation attribute
                path='/',                                # cookie path for whole site
            )

            # set the refresh token cookie on the response
            resp.set_cookie(
                key=refresh_cookie_name,                 # cookie key/name
                value=str(refresh),                      # JWT refresh token as string
                max_age=refresh_max_age,                 # lifetime in seconds
                secure=cookie_secure,                    # send only over HTTPS when True
                httponly=cookie_httponly,                # prevent JS access to the cookie
                samesite=cookie_samesite,                # CSRF mitigation attribute
                path='/',                                # cookie path for whole site
            )

            # return the response with cookies set
            return resp

        except ValidationError as exc:
            # --- robust error extraction (list, dict, str) ---
            detail_obj = exc.detail

            # list: take first item and return immediately
            if isinstance(detail_obj, list) and detail_obj:
                return Response({'detail': str(detail_obj[0])}, status=status.HTTP_401_UNAUTHORIZED)

            # dict: iterate values; on first match (list or str) return immediately
            if isinstance(detail_obj, dict):
                for v in detail_obj.values():
                    if isinstance(v, list) and v:
                        return Response({'detail': str(v[0])}, status=status.HTTP_401_UNAUTHORIZED)
                    if isinstance(v, str):
                        return Response({'detail': v}, status=status.HTTP_401_UNAUTHORIZED)

            # str: return as-is
            if isinstance(detail_obj, str):
                return Response({'detail': detail_obj}, status=status.HTTP_401_UNAUTHORIZED)

            # fallback
            return Response({'detail': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

        except Exception as exc:
            # for any other unexpected error, return a 500 with generic detail
            # (You can also let DRF propagate this, but this matches your spec.)
            return Response({'detail': 'Internal server error.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)