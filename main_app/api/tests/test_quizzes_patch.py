# tests/test_quizzes_patch.py
import pytest

from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from main_app.models import Quiz, Question


@pytest.fixture
def api_client():
    """
    Return a DRF APIClient instance for making HTTP requests in tests.
    """
    return APIClient()  # plain client; we will attach cookies per test as needed


@pytest.fixture
def user(db):
    """
    Create and return a user for authentication in tests.
    """
    User = get_user_model()
    return User.objects.create_user(username='alice', email='alice@example.com', password='pw123456')


@pytest.fixture
def other_user(db):
    """
    Create and return a second user to test permission boundaries.
    """
    User = get_user_model()
    return User.objects.create_user(username='bob', email='bob@example.com', password='pw123456')


def auth_with_cookie(client: APIClient, user):
    """
    Helper: issue an access token for 'user' and set it as HttpOnly cookie on the client.
    Cookie name defaults to 'access_token' per CookieJWTAuthentication.
    """
    token = AccessToken.for_user(user)
    client.cookies['access_token'] = str(token)  # simulate HttpOnly cookie auth


@pytest.mark.django_db
def test_patch_quiz_updates_title_and_returns_full_payload(api_client, user):
    """
    Happy path: owner patches the title; response is 200 and contains full quiz details.
    """
    # Arrange: create a quiz owned by 'user'
    quiz = Quiz.objects.create(
        user=user,
        title='Original Title',
        description='Quiz Description',
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    )
    # Add one question to ensure nested payload is present
    Question.objects.create(
        quiz=quiz,
        question_title='Question 1',
        question_options=['Option A', 'Option B', 'Option C', 'Option D'],
        answer='Option A',
    )

    # Authenticate via cookie
    auth_with_cookie(api_client, user)

    # Act: send PATCH with a new title
    url = reverse('quiz-detail', kwargs={'pk': quiz.id})
    res = api_client.patch(url, data={'title': 'Partially Updated Title'}, format='json')

    # Assert: status and payload shape
    assert res.status_code == 200
    body = res.json()
    assert body['id'] == quiz.id
    assert body['title'] == 'Partially Updated Title'
    assert body['description'] == 'Quiz Description'
    assert body['video_url'] == 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    assert isinstance(body.get('questions'), list) and len(body['questions']) == 1
    # Timestamps should be present
    assert 'created_at' in body and 'updated_at' in body


@pytest.mark.django_db
def test_patch_quiz_requires_authentication(api_client, user):
    """
    Unauthenticated requests should get 401.
    """
    # Arrange: create a quiz
    quiz = Quiz.objects.create(
        user=user,
        title='Original Title',
        description='Quiz Description',
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    )

    # Act: no auth cookie set
    url = reverse('quiz-detail', kwargs={'pk': quiz.id})
    res = api_client.patch(url, data={'title': 'X'}, format='json')

    # Assert
    assert res.status_code == 401


@pytest.mark.django_db
def test_patch_quiz_forbidden_for_non_owner(api_client, user, other_user):
    """
    A different authenticated user must receive 403 when trying to patch someone else's quiz.
    """
    # Arrange: quiz belongs to 'other_user'
    quiz = Quiz.objects.create(
        user=other_user,
        title='Original Title',
        description='Quiz Description',
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    )

    # Authenticate as 'user' (not owner)
    auth_with_cookie(api_client, user)

    # Act
    url = reverse('quiz-detail', kwargs={'pk': quiz.id})
    res = api_client.patch(url, data={'title': 'Hacked'}, format='json')

    # Assert
    assert res.status_code == 403


@pytest.mark.django_db
def test_patch_quiz_rejects_unknown_fields(api_client, user):
    """
    Sending fields that are not allowed by the write-serializer should yield 400.
    """
    quiz = Quiz.objects.create(
        user=user,
        title='Original Title',
        description='Quiz Description',
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    )
    auth_with_cookie(api_client, user)

    url = reverse('quiz-detail', kwargs={'pk': quiz.id})
    # 'video_url' and 'questions' are not writable via partial update
    res = api_client.patch(url, data={
        'video_url': 'https://youtu.be/NEWID',
        'questions': [{'id': 999}]
    }, format='json')

    assert res.status_code == 400
