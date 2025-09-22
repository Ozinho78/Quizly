import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from main_app.models import Quiz, Question


def _issue_access_cookie(client, user):
    """Issues a valid JWT access token for the given user and sets it on the Django test client"""
    refresh = RefreshToken.for_user(user)
    access = str(refresh.access_token)
    cookie_name = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')
    client.cookies[cookie_name] = access


@pytest.mark.django_db
class TestQuizDetailEndpoint:
    """Tests for GET /api/quizzes/{id}"""

    def setup_method(self):
        """Creates users, a quiz and one question to work with."""
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='demo', password='pass1234')
        self.other = User.objects.create_user(username='other', password='pass1234')

        self.quiz = Quiz.objects.create(
            user=self.user,
            title='Test Quiz',
            description='Desc',
            video_url='https://youtu.be/example',
        )

        Question.objects.create(
            quiz=self.quiz,
            question_title='Q1',
            question_options=['A', 'B', 'C', 'D'],
            answer='A',
        )

    def test_quiz_detail_success(self, client):
        """Owner can retrieve their quiz (200) when JWT cookie is present"""
        _issue_access_cookie(client, self.user)
        url = reverse('quiz-detail', args=[self.quiz.id])
        resp = client.get(url)                          
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()                           
        assert data['id'] == self.quiz.id            
        assert data['title'] == 'Test Quiz'          
        assert len(data['questions']) == 1           
        assert data['questions'][0]['answer'] == 'A' 

    def test_quiz_detail_not_found(self, client):
        """Requesting a non-existing quiz returns 404"""
        _issue_access_cookie(client, self.user)      
        url = reverse('quiz-detail', args=[999999])  
        resp = client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_quiz_detail_forbidden(self, client):
        """Accessing someone else's quiz returns 403"""
        _issue_access_cookie(client, self.other)
        url = reverse('quiz-detail', args=[self.quiz.id])
        resp = client.get(url)
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_quiz_detail_unauthenticated(self, client):
        """Missing JWT cookie results in 401"""
        url = reverse('quiz-detail', args=[self.quiz.id])
        resp = client.get(url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED