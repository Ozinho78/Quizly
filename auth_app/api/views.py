from django.conf import settings # access Django settings for lifetimes/flags
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.serializers import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView # DRF base API view
from rest_framework.request import Request
from rest_framework.response import Response # DRF HTTP response wrapper
from rest_framework import status # symbolic HTTP status codes
from rest_framework_simplejwt.tokens import RefreshToken # token issuer for JWTs
from rest_framework_simplejwt.exceptions import TokenError
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
        
        
@method_decorator(csrf_exempt, name='dispatch')
class LogoutView(APIView):
    """
    Log the user out by clearing JWT cookies and (best-effort) blacklisting the refresh token.
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """
        Steps:
          1) Check if the refresh cookie is present -> else 401.
          2) Try to blacklist the refresh token if blacklist app is installed.
          3) Delete both cookies on the response and return 200 with detail.
        """
        # Cookie-Namen aus Settings (Fallbacks wie in LoginView)
        access_cookie_name = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')
        refresh_cookie_name = getattr(settings, 'JWT_REFRESH_COOKIE_NAME', 'refresh_token')

        # Flags (so löschen/überschreiben den identischen Cookie)
        cookie_secure = getattr(settings, 'JWT_COOKIE_SECURE', True)
        cookie_samesite = getattr(settings, 'JWT_COOKIE_SAMESITE', 'Lax')

        # 1) Auth-Gate per Cookie
        refresh_token = request.COOKIES.get(refresh_cookie_name)
        if not refresh_token:
            return Response(
                {'detail': 'Authentication credentials were not provided.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 2) Best-effort Blacklist (ohne harte Abhängigkeit)
        try:
            if 'rest_framework_simplejwt.token_blacklist' in getattr(settings, 'INSTALLED_APPS', []):
                from rest_framework_simplejwt.tokens import RefreshToken  # lazy import
                try:
                    RefreshToken(refresh_token).blacklist()
                except Exception:
                    # ungültig/abgelaufen/schon geblacklistet → egal fürs Logout
                    pass
        except Exception:
            # Import-Fehler oder anderes → nicht fatal fürs Logout
            pass

        # 3) Cookies löschen und 200 zurück
        resp = Response(
            {'detail': 'Log-Out successfully! All Tokens will be deleted. Refresh token is now invalid.'},
            status=status.HTTP_200_OK
        )
        resp.delete_cookie(
            key=access_cookie_name,
            path='/',
            samesite=cookie_samesite,   # ok
            # domain=...                # nur falls du beim Setzen auch eine Domain gesetzt hattest
        )
        resp.delete_cookie(
            key=refresh_cookie_name,
            path='/',
            samesite=cookie_samesite,
        )
        return resp
    
    
@method_decorator(csrf_exempt, name='dispatch')
class TokenRefreshView(APIView):
    """
    Issue a new access token from the refresh token stored in an HttpOnly cookie.

    Behavior:
      - Requires the presence of the 'refresh_token' cookie.
      - Validates the refresh token and issues a new access token.
      - Sets the new 'access_token' cookie on the response.
      - Returns JSON body: {'detail': 'Token refreshed', 'access': '<new_access>'}.
      - Returns 401 if the refresh cookie is missing or invalid.
      - Returns 500 for unexpected server errors.
    """

    # No SessionAuthentication/CSRF; we authenticate via the presence of the cookie.
    authentication_classes = []  # disable default session auth
    permission_classes = []      # open endpoint, gated by cookie check

    def post(self, request):
        """
        POST: Refresh the access token using the refresh cookie.
        """
        try:
            # Read cookie names and flags from settings with sane fallbacks (mirrors LoginView).
            access_cookie_name = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')  # name of access cookie
            refresh_cookie_name = getattr(settings, 'JWT_REFRESH_COOKIE_NAME', 'refresh_token')  # name of refresh cookie
            cookie_secure = getattr(settings, 'JWT_COOKIE_SECURE', True)  # use secure flag in prod
            cookie_samesite = getattr(settings, 'JWT_COOKIE_SAMESITE', 'Lax')  # default samesite

            # Pull refresh token from cookies; if missing, treat as unauthenticated (spec requires 401).
            refresh_token = request.COOKIES.get(refresh_cookie_name)  # get refresh jwt from cookie jar
            if not refresh_token:  # if no cookie present
                return Response(  # reply with 401 as per spec
                    {'detail': 'Refresh token missing.'},  # short explanation
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Validate the refresh token and derive a new access token.
            try:
                refresh_obj = RefreshToken(refresh_token)  # may raise TokenError if malformed/expired
                new_access = refresh_obj.access_token      # create a fresh access token bound to same user
            except TokenError:  # invalid/expired/bad signature
                return Response(  # respond with 401 according to spec
                    {'detail': 'Invalid refresh token.'},  # clear message
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Determine cookie lifetime for the access cookie from SIMPLE_JWT (fallback 5 minutes).
            access_lifetime = getattr(settings, 'SIMPLE_JWT', {}).get('ACCESS_TOKEN_LIFETIME')  # timedelta or None
            access_max_age = int(access_lifetime.total_seconds()) if access_lifetime else 300   # seconds for cookie

            # Prepare success payload including the access token string.
            body = {  # response body matching your contract
                'detail': 'Token refreshed',
                'access': str(new_access),  # string version of the token
            }

            # Build the response with HTTP 200.
            resp = Response(body, status=status.HTTP_200_OK)  # success response

            # Set/overwrite the 'access_token' cookie with the fresh token.
            resp.set_cookie(                  # write the cookie to the client
                key=access_cookie_name,       # cookie name
                value=str(new_access),        # jwt string
                max_age=access_max_age,       # seconds
                secure=cookie_secure,         # HTTPS-only in prod
                httponly=True,                # HttpOnly requirement
                samesite=cookie_samesite,     # samesite policy
                path='/',                     # cookie applies to all paths
            )

            # Done.
            return resp  # send response with new access cookie

        except Exception:
            # Any unexpected error becomes a 500 per your spec (you also have a global handler set).
            return Response({'detail': 'Internal server error.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
class MeView(APIView):
    """
    Returns minimal info about the authenticated user.
    Requires CookieJWTAuthentication (configured globally).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response({'id': u.id, 'username': u.username, 'email': u.email}, status=200)