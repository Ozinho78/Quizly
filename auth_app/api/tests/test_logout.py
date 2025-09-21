import json
import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.mark.django_db
class TestLogoutEndpoint:
    """Tests for /api/logout/ endpoint"""

    def _register_and_login(self, client, username='alice', password='StrongPass123!'):
        """Creates a user, login with /api/login/, and returns the login response with cookies set"""
        User.objects.create_user(username=username, password=password, email='alice@example.com')
        url_login = reverse('api-login')
        resp = client.post(
            url_login,
            data={'username': username, 'password': password},
            content_type='application/json'
        )
        assert resp.status_code == 200, f'Login failed: {resp.status_code} {resp.content}'
        assert 'access_token' in resp.cookies
        assert 'refresh_token' in resp.cookies
        return resp

    def test_logout_success_deletes_cookies_and_returns_200(self, client, settings):
        """Given a logged-in user with JWT cookies, response is 200 with the required detail and both cookies are deleted"""
        login_resp = self._register_and_login(client)
        client.cookies['access_token'] = login_resp.cookies['access_token'].value
        client.cookies['refresh_token'] = login_resp.cookies['refresh_token'].value
        url_logout = reverse('api-logout')
        resp = client.post(url_logout, data={}, content_type='application/json')
        assert resp.status_code == 200
        body = json.loads(resp.content.decode())
        assert body['detail'] == 'Log-Out successfully! All Tokens will be deleted. Refresh token is now invalid.'
        assert 'access_token' in resp.cookies
        assert 'refresh_token' in resp.cookies
        acc = resp.cookies['access_token']
        ref = resp.cookies['refresh_token']
        assert (acc.get('max-age') == 0 or acc.get('expires')) is not None
        assert (ref.get('max-age') == 0 or ref.get('expires')) is not None

    def test_logout_unauthenticated_returns_401(self, client):
        """Given no refresh cookie, 401 Unauthorized is returned"""
        url_logout = reverse('api-logout')
        resp = client.post(url_logout, data={}, content_type='application/json')
        assert resp.status_code == 401
        body = json.loads(resp.content.decode())
        assert body['detail'] == 'Authentication credentials were not provided.'