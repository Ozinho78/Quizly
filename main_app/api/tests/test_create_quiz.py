from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User


def authenticate_client(client: APIClient, user: User):
    """Creates JWTs for user and sets them as cookies on the test client"""
    refresh = RefreshToken.for_user(user)
    access = refresh.access_token
    client.cookies['access_token'] = str(access)
    client.cookies['refresh_token'] = str(refresh)


def test_create_quiz_success(monkeypatch, db):
    """Happy path: endpoint returns 201 and the expected schema."""
    user = User.objects.create_user(username='u1', password='pw')
    client = APIClient()
    authenticate_client(client, user)
    
    def fake_download(url, workdir):
        return workdir / 'audio.wav'

    def fake_transcribe(path):
        return 'short transcript about climate change and causes'

    def fake_generate(transcript):
        return {
            'title': 'Quiz Title',
            'description': 'Quiz Description',
            'questions': [
                {
                    'question_title': f'Question {i+1}',
                    'options': ['Option A', 'Option B', 'Option C', 'Option D'],
                    'answer': 'Option A',
                }
                for i in range(10)
        ],
        }

    from main_app.services import pipeline
    monkeypatch.setattr(pipeline, 'download_audio_from_youtube', fake_download)
    monkeypatch.setattr(pipeline, 'transcribe_audio_with_whisper', fake_transcribe)
    monkeypatch.setattr(pipeline, 'generate_quiz_with_gemini', fake_generate)
    url = reverse('create-quiz')
    resp = client.post(url, data={'url': 'https://www.youtube.com/watch?v=abc123'}, format='json')
    assert resp.status_code == 201
    data = resp.json()
    assert data['title'] == 'Quiz Title'
    assert data['video_url'] == 'https://www.youtube.com/watch?v=abc123'
    assert len(data['questions']) == 10
    assert len(data['questions'][0]['question_options']) == 4


def test_create_quiz_requires_auth(db):
    """Without cookies the endpoint should return 401"""
    client = APIClient()
    url = reverse('create-quiz')
    resp = client.post(url, data={'url': 'https://youtu.be/xyz'}, format='json')
    assert resp.status_code == 401


def test_create_quiz_validates_url(db):
    """Non-YouTube URLs should be rejected with 400"""
    user = User.objects.create_user(username='u2', password='pw')
    client = APIClient()
    authenticate_client(client, user)
    url = reverse('create-quiz')
    resp = client.post(url, data={'url': 'https://example.com/video.mp4'}, format='json')
    assert resp.status_code == 400