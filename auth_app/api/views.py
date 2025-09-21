from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.serializers import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from auth_app.api.serializers import RegisterSerializer, LoginSerializer


class RegisterView(APIView):
    """API endpoint for registering a new user"""
    def post(self, request):
        """Handles POST requests to create a new user"""
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'detail': 'User created successfully!'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    """Handles user login and sets JWT cookies"""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request: Request):
        """Validates credentials, generates JWT tokens and sets them in HttpOnly cookies"""
        serializer = LoginSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            access = refresh.access_token
            response_data = {
                'detail': 'Login successfully!',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                },
            }
            resp = Response(response_data, status=status.HTTP_200_OK)
            cookie_secure = getattr(settings, 'JWT_COOKIE_SECURE', True)
            cookie_httponly = True
            cookie_samesite = getattr(settings, 'JWT_COOKIE_SAMESITE', 'Lax')
            access_cookie_name = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')
            refresh_cookie_name = getattr(settings, 'JWT_REFRESH_COOKIE_NAME', 'refresh_token')
            access_lifetime = getattr(settings, 'SIMPLE_JWT', {}).get('ACCESS_TOKEN_LIFETIME')
            access_max_age = int(access_lifetime.total_seconds()) if access_lifetime else 300
            refresh_lifetime = getattr(settings, 'SIMPLE_JWT', {}).get('REFRESH_TOKEN_LIFETIME')
            refresh_max_age = int(refresh_lifetime.total_seconds()) if refresh_lifetime else 86400
            resp.set_cookie(
                key=access_cookie_name,               
                value=str(access),                    
                max_age=access_max_age,               
                secure=cookie_secure,                 
                httponly=cookie_httponly,             
                samesite=cookie_samesite,             
                path='/',                             
            )
            resp.set_cookie(
                key=refresh_cookie_name,
                value=str(refresh),
                max_age=refresh_max_age,
                secure=cookie_secure,
                httponly=cookie_httponly,
                samesite=cookie_samesite,
                path='/',
            )
            return resp

        except ValidationError as exc:
            detail_obj = exc.detail
            if isinstance(detail_obj, list) and detail_obj:
                return Response({'detail': str(detail_obj[0])}, status=status.HTTP_401_UNAUTHORIZED)
            if isinstance(detail_obj, dict):
                for v in detail_obj.values():
                    if isinstance(v, list) and v:
                        return Response({'detail': str(v[0])}, status=status.HTTP_401_UNAUTHORIZED)
                    if isinstance(v, str):
                        return Response({'detail': v}, status=status.HTTP_401_UNAUTHORIZED)
            if isinstance(detail_obj, str):
                return Response({'detail': detail_obj}, status=status.HTTP_401_UNAUTHORIZED)
            return Response({'detail': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as exc:
            return Response({'detail': 'Internal server error.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
@method_decorator(csrf_exempt, name='dispatch')
class LogoutView(APIView):
    """Logs the user out by clearing JWT cookies and blacklists the refresh token if possible"""
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """Checks for the refresh token cookie, blacklists it if possible, and clears both cookies"""
        access_cookie_name = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')
        refresh_cookie_name = getattr(settings, 'JWT_REFRESH_COOKIE_NAME', 'refresh_token')
        cookie_secure = getattr(settings, 'JWT_COOKIE_SECURE', True)
        cookie_samesite = getattr(settings, 'JWT_COOKIE_SAMESITE', 'Lax')
        refresh_token = request.COOKIES.get(refresh_cookie_name)
        if not refresh_token:
            return Response(
                {'detail': 'Authentication credentials were not provided.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        try:
            if 'rest_framework_simplejwt.token_blacklist' in getattr(settings, 'INSTALLED_APPS', []):
                from rest_framework_simplejwt.tokens import RefreshToken
                try:
                    RefreshToken(refresh_token).blacklist()
                except Exception:
                    pass
        except Exception:
            pass

        resp = Response(
            {'detail': 'Log-Out successfully! All Tokens will be deleted. Refresh token is now invalid.'},
            status=status.HTTP_200_OK
        )
        resp.delete_cookie(
            key=access_cookie_name,
            path='/',
            samesite=cookie_samesite,
        )
        resp.delete_cookie(
            key=refresh_cookie_name,
            path='/',
            samesite=cookie_samesite,
        )
        return resp
    
    
@method_decorator(csrf_exempt, name='dispatch')
class TokenRefreshView(APIView):
    """Issues a new access token from the refresh token stored in an HttpOnly cookie"""
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """Refreshs the access token using the refresh cookie"""
        try:
            access_cookie_name = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')
            refresh_cookie_name = getattr(settings, 'JWT_REFRESH_COOKIE_NAME', 'refresh_token')
            cookie_secure = getattr(settings, 'JWT_COOKIE_SECURE', True)
            cookie_samesite = getattr(settings, 'JWT_COOKIE_SAMESITE', 'Lax')
            refresh_token = request.COOKIES.get(refresh_cookie_name)
            if not refresh_token:
                return Response(
                    {'detail': 'Refresh token missing.'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            try:
                refresh_obj = RefreshToken(refresh_token)
                new_access = refresh_obj.access_token
            except TokenError:
                return Response(
                    {'detail': 'Invalid refresh token.'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            access_lifetime = getattr(settings, 'SIMPLE_JWT', {}).get('ACCESS_TOKEN_LIFETIME')
            access_max_age = int(access_lifetime.total_seconds()) if access_lifetime else 300
            body = {
                'detail': 'Token refreshed',
                'access': str(new_access),
            }
            resp = Response(body, status=status.HTTP_200_OK)
            resp.set_cookie(
                key=access_cookie_name,
                value=str(new_access),
                max_age=access_max_age,
                secure=cookie_secure,
                httponly=True,
                samesite=cookie_samesite,
                path='/',
            )
            return resp
        except Exception:
            return Response({'detail': 'Internal server error.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        