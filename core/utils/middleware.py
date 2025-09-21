from django.conf import settings

class CookieToAuthorizationMiddleware:
    """
    Mirror 'access_token' cookie into 'Authorization: Bearer ...' if header is missing.
    Keeps HttpOnly (läuft nur serverseitig).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cookie_name = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')
        raw = request.COOKIES.get(cookie_name)
        if raw and 'HTTP_AUTHORIZATION' not in request.META:
            request.META['HTTP_AUTHORIZATION'] = f'Bearer {raw}'
        return self.get_response(request)
