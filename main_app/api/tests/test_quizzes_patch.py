import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from main_app.models import Quiz, Question


@pytest.fixture
def api_client():
    """Returns a DRF APIClient instance for making HTTP requests in tests"""
    return APIClient()


@pytest.fixture
def user(db):
    """Creates and returns a user for authentication in tests"""
    User = get_user_model()
    return User.objects.create_user(username='alice', email='alice@example.com', password='pw123456')


@pytest.fixture
def other_user(db):
    """Creates and returns a second user to test permission boundaries"""
    User = get_user_model()
    return User.objects.create_user(username='bob', email='bob@example.com', password='pw123456')


def auth_with_cookie(client: APIClient, user):
    """Issues an access token for 'user' and set it as HttpOnly cookie on the client"""
    token = AccessToken.for_user(user)
    client.cookies['access_token'] = str(token)


@pytest.mark.django_db
def test_patch_quiz_updates_title_and_returns_full_payload(api_client, user):
    """Owner patches the title, response is 200 and contains full quiz details"""
    quiz = Quiz.objects.create(
        user=user,
        title='Original Title',
        description='Quiz Description',
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    )
    Question.objects.create(
        quiz=quiz,
        question_title='Question 1',
        question_options=['Option A', 'Option B', 'Option C', 'Option D'],
        answer='Option A',
    )
    auth_with_cookie(api_client, user)
    url = reverse('quiz-detail', kwargs={'pk': quiz.id})
    res = api_client.patch(url, data={'title': 'Partially Updated Title'}, format='json')
    assert res.status_code == 200
    body = res.json()
    assert body['id'] == quiz.id
    assert body['title'] == 'Partially Updated Title'
    assert body['description'] == 'Quiz Description'
    assert body['video_url'] == 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    assert isinstance(body.get('questions'), list) and len(body['questions']) == 1
    assert 'created_at' in body and 'updated_at' in body


@pytest.mark.django_db
def test_patch_quiz_requires_authentication(api_client, user):
    """Unauthenticated requests should throw 401"""
    quiz = Quiz.objects.create(
        user=user,
        title='Original Title',
        description='Quiz Description',
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    )
    url = reverse('quiz-detail', kwargs={'pk': quiz.id})
    res = api_client.patch(url, data={'title': 'X'}, format='json')
    assert res.status_code == 401


@pytest.mark.django_db
def test_patch_quiz_forbidden_for_non_owner(api_client, user, other_user):
    """Different authenticated user must receive 403 when trying to patch someone else's quiz"""
    quiz = Quiz.objects.create(
        user=other_user,
        title='Original Title',
        description='Quiz Description',
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    )
    auth_with_cookie(api_client, user)
    url = reverse('quiz-detail', kwargs={'pk': quiz.id})
    res = api_client.patch(url, data={'title': 'Hacked'}, format='json')
    assert res.status_code == 403


@pytest.mark.django_db
def test_patch_quiz_rejects_unknown_fields(api_client, user):
    """Sending fields that are not allowed by the write-serializer should return 400"""
    quiz = Quiz.objects.create(
        user=user,
        title='Original Title',
        description='Quiz Description',
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    )
    auth_with_cookie(api_client, user)
    url = reverse('quiz-detail', kwargs={'pk': quiz.id})
    res = api_client.patch(url, data={
        'video_url': 'https://youtu.be/NEWID',
        'questions': [{'id': 999}]
    }, format='json')
    assert res.status_code == 400