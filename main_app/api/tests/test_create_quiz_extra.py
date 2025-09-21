import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from main_app.models import Quiz, Question
from main_app.services import pipeline


def authenticate_client(client, user):
    """Helper that sets JWT cookies on the DRF test client."""
    refresh = RefreshToken.for_user(user)
    client.cookies['access_token'] = str(refresh.access_token)
    client.cookies['refresh_token'] = str(refresh)


@pytest.mark.django_db
def test_create_quiz_idempotent_returns_existing_quiz(monkeypatch):
    """If a quiz with the same video_url already exists, the view returns it with 200 and does not call the pipeline."""
    # Arrange: an authenticated client
    user = User.objects.create_user(username='u_idem', password='pw')
    client = APIClient()
    authenticate_client(client, user)

    # Prepare an existing quiz (NOW with same owner!)
    quiz = Quiz.objects.create(
        user=user,  # <-- important: non-null and idempotency is per user
        title='Existing',
        description='D',
        video_url='https://youtu.be/idem123'
    )
    Question.objects.create(
        quiz=quiz,
        question_title='Q1',
        question_options=['A', 'B', 'C', 'D'],
        answer='A',
    )

    # Make sure pipeline would raise if called (so we know the idempotent branch is taken)
    def should_not_be_called(*args, **kwargs):
        raise AssertionError('Pipeline should not be called for existing quizzes.')

    monkeypatch.setattr(pipeline, 'download_audio_from_youtube', should_not_be_called)
    monkeypatch.setattr(pipeline, 'transcribe_audio_with_whisper', should_not_be_called)
    monkeypatch.setattr(pipeline, 'generate_quiz_with_gemini', should_not_be_called)

    # Act
    url = reverse('create-quiz')
    resp = client.post(url, data={'url': 'https://youtu.be/idem123'}, format='json')

    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data['id'] == quiz.id
    assert data['video_url'] == 'https://youtu.be/idem123'
    assert len(data['questions']) == 1


@pytest.mark.django_db
def test_create_quiz_pipeline_error_bubbles_as_500(monkeypatch):
    """Known pipeline errors should map to 500 with a readable message."""
    user = User.objects.create_user(username='u_err', password='pw')
    client = APIClient()
    authenticate_client(client, user)

    # Force the pipeline to raise the domain-specific error
    from main_app.services.pipeline import QuizPipelineError
    def raise_known(_):
        raise QuizPipelineError('Gemini returned unexpected format (no JSON).')

    monkeypatch.setattr(pipeline, 'download_audio_from_youtube', lambda u, w: w/'audio.wav')
    monkeypatch.setattr(pipeline, 'transcribe_audio_with_whisper', lambda p: 'text')
    monkeypatch.setattr(pipeline, 'generate_quiz_with_gemini', raise_known)

    url = reverse('create-quiz')
    resp = client.post(url, data={'url': 'https://www.youtube.com/watch?v=abc'}, format='json')

    assert resp.status_code == 500
    assert resp.json()['detail'] == 'Gemini returned unexpected format (no JSON).'


@pytest.mark.django_db
def test_create_quiz_unexpected_exception_returns_generic_500(monkeypatch):
    """Unexpected exceptions should map to a generic 500 detail."""
    user = User.objects.create_user(username='u_unexp', password='pw')
    client = APIClient()
    authenticate_client(client, user)

    def boom(*args, **kwargs):
        raise RuntimeError('disk failure')

    monkeypatch.setattr(pipeline, 'download_audio_from_youtube', boom)

    url = reverse('create-quiz')
    resp = client.post(url, data={'url': 'https://www.youtube.com/watch?v=abc'}, format='json')

    assert resp.status_code == 500
    assert resp.json()['detail'] == 'Internal server error.'
