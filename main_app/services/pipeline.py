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
    Ask Gemini 1.5 Flash to write 10 multiple-choice questions from the transcript.
    Returns a dict with shape: {
    'title': str,
    'description': str,
    'questions': [ {'question_title': str, 'options': [str, str, str, str], 'answer': str}, ...]
    }
    """
    _ensure_genai_configured() # validate client
    model = genai.GenerativeModel('gemini-1.5-flash') # select fast, cost-effective model

    # Prompt engineered to ensure structure; asks for strict JSON
    system_prompt = (
        'You are a quiz generator. Create exactly 10 multiple-choice questions (4 options each)\n'
        'based ONLY on the provided transcript. Include a short title and description.\n'
        'Return STRICT JSON with keys: title, description, questions. Each question must have\n'
        'question_title, options (list of 4 strings), and answer (one of options). No extra text.'
    )

    # Call the model with a JSON-friendly response
    response = model.generate_content([
        system_prompt, # instruction
        transcript[:15000], # cap tokens for long videos (simple guard)
    ])

    # Extract text; Gemini often returns JSON as a code block → best-effort parse
    text = response.text or '' # get raw model text

    import json, re # parse helpers
    # Try to find a JSON block in the response
    match = re.search(r'\{[\s\S]*\}$', text.strip()) # naive JSON capture from first '{' to end
    if not match:
        raise QuizPipelineError('Gemini returned unexpected format (no JSON).') # guard format

    payload = json.loads(match.group(0)) # parse JSON string


    # Basic shape validation
    if 'questions' not in payload or len(payload['questions']) != 10:
        raise QuizPipelineError('Model did not produce exactly 10 questions.') # enforce count
    for q in payload['questions']:
        opts = q.get('options', []) # retrieve options list
        if len(opts) != 4:
            raise QuizPipelineError('Each question must have 4 options.') # enforce cardinality
        if q.get('answer') not in opts:
            raise QuizPipelineError('Answer must be one of the options.') # enforce consistency

    return payload # structured quiz content