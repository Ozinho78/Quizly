from typing import Optional, Tuple
from django.conf import settings
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication

class CookieJWTAuthentication(JWTAuthentication):
    """Authenticates using the JWT access token stored in an HttpOnly cookie. Falls back to Authorization header if absent"""
    
    def authenticate(self, request: Request) -> Optional[Tuple[object, str]]:
        cookie_name = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')
        raw = request.COOKIES.get(cookie_name)
        if raw:
            validated = self.get_validated_token(raw)
            user = self.get_user(validated)
            return (user, validated)
        return super().authenticate(request)
