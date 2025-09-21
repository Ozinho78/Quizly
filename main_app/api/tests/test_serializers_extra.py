import pytest
from rest_framework import serializers
from main_app.api.serializers import QuizCreateSerializer

@pytest.mark.parametrize('url', [
    'https://www.youtube.com/watch?v=AAAA',
    'https://youtu.be/BBBB',
])
def test_quiz_create_serializer_accepts_youtube_urls(url):
    """Valid YouTube URLs should pass."""
    s = QuizCreateSerializer(data={'url': url})
    assert s.is_valid(), s.errors
    assert s.validated_data['url'] == url

@pytest.mark.parametrize('url', [
    'https://vimeo.com/123',
    'https://example.com',
    'ftp://youtube.com/watch?v=bad',
])
def test_quiz_create_serializer_rejects_non_youtube(url):
    """Non-YouTube URLs should be rejected with a validation error."""
    s = QuizCreateSerializer(data={'url': url})
    assert not s.is_valid()
    assert 'url' in s.errors
