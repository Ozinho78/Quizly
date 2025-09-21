# tests/test_quizzes_delete.py
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
    # Create and return a reusable API client for tests
    return APIClient()  # basic client without default auth; we'll set cookies per test as needed


@pytest.fixture
def user(db):
    """
    Create and return a user for authentication in tests.
    """
    # Get the configured User model
    User = get_user_model()  # obtain the Django User model
    # Create a standard user for ownership tests
    return User.objects.create_user(username='alice', email='alice@example.com', password='pw123456')  # persist user


@pytest.fixture
def other_user(db):
    """
    Create and return another user to test forbidden access.
    """
    # Get the configured User model
    User = get_user_model()  # obtain the Django User model
    # Create a second user; will own resources the first user must not delete
    return User.objects.create_user(username='bob', email='bob@example.com', password='pw123456')  # persist user


def auth_with_cookie(client: APIClient, user):
    """
    Helper: issue an access token for 'user' and set it as HttpOnly cookie on the client.
    Cookie name should match your CookieJWTAuthentication setup ('access_token').
    """
    # Create a short-lived access token bound to the given user
    token = AccessToken.for_user(user)  # issue JWT access token
    # Attach token as if it were an HttpOnly cookie from the server
    client.cookies['access_token'] = str(token)  # simulate cookie-based JWT auth


@pytest.mark.django_db
def test_delete_quiz_success_returns_204_and_removes_related_questions(api_client, user):
    """
    Owner deletes their quiz -> expect 204 and quiz/questions removed from DB.
    """
    # Arrange: create a quiz owned by 'user'
    quiz = Quiz.objects.create(
        user=user,  # set owner
        title='To be deleted',  # initial title
        description='Temporary quiz',  # any description
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',  # placeholder url
    )  # persist quiz

    # Add multiple questions to ensure cascade deletion is exercised
    Question.objects.create(
        quiz=quiz,  # link to quiz
        question_title='Q1',  # simple title
        question_options=['A', 'B', 'C', 'D'],  # 4 options
        answer='A',  # correct answer
    )  # persist question
    Question.objects.create(
        quiz=quiz,  # link to quiz
        question_title='Q2',  # another title
        question_options=['A', 'B', 'C', 'D'],  # 4 options
        answer='B',  # correct answer
    )  # persist question

    # Authenticate via JWT cookie
    auth_with_cookie(api_client, user)  # set access_token cookie

    # Act: send DELETE to the detail endpoint
    url = reverse('quiz-detail', kwargs={'pk': quiz.id})  # build detail url
    res = api_client.delete(url)  # perform DELETE request

    # Assert: proper status code
    assert res.status_code == 204  # no content expected

    # Assert: quiz removed from DB
    assert not Quiz.objects.filter(id=quiz.id).exists()  # quiz must not exist anymore

    # Assert: related questions removed (cascade)
    assert Question.objects.filter(quiz_id=quiz.id).count() == 0  # zero related rows expected


@pytest.mark.django_db
def test_delete_quiz_requires_authentication(api_client, user):
    """
    Unauthenticated deletion attempts must yield 401.
    """
    # Arrange: create a quiz owned by 'user'
    quiz = Quiz.objects.create(
        user=user,  # owner
        title='No Auth',  # title
        description='Auth required',  # description
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',  # placeholder
    )  # persist quiz

    # Act: perform DELETE without cookie
    url = reverse('quiz-detail', kwargs={'pk': quiz.id})  # build url
    res = api_client.delete(url)  # send request without auth

    # Assert: must be unauthorized
    assert res.status_code == 401  # auth required


@pytest.mark.django_db
def test_delete_quiz_forbidden_for_non_owner(api_client, user, other_user):
    """
    Authenticated user who is NOT the owner must receive 403.
    """
    # Arrange: quiz belongs to 'other_user'
    quiz = Quiz.objects.create(
        user=other_user,  # not the requester
        title='Foreign Quiz',  # title
        description='Owned by someone else',  # description
        video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',  # placeholder
    )  # persist quiz

    # Authenticate as 'user' (not owner)
    auth_with_cookie(api_client, user)  # set cookie for different user

    # Act: try deleting someone else's quiz
    url = reverse('quiz-detail', kwargs={'pk': quiz.id})  # detail url
    res = api_client.delete(url)  # DELETE request

    # Assert: forbidden
    assert res.status_code == 403  # no permission to delete foreign resources

    # And object should still exist
    assert Quiz.objects.filter(id=quiz.id).exists()  # quiz must remain


@pytest.mark.django_db
def test_delete_quiz_404_when_not_found(api_client, user):
    """
    Deleting a non-existent quiz should return 404.
    """
    # Authenticate as valid user
    auth_with_cookie(api_client, user)  # set JWT cookie

    # Act: DELETE a very high id that does not exist
    url = reverse('quiz-detail', kwargs={'pk': 999999})  # id not present
    res = api_client.delete(url)  # perform request

    # Assert: not found
    assert res.status_code == 404  # resource missing
