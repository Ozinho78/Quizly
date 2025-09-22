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
    """Creates and return another user to test forbidden access"""
    User = get_user_model()
    return User.objects.create_user(username='bob', email='bob@example.com', password='pw123456')


def auth_with_cookie(client: APIClient, user):
    """Issues an access token for 'user' and set it as HttpOnly cookie on the client"""
    token = AccessToken.for_user(user)
    client.cookies['access_token'] = str(token)


@pytest.mark.django_db
def test_delete_quiz_success_returns_204_and_removes_related_questions(api_client, user):
    """Owner deletes their quiz, expect 204 and quiz/questions removed from DB"""
    quiz = Quiz.objects.create(
        user=user,
        title='To be deleted',
        description='Temporary quiz',
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    )
    Question.objects.create(
        quiz=quiz,
        question_title='Q1',
        question_options=['A', 'B', 'C', 'D'],
        answer='A',
    )
    Question.objects.create(
        quiz=quiz,
        question_title='Q2',
        question_options=['A', 'B', 'C', 'D'],
        answer='B',
    )
    auth_with_cookie(api_client, user)
    url = reverse('quiz-detail', kwargs={'pk': quiz.id})
    res = api_client.delete(url)
    assert res.status_code == 204
    assert not Quiz.objects.filter(id=quiz.id).exists()
    assert Question.objects.filter(quiz_id=quiz.id).count() == 0


@pytest.mark.django_db
def test_delete_quiz_requires_authentication(api_client, user):
    """Unauthenticated deletion attempts must throw 401"""
    quiz = Quiz.objects.create(
        user=user,
        title='No Auth',
        description='Auth required',
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    )
    url = reverse('quiz-detail', kwargs={'pk': quiz.id})
    res = api_client.delete(url)
    assert res.status_code == 401


@pytest.mark.django_db
def test_delete_quiz_forbidden_for_non_owner(api_client, user, other_user):
    """Authenticated user who is NOT the owner must receive 403"""
    quiz = Quiz.objects.create(
        user=other_user,
        title='Foreign Quiz',
        description='Owned by someone else',
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    )
    auth_with_cookie(api_client, user)
    url = reverse('quiz-detail', kwargs={'pk': quiz.id})
    res = api_client.delete(url)
    assert res.status_code == 403
    assert Quiz.objects.filter(id=quiz.id).exists()


@pytest.mark.django_db
def test_delete_quiz_404_when_not_found(api_client, user):
    """Deleting a non-existent quiz should return 404"""
    auth_with_cookie(api_client, user)
    url = reverse('quiz-detail', kwargs={'pk': 999999})
    res = api_client.delete(url)
    assert res.status_code == 404