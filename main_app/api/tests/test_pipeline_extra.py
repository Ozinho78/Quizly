import os
import json
import pytest
import types
import subprocess
from pathlib import Path
from main_app.services.pipeline import (
    download_audio_from_youtube,
    transcribe_audio_with_whisper,
    generate_quiz_with_gemini,
    QuizPipelineError,
)
import main_app.services.pipeline as pipeline_mod

# ---------- download_audio_from_youtube ----------

def _dummy_completed(returncode=0):
    c = types.SimpleNamespace()
    c.returncode = returncode
    c.stdout = b''
    c.stderr = b''
    return c

def test_download_audio_success(monkeypatch, tmp_path):
    """Simulate successful yt-dlp and ffmpeg runs."""
    calls = []

    def fake_run(cmd, stdout=None, stderr=None):
        calls.append(cmd)
        # First call is yt-dlp, second is ffmpeg
        if 'yt-dlp' in cmd[0]:
            return _dummy_completed(0)
        if 'ffmpeg' in cmd[0]:
            return _dummy_completed(0)
        return _dummy_completed(0)

    monkeypatch.setattr(subprocess, 'run', fake_run)
    wav = download_audio_from_youtube('https://youtu.be/x', tmp_path)
    assert wav.name.endswith('.wav')
    assert any('yt-dlp' in c[0] for c in calls)
    assert any('ffmpeg' in c[0] for c in calls)

def test_download_audio_ytdlp_fail(monkeypatch, tmp_path):
    """If yt-dlp fails, raise QuizPipelineError."""
    def fake_run(cmd, stdout=None, stderr=None):
        if 'yt-dlp' in cmd[0]:
            return _dummy_completed(1)
        return _dummy_completed(0)

    monkeypatch.setattr(subprocess, 'run', fake_run)
    with pytest.raises(QuizPipelineError):
        download_audio_from_youtube('https://youtu.be/x', tmp_path)

def test_download_audio_ffmpeg_fail(monkeypatch, tmp_path):
    """If ffmpeg fails, raise QuizPipelineError."""
    state = {'first': True}
    def fake_run(cmd, stdout=None, stderr=None):
        # first call yt-dlp ok, second call ffmpeg fails
        if state['first']:
            state['first'] = False
            return _dummy_completed(0)
        return _dummy_completed(1)

    monkeypatch.setattr(subprocess, 'run', fake_run)
    with pytest.raises(QuizPipelineError):
        download_audio_from_youtube('https://youtu.be/x', tmp_path)

# ---------- transcribe_audio_with_whisper ----------

def test_transcribe_whisper_success(monkeypatch, tmp_path):
    """Whisper returns text dictionary."""
    class DummyModel:
        def transcribe(self, path):
            return {'text': 'hello world'}
    monkeypatch.setattr(pipeline_mod.whisper, 'load_model', lambda n: DummyModel())
    text = transcribe_audio_with_whisper(tmp_path/'a.wav', model_name='base')
    assert text == 'hello world'

def test_transcribe_whisper_empty(monkeypatch, tmp_path):
    """Whisper returns empty text -> error."""
    class DummyModel:
        def transcribe(self, path):
            return {'text': '   '}
    monkeypatch.setattr(pipeline_mod.whisper, 'load_model', lambda n: DummyModel())
    with pytest.raises(QuizPipelineError):
        transcribe_audio_with_whisper(tmp_path/'a.wav')

# ---------- generate_quiz_with_gemini ----------

def _stub_genai_with_text(text):
    """Helper to stub google.generativeai returning a specific text."""
    class DummyResp:
        def __init__(self, t): self.text = t
    class DummyModel:
        def __init__(self, name): pass
        def generate_content(self, parts): return DummyResp(text)
    class DummyGenAI:
        def configure(self, api_key=None): pass
        GenerativeModel = DummyModel
    return DummyGenAI()

def test_generate_quiz_success(monkeypatch):
    """Happy path with strict 10 questions and 4 options each."""
    payload = {
        'title': 'T',
        'description': 'D',
        'questions': [
            {'question_title': f'Q{i+1}', 'options': ['A','B','C','D'], 'answer': 'A'}
            for i in range(10)
        ]
    }
    monkeypatch.setenv('GEMINI_API_KEY', 'x')
    monkeypatch.setattr(pipeline_mod, 'genai', _stub_genai_with_text(json.dumps(payload)))
    out = generate_quiz_with_gemini('some transcript')
    assert out['title'] == 'T'
    assert len(out['questions']) == 10
    assert len(out['questions'][0]['options']) == 4

def test_generate_quiz_missing_key(monkeypatch):
    """Missing GEMINI_API_KEY should raise QuizPipelineError."""
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    # genai exists but key missing -> still error
    monkeypatch.setattr(pipeline_mod, 'genai', _stub_genai_with_text('{}'))
    with pytest.raises(QuizPipelineError):
        generate_quiz_with_gemini('t')

def test_generate_quiz_bad_json(monkeypatch):
    """Non-JSON response should error."""
    monkeypatch.setenv('GEMINI_API_KEY', 'x')
    monkeypatch.setattr(pipeline_mod, 'genai', _stub_genai_with_text('not json at all'))
    with pytest.raises(QuizPipelineError):
        generate_quiz_with_gemini('t')

def test_generate_quiz_wrong_count(monkeypatch):
    """Model must produce exactly 10 questions."""
    payload = {'title':'T','description':'D','questions':[{'question_title':'Q1','options':['A','B','C','D'],'answer':'A'}]}
    monkeypatch.setenv('GEMINI_API_KEY', 'x')
    monkeypatch.setattr(pipeline_mod, 'genai', _stub_genai_with_text(json.dumps(payload)))
    with pytest.raises(QuizPipelineError):
        generate_quiz_with_gemini('t')

def test_generate_quiz_bad_options_len(monkeypatch):
    """Each question must have exactly 4 options."""
    payload = {'title':'T','description':'D','questions':[{'question_title':'Q1','options':['A','B','C'],'answer':'A'}]*10}
    monkeypatch.setenv('GEMINI_API_KEY', 'x')
    monkeypatch.setattr(pipeline_mod, 'genai', _stub_genai_with_text(json.dumps(payload)))
    with pytest.raises(QuizPipelineError):
        generate_quiz_with_gemini('t')

def test_generate_quiz_answer_not_in_options(monkeypatch):
    """Answer must be contained in options."""
    payload = {'title':'T','description':'D','questions':[{'question_title':'Q1','options':['A','B','C','D'],'answer':'Z'}]*10}
    monkeypatch.setenv('GEMINI_API_KEY', 'x')
    monkeypatch.setattr(pipeline_mod, 'genai', _stub_genai_with_text(json.dumps(payload)))
    with pytest.raises(QuizPipelineError):
        generate_quiz_with_gemini('t')
