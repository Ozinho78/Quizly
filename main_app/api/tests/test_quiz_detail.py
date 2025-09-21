import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings

from main_app.models import Quiz, Question

def _issue_access_cookie(client, user):
    """
    Issue a valid JWT access token for the given user and set it
    on the Django test client using the HttpOnly cookie name from settings.
    """
    # Create a fresh token pair for the user
    refresh = RefreshToken.for_user(user)                      # new refresh token
    access = str(refresh.access_token)                         # corresponding access token

    # Use the same cookie name as in app code (default: 'access_token')
    cookie_name = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')

    # Set cookie on the test client (httponly behavior is not enforced in tests)
    client.cookies[cookie_name] = access                       # attach JWT like the frontend would

@pytest.mark.django_db
class TestQuizDetailEndpoint:
    """
    Tests for GET /api/quizzes/{id}
    Ensures that:
      - the owner gets 200 and full quiz payload
      - 404 for non-existent quiz
      - 403 when accessing someone else's quiz
      - 401 for unauthenticated requests
    """

    def setup_method(self):
        """Create users, a quiz and one question to work with."""
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='demo', password='pass1234')   # quiz owner
        self.other = User.objects.create_user(username='other', password='pass1234') # different user

        self.quiz = Quiz.objects.create(                                             # owner's quiz
            user=self.user,
            title='Test Quiz',
            description='Desc',
            video_url='https://youtu.be/example',
        )

        Question.objects.create(                                                     # a sample question
            quiz=self.quiz,
            question_title='Q1',
            question_options=['A', 'B', 'C', 'D'],
            answer='A',
        )

    def test_quiz_detail_success(self, client):
        """Owner can retrieve their quiz (200) when JWT cookie is present."""
        _issue_access_cookie(client, self.user)                                      # set JWT cookie
        url = reverse('quiz-detail', args=[self.quiz.id])                            # build URL
        resp = client.get(url)                                                       # call endpoint
        assert resp.status_code == status.HTTP_200_OK                                # must be 200
        data = resp.json()                                                           # parse JSON
        assert data['id'] == self.quiz.id                                            # correct quiz
        assert data['title'] == 'Test Quiz'                                          # fields preserved
        assert len(data['questions']) == 1                                           # nested questions
        assert data['questions'][0]['answer'] == 'A'                                 # payload shape

    def test_quiz_detail_not_found(self, client):
        """Requesting a non-existing quiz returns 404."""
        _issue_access_cookie(client, self.user)                                      # auth set
        url = reverse('quiz-detail', args=[999999])                                  # nonexistent id
        resp = client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_quiz_detail_forbidden(self, client):
        """Accessing someone else's quiz returns 403."""
        _issue_access_cookie(client, self.other)                                     # other user auth
        url = reverse('quiz-detail', args=[self.quiz.id])
        resp = client.get(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_quiz_detail_unauthenticated(self, client):
        """Missing JWT cookie results in 401."""
        url = reverse('quiz-detail', args=[self.quiz.id])                            # no cookie set
        resp = client.get(url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
