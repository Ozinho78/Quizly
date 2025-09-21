import os
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict
import whisper

try:
    import google.generativeai as genai
except Exception:
    genai = None
    
    
def _normalize_text(s: str) -> str:
    """Returns a normalized version of a string for tolerant comparisons"""
    import re
    if not isinstance(s, str):
        return ''
    t = s.strip().lower()
    t = re.sub(r"[\\s\\.,;:!?'\"`]+$", '', t)
    return t


def _answer_index_from_token(ans: str):
    """Tries to interpret the answer as an index token like 'A', 'B', '1', 'option C'"""
    a = _normalize_text(ans)
    mapping = {
        ('a', '1', 'option a', 'a)', '(a)', 'a.', 'answera'): 0,
        ('b', '2', 'option b', 'b)', '(b)', 'b.', 'answerb'): 1,
        ('c', '3', 'option c', 'c)', '(c)', 'c.', 'answerc'): 2,
        ('d', '4', 'option d', 'd)', '(d)', 'd.', 'answerd'): 3,
    }
    for keys, idx in mapping.items():
        if a in keys:
            return idx
    return None


def _repair_quiz_payload(payload: dict) -> dict:
    """Attempts to auto-repair common model output issues"""
    import logging
    logger = logging.getLogger(__name__)
    questions = payload.get('questions', [])
    for i, q in enumerate(questions):
        opts = q.get('options') or []
        ans = q.get('answer', '')
        if ans in opts:
            continue

        idx = _answer_index_from_token(ans)
        if idx is not None and 0 <= idx < len(opts):
            q['answer'] = opts[idx]
            logger.info('Repaired answer by index mapping at question %s.', i + 1)
            continue
        
        norm_ans = _normalize_text(ans)
        repaired = False
        for opt in opts:
            if _normalize_text(opt) == norm_ans:
                q['answer'] = opt
                logger.info('Repaired answer by normalized match at question %s.', i + 1)
                repaired = True
                break

        if not repaired:
            logger.warning('Could not repair answer mismatch at question %s.', i + 1)

    return payload
    
    
class QuizPipelineError(Exception):
    """Raised for any pipeline-related failure to unify error handling"""
    pass
  
  
def download_audio_from_youtube(url: str, workdir: Path) -> Path:
    """Downloads a video's audio track using yt-dlp and convert to WAV via ffmpeg.
    Returns the path to a mono 16kHz WAV file suitable for Whisper.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    m4a_path = workdir / 'audio.m4a'
    wav_path = workdir / 'audio.wav'
    ytdlp_cmd = [
        'yt-dlp',
        '-f', 'bestaudio',
        '-o', str(m4a_path),
        url,
    ]
    res = subprocess.run(ytdlp_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise QuizPipelineError('Failed to download audio with yt-dlp.')

    ffmpeg_cmd = [
        'ffmpeg',
        '-y',
        '-i', str(m4a_path),
        '-ac', '1',
        '-ar', '16000',
        str(wav_path),
    ]
    res2 = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res2.returncode != 0:
        raise QuizPipelineError('Failed to convert audio with ffmpeg.')
    return wav_path


def transcribe_audio_with_whisper(wav_path: Path, model_name: str = 'base') -> str:
    """Transcribes the given WAV file using a local Whisper model"""
    model = whisper.load_model(model_name)
    result = model.transcribe(str(wav_path))
    text = result.get('text', '').strip()
    if not text:
        raise QuizPipelineError('Whisper returned empty transcript.')
    return text
  
  
def _ensure_genai_configured() -> None:
    """Initializes the Gemini client with API key from environment"""
    if genai is None:
        raise QuizPipelineError('google-generativeai package not installed.')
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise QuizPipelineError('GEMINI_API_KEY environment variable is missing.')
    genai.configure(api_key=api_key)


def generate_quiz_with_gemini(transcript: str) -> Dict[str, List[Dict[str, str]]]:
    """Asks Gemini 1.5 Flash to write 10 multiple-choice questions in strict JSON"""
    _ensure_genai_configured()
    generation_config = {
        'response_mime_type': 'application/json',
        'temperature': 0.3,
    }
    try:
        model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)
    except TypeError:
        model = genai.GenerativeModel('gemini-1.5-flash')

    system_prompt = (
        'You are a quiz generator. Create exactly 10 multiple-choice questions (4 options each)\n'
        'based ONLY on the provided transcript. Include a short title and description.\n'
        'Return STRICT JSON with keys: title, description, questions. Each question must have\n'
        'question_title, options (list of 4 strings), and answer (one of options). No extra text.'
    )

    response = model.generate_content([system_prompt, transcript[:15000]])
    import logging
    logger = logging.getLogger(__name__)
    logger.info('Gemini raw (first 600 chars): %s', (response.text or '')[:600])

    import json
    text = response.text or ''
    try:
        payload = json.loads(text)
    except Exception as e:
        payload = _parse_json_loose(text)
        
    payload = _repair_quiz_payload(payload)
    if 'questions' not in payload or len(payload['questions']) != 10:
        raise QuizPipelineError('Model did not produce exactly 10 questions.')
    for q in payload['questions']:
        opts = q.get('options', [])
        if len(opts) != 4:
            raise QuizPipelineError('Each question must have 4 options.')
        if q.get('answer') not in opts:
            raise QuizPipelineError('Answer must be one of the options.')
    return payload


def _parse_json_loose(text: str) -> dict:
    """Tries several strategies to extract JSON from a model response"""
    import json, re
    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text, flags=re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    s, e = text.find('{'), text.rfind('}')
    while s != -1 and e != -1 and e >= s:
        try:
            return json.loads(text[s:e+1])
        except Exception:
            e = text.rfind('}', 0, e)
    raise QuizPipelineError('Gemini returned unexpected format (no JSON).')