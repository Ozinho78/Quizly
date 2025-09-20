import os # env vars for keys/paths
import tempfile # create safe temp dirs/files
import subprocess # invoke ffmpeg/yt-dlp CLIs
from pathlib import Path # path utils
from typing import List, Dict # type hints

# Whisper (openai-whisper) model loader
import whisper # local speech-to-text

# Gemini (google-generativeai) SDK
try:
    import google.generativeai as genai # official Gemini client
except Exception: # allow import to fail in unit tests without the package
    genai = None # type: ignore
    
    
def _normalize_text(s: str) -> str:
    """
    Return a normalized version of a string for tolerant comparisons.
    Lowercases, trims, and strips trailing punctuation.
    """
    import re  # local import to keep module scope tidy
    if not isinstance(s, str):  # guard non-strings
        return ''
    t = s.strip().lower()  # trim and lowercase
    t = re.sub(r"[\\s\\.,;:!?'\"`]+$", '', t)  # strip trailing punctuation/spaces
    return t  # normalized text


def _answer_index_from_token(ans: str):
    """
    Try to interpret the answer as an index token like 'A', 'B', '1', 'option C', etc.
    Returns an integer in [0..3] or None if it cannot be interpreted.
    """
    a = _normalize_text(ans)  # normalized
    mapping = {
        ('a', '1', 'option a', 'a)', '(a)', 'a.', 'answera'): 0,
        ('b', '2', 'option b', 'b)', '(b)', 'b.', 'answerb'): 1,
        ('c', '3', 'option c', 'c)', '(c)', 'c.', 'answerc'): 2,
        ('d', '4', 'option d', 'd)', '(d)', 'd.', 'answerd'): 3,
    }
    for keys, idx in mapping.items():
        if a in keys:
            return idx  # mapped to 0..3
    return None  # no mapping found


def _repair_quiz_payload(payload: dict) -> dict:
    """
    Attempt to auto-repair common model output issues:
      - 'answer' given as a letter/number instead of full option text
      - minor punctuation/case differences between 'answer' and an option
    Does NOT change the number of questions or options.
    """
    import logging  # local import for lightweight logging
    logger = logging.getLogger(__name__)  # module logger

    questions = payload.get('questions', [])  # list of questions
    for i, q in enumerate(questions):
        opts = q.get('options') or []  # safe list
        ans = q.get('answer', '')  # current answer
        # If already exact match, continue
        if ans in opts:
            continue  # nothing to do

        # 1) Try index/letter mapping
        idx = _answer_index_from_token(ans)  # map tokens like 'A' -> 0
        if idx is not None and 0 <= idx < len(opts):
            q['answer'] = opts[idx]  # set to the actual option string
            logger.info('Repaired answer by index mapping at question %s.', i + 1)
            continue  # repaired

        # 2) Try normalized text comparison
        norm_ans = _normalize_text(ans)  # normalized answer
        repaired = False  # track if repaired
        for opt in opts:
            if _normalize_text(opt) == norm_ans:  # tolerant match
                q['answer'] = opt  # adopt the canonical option text
                logger.info('Repaired answer by normalized match at question %s.', i + 1)
                repaired = True  # mark repaired
                break  # done for this question

        # If not repaired, leave as is; final validation will raise a clear error
        if not repaired:
            logger.warning('Could not repair answer mismatch at question %s.', i + 1)

    return payload  # possibly repaired
    
    
class QuizPipelineError(Exception):
    """Raised for any pipeline-related failure to unify error handling."""
    pass # acts as a domain-specific error type
  
  
def download_audio_from_youtube(url: str, workdir: Path) -> Path:
    """
    Download a video's audio track using yt-dlp and convert to WAV via ffmpeg.
    Returns the path to a mono 16kHz WAV file suitable for Whisper.
    """
    # ensure workdir exists
    workdir.mkdir(parents=True, exist_ok=True) # create folder if needed

    # choose an output file template for yt-dlp (we want an m4a or bestaudio)
    m4a_path = workdir / 'audio.m4a' # intermediate container
    wav_path = workdir / 'audio.wav' # final PCM WAV for ASR
    
    # use yt-dlp to fetch the best available audio-only stream
    ytdlp_cmd = [
        'yt-dlp', # command-line tool
        '-f', 'bestaudio', # best audio format
        '-o', str(m4a_path), # output path template
        url, # the YouTube URL
    ]
    # run yt-dlp; capture output for logging/debugging
    res = subprocess.run(ytdlp_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise QuizPipelineError('Failed to download audio with yt-dlp.') # bubble up concise error

    # convert to 16kHz mono WAV for Whisper (ffmpeg must be in PATH)
    ffmpeg_cmd = [
        'ffmpeg', # binary from PATH
        '-y', # overwrite without prompt
        '-i', str(m4a_path), # input file
        '-ac', '1', # mono channel
        '-ar', '16000', # sample rate 16k
        str(wav_path), # output wav
    ]
    res2 = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res2.returncode != 0:
        raise QuizPipelineError('Failed to convert audio with ffmpeg.') # error converting

    return wav_path # path for next stage


def transcribe_audio_with_whisper(wav_path: Path, model_name: str = 'base') -> str:
    """
    Transcribe the given WAV file using a local Whisper model.
    You can tweak model_name to 'small' or 'medium' if available.
    """
    model = whisper.load_model(model_name) # load the requested Whisper model
    result = model.transcribe(str(wav_path)) # run transcription on the audio file
    text = result.get('text', '').strip() # extract the text field safely
    if not text:
        raise QuizPipelineError('Whisper returned empty transcript.') # guard empty
    return text # return transcript for prompting
  
  
def _ensure_genai_configured() -> None:
    """Initialize the Gemini client with API key from environment."""
    if genai is None:
        raise QuizPipelineError('google-generativeai package not installed.') # missing client
    api_key = os.environ.get('GEMINI_API_KEY') # read key from env
    if not api_key:
        raise QuizPipelineError('GEMINI_API_KEY environment variable is missing.') # missing key
    genai.configure(api_key=api_key) # configure client globally


def generate_quiz_with_gemini(transcript: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Ask Gemini 1.5 Flash to write 10 multiple-choice questions in strict JSON.
    """
    _ensure_genai_configured()
    # NEW: force JSON-only output
    generation_config = {
        'response_mime_type': 'application/json',  # <- wichtig
        'temperature': 0.3,  # etwas deterministischer
    }
    model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)

    system_prompt = (
        'You are a quiz generator. Create exactly 10 multiple-choice questions (4 options each)\n'
        'based ONLY on the provided transcript. Include a short title and description.\n'
        'Return STRICT JSON with keys: title, description, questions. Each question must have\n'
        'question_title, options (list of 4 strings), and answer (one of options). No extra text.'
    )

    response = model.generate_content([system_prompt, transcript[:15000]])
    import logging
    logger = logging.getLogger(__name__)
    # Vorsicht: keine sensiblen Daten loggen; hier nur Modell-Output (gekürzt)
    logger.info('Gemini raw (first 600 chars): %s', (response.text or '')[:600])

    import json
    text = response.text or ''
    try:
        payload = json.loads(text)  # sollte jetzt klappen, da JSON erzwungen
    except Exception as e:
        # Fallback: nach JSON in Code-Fence oder größtem JSON-Block suchen (sicherheitshalber)
        payload = _parse_json_loose(text)  # siehe Helper unten, einmalig hinzufügen
        
    payload = _repair_quiz_payload(payload)  # try to fix common answer mismatches

    # Shape-Checks
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
    """
    Try several strategies to extract JSON from a model response that may include markdown or prose.
    """
    import json, re
    # 1) direct
    try:
        return json.loads(text)
    except Exception:
        pass
    # 2) fenced ```json ... ```
    m = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text, flags=re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 3) largest object between first '{' and last '}'
    s, e = text.find('{'), text.rfind('}')
    while s != -1 and e != -1 and e >= s:
        try:
            return json.loads(text[s:e+1])
        except Exception:
            e = text.rfind('}', 0, e)
    raise QuizPipelineError('Gemini returned unexpected format (no JSON).')