import json
import pytest
from django.contrib.auth.models import User
from django.urls import reverse

@pytest.mark.django_db
class TestTokenRefreshEndpoint:
    """Tests for /api/token/refresh/ endpoint"""

    def _register_and_login(self, client, username='alice', password='StrongPass123!'):
        """Creates a user and performs login to obtain cookies"""
        User.objects.create_user(username=username, password=password, email='alice@example.com')
        login_url = reverse('api-login')
        resp = client.post(login_url, data={'username': username, 'password': password}, content_type='application/json')
        assert resp.status_code == 200, f'Login failed: {resp.status_code} {resp.content}'
        assert 'access_token' in resp.cookies
        assert 'refresh_token' in resp.cookies
        return resp

    def test_refresh_success_sets_new_access_cookie_and_returns_token(self, client):
        """Given a valid refresh cookie, 200 with body {'detail':'Token refreshed','access':...} and a new access cookie is set"""
        login_resp = self._register_and_login(client)
        client.cookies['refresh_token'] = login_resp.cookies['refresh_token'].value
        client.cookies['access_token'] = login_resp.cookies['access_token'].value
        url = reverse('api-token-refresh')
        resp = client.post(url, data={}, content_type='application/json')
        assert resp.status_code == 200
        data = json.loads(resp.content.decode())
        assert data['detail'] == 'Token refreshed'
        assert 'access' in data and isinstance(data['access'], str) and len(data['access']) > 0
        assert 'access_token' in resp.cookies
        assert resp.cookies['access_token'].value == data['access']

    def test_refresh_missing_cookie_returns_401(self, client):
        """Given no refresh cookie, 401 with an explanatory message is returned"""
        url = reverse('api-token-refresh')
        resp = client.post(url, data={}, content_type='application/json')
        assert resp.status_code == 401
        msg = json.loads(resp.content.decode())['detail']
        assert 'missing' in msg.lower()

    def test_refresh_invalid_cookie_returns_401(self, client):
        """Given an invalid refresh cookie, 401 with 'Invalid refresh token.' is returned"""
        client.cookies['refresh_token'] = 'not-a-valid-jwt'
        url = reverse('api-token-refresh')
        resp = client.post(url, data={}, content_type='application/json')
        assert resp.status_code == 401
        assert json.loads(resp.content.decode())['detail'] == 'Invalid refresh token.'