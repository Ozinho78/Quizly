# -*- coding: utf-8 -*-
import json
import types
from pathlib import Path
import pytest

from main_app.services import pipeline


def test_download_audio_success(tmp_path, monkeypatch):
    """Ensures yt-dlp and ffmpeg happy path returns a WAV path."""

    call_order = {'n': 0}  # track calls

    def fake_run(cmd, stdout=None, stderr=None):
        # 1st call: yt-dlp, 2nd call: ffmpeg
        call_order['n'] += 1
        return types.SimpleNamespace(returncode=0)

    # Patch subprocess.run in pipeline
    monkeypatch.setattr(pipeline.subprocess, 'run', fake_run)

    wav = pipeline.download_audio_from_youtube('https://youtu.be/abc', tmp_path)
    assert wav.name == 'audio.wav'
    assert call_order['n'] == 2  # yt-dlp + ffmpeg


def test_download_audio_yt_dlp_fail(tmp_path, monkeypatch):
    """If yt-dlp fails, raise QuizPipelineError."""

    def fake_run(cmd, stdout=None, stderr=None):
        return types.SimpleNamespace(returncode=1)  # fail immediately

    monkeypatch.setattr(pipeline.subprocess, 'run', fake_run)

    with pytest.raises(pipeline.QuizPipelineError):
        pipeline.download_audio_from_youtube('https://youtu.be/abc', tmp_path)


def test_download_audio_ffmpeg_fail(tmp_path, monkeypatch):
    """If ffmpeg conversion fails, raise QuizPipelineError."""

    def fake_run(cmd, stdout=None, stderr=None):
        # first ok (yt-dlp), second fail (ffmpeg)
        if 'yt-dlp' in cmd[0]:
            return types.SimpleNamespace(returncode=0)
        return types.SimpleNamespace(returncode=2)

    monkeypatch.setattr(pipeline.subprocess, 'run', fake_run)

    with pytest.raises(pipeline.QuizPipelineError):
        pipeline.download_audio_from_youtube('https://youtu.be/abc', tmp_path)


def test_transcribe_whisper_success(tmp_path, monkeypatch):
    """Whisper returns non-empty text."""

    class FakeModel:
        def transcribe(self, p):
            return {'text': 'hello world'}

    monkeypatch.setattr(pipeline.whisper, 'load_model', lambda name: FakeModel())

    text = pipeline.transcribe_audio_with_whisper(tmp_path / 'audio.wav')
    assert text == 'hello world'


def test_transcribe_whisper_empty(tmp_path, monkeypatch):
    """Empty transcript triggers QuizPipelineError."""

    class FakeModel:
        def transcribe(self, p):
            return {'text': ''}

    monkeypatch.setattr(pipeline.whisper, 'load_model', lambda name: FakeModel())

    with pytest.raises(pipeline.QuizPipelineError):
        pipeline.transcribe_audio_with_whisper(tmp_path / 'audio.wav')


def test_generate_quiz_missing_pkg(monkeypatch):
    """If google-generativeai is not installed, raise QuizPipelineError."""
    monkeypatch.setattr(pipeline, 'genai', None)
    with pytest.raises(pipeline.QuizPipelineError):
        pipeline.generate_quiz_with_gemini('text')


def test_generate_quiz_malformed_json(monkeypatch):
    """Non-JSON response should raise QuizPipelineError."""
    monkeypatch.setenv('GEMINI_API_KEY', 'x')

    class FakeResp:
        text = 'not-json-response'

    class FakeModel:
        def __init__(self, name): pass
        def generate_content(self, parts): return FakeResp()

    class FakeGenAI:
        def configure(self, api_key=None): pass
        GenerativeModel = FakeModel

    monkeypatch.setattr(pipeline, 'genai', FakeGenAI())

    with pytest.raises(pipeline.QuizPipelineError):
        pipeline.generate_quiz_with_gemini('text')


def test_generate_quiz_success(monkeypatch):
    """Valid strict JSON with 10×4 MCQ returns payload."""

    monkeypatch.setenv('GEMINI_API_KEY', 'x')

    payload = {
        'title': 'Quiz Title',
        'description': 'Quiz Description',
        'questions': [
            {
                'question_title': f'Q{i+1}',
                'options': ['A','B','C','D'],
                'answer': 'A'
            } for i in range(10)
        ]
    }

    class FakeResp:
        # simulate pure JSON text
        text = json.dumps(payload)

    class FakeModel:
        def __init__(self, name): pass
        def generate_content(self, parts): return FakeResp()

    class FakeGenAI:
        def configure(self, api_key=None): pass
        GenerativeModel = FakeModel

    monkeypatch.setattr(pipeline, 'genai', FakeGenAI())

    out = pipeline.generate_quiz_with_gemini('some transcript')
    assert out['title'] == 'Quiz Title'
    assert len(out['questions']) == 10
    assert len(out['questions'][0]['options']) == 4
