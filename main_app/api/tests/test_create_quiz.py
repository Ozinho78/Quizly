import json # to build request payloads
import types # to create simple stub types
from django.urls import reverse # to resolve route names
from rest_framework.test import APIClient # DRF test client
from rest_framework_simplejwt.tokens import RefreshToken # to mint cookies
from django.contrib.auth.models import User # create a test user


# Helper to log in the client by setting HttpOnly-like cookies in tests
def authenticate_client(client: APIClient, user: User):
    """Create JWTs for user and set them as cookies on the test client."""
    refresh = RefreshToken.for_user(user) # create refresh
    access = refresh.access_token # derive access
    client.cookies['access_token'] = str(access) # set cookie expected by CookieJWTAuthentication
    client.cookies['refresh_token'] = str(refresh) # not used by the endpoint but mirrors real flow


def test_create_quiz_success(monkeypatch, db):
    """Happy path: endpoint returns 201 and the expected schema."""
    # Arrange: user and auth
    user = User.objects.create_user(username='u1', password='pw') # create user
    client = APIClient() # test client
    authenticate_client(client, user) # set cookies
    
    # Stub pipeline functions to avoid heavy I/O
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

    # Patch the service functions
    from main_app import services
    from main_app.services import pipeline
    monkeypatch.setattr(pipeline, 'download_audio_from_youtube', fake_download)
    monkeypatch.setattr(pipeline, 'transcribe_audio_with_whisper', fake_transcribe)
    monkeypatch.setattr(pipeline, 'generate_quiz_with_gemini', fake_generate)

    # Act: call the endpoint
    url = reverse('create-quiz') # resolves to /api/createQuiz/
    resp = client.post(url, data={'url': 'https://www.youtube.com/watch?v=abc123'}, format='json')

    # Assert: status and minimal schema
    assert resp.status_code == 201
    data = resp.json()
    assert data['title'] == 'Quiz Title'
    assert data['video_url'] == 'https://www.youtube.com/watch?v=abc123'
    assert len(data['questions']) == 10
    assert len(data['questions'][0]['question_options']) == 4


def test_create_quiz_requires_auth(db):
    """Without cookies the endpoint should return 401."""
    client = APIClient() # no auth
    url = reverse('create-quiz')
    resp = client.post(url, data={'url': 'https://youtu.be/xyz'}, format='json')
    assert resp.status_code == 401 # permission denied


def test_create_quiz_validates_url(db):
    """Non-YouTube URLs should be rejected with 400."""
    # authenticate
    user = User.objects.create_user(username='u2', password='pw')
    client = APIClient()
    authenticate_client(client, user)

    # call with invalid URL
    url = reverse('create-quiz')
    resp = client.post(url, data={'url': 'https://example.com/video.mp4'}, format='json')
    assert resp.status_code == 400 # bad request