import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.serializers import ValidationError as DRFValidationError


@pytest.mark.django_db
def test_login_success(django_user_model):
    """Creates a user, POSTs valid credentials to /api/login/, expects 200 OK with correct body and cookies"""
    user = django_user_model.objects.create_user(username='alice', email='alice@example.com', password='testpass123')
    client = APIClient()
    url = reverse('api-login')
    payload = {'username': 'alice', 'password': 'testpass123'}
    response = client.post(url, payload, format='json')
    assert response.status_code == status.HTTP_200_OK
    assert response.data['detail'] == 'Login successfully!'
    assert response.data['user']['id'] == user.id
    assert response.data['user']['username'] == 'alice'
    assert response.data['user']['email'] == 'alice@example.com'
    access_cookie_name = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')
    refresh_cookie_name = getattr(settings, 'JWT_REFRESH_COOKIE_NAME', 'refresh_token')
    assert access_cookie_name in response.cookies
    assert refresh_cookie_name in response.cookies
    assert response.cookies[access_cookie_name]['httponly']
    assert response.cookies[refresh_cookie_name]['httponly']


@pytest.mark.django_db
def test_login_invalid_credentials(django_user_model):
    """POST invalid credentials to /api/login/, expect 401 Unauthorized with appropriate error message"""
    django_user_model.objects.create_user(username='bob', email='bob@example.com', password='topsecret')
    client = APIClient()
    url = reverse('api-login')
    payload = {'username': 'bob', 'password': 'wrongpass'}
    response = client.post(url, payload, format='json')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert 'detail' in response.data


@pytest.mark.django_db
def test_login_internal_error_returns_500(monkeypatch, django_user_model):
    """Forces an unexpected exception during validation to hit the generic 500 branch in the view"""
    django_user_model.objects.create_user(username='crash', email='crash@example.com', password='pw123456!')
    from auth_app.api import serializers as auth_serializers
    def boom(*args, **kwargs):
        raise Exception('unexpected')
    monkeypatch.setattr(auth_serializers.LoginSerializer, 'is_valid', boom)
    client = APIClient()
    url = reverse('api-login')
    response = client.post(url, {'username': 'crash', 'password': 'whatever'}, format='json')
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.data == {'detail': 'Internal server error.'}
