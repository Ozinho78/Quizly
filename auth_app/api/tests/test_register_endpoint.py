import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


@pytest.fixture
def api_client() -> APIClient:
    """Provides a DRF APIClient instance for making HTTP requests in tests"""
    return APIClient()


@pytest.mark.django_db
def test_register_success(api_client):
    """Ensures a brand-new user can be created via POST /api/register/"""
    payload = {
        'username': 'alice',
        'email': 'alice@example.com',
        'password': 'Str0ng!Pass'
    }
    response = api_client.post('/api/register/', data=payload, format='json')
    assert response.status_code == 201
    assert response.json() == {'detail': 'User created successfully!'}
    assert User.objects.filter(username='alice', email='alice@example.com').exists()


@pytest.mark.django_db
def test_register_invalid_email(api_client):
    """Checks that an invalid email is rejected with HTTP 400"""
    payload = {
        'username': 'bob',
        'email': 'not-an-email',
        'password': 'Str0ng!Pass'
    }
    response = api_client.post('/api/register/', data=payload, format='json')
    assert response.status_code == 400
    body = response.json()
    assert 'email' in body


@pytest.mark.django_db
def test_register_duplicate_email(api_client):
    """Verifies duplicate emails are rejected (validate_email_unique) with HTTP 400"""
    User.objects.create_user(username='existing', email='dupe@example.com', password='Xx1!xxxx')
    payload = {
        'username': 'charlie',
        'email': 'dupe@example.com',
        'password': 'Str0ng!Pass'
    }
    response = api_client.post('/api/register/', data=payload, format='json')
    assert response.status_code == 400
    assert 'email' in response.json()


@pytest.mark.django_db
def test_register_weak_password(api_client):
    """Ensures password strength rules are enforced (HTTP 400 on weak passwords)"""
    payload = {
        'username': 'daisy',
        'email': 'daisy@example.com',
        'password': 'weakpass'
    }
    response = api_client.post('/api/register/', data=payload, format='json')
    assert response.status_code == 400
    assert 'password' in response.json()


@pytest.mark.django_db
def test_register_missing_fields(api_client):
    """Confirms serializer validation catches missing required fields"""
    payload = {'username': 'eve'}
    response = api_client.post('/api/register/', data=payload, format='json')
    assert response.status_code == 400
    body = response.json()
    assert 'email' in body and 'password' in body


@pytest.mark.django_db
def test_register_handles_unexpected_server_error(api_client, monkeypatch):
    """Simulates an unexpected exception during user creation to test custom exception handler"""
    from auth_app.api.serializers import RegisterSerializer
    
    def caught(*args, **kwargs):
        raise Exception('unexpected')

    monkeypatch.setattr(RegisterSerializer, 'save', caught)
    payload = {
        'username': 'frank',
        'email': 'frank@example.com',
        'password': 'Str0ng!Pass'
    }
    response = api_client.post('/api/register/', data=payload, format='json')
    assert response.status_code == 500
    assert response.json() == {'detail': 'Internal Server Error'}
