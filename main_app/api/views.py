from django.conf import settings # access settings (cookie names) if needed
import tempfile # for safe temp dirs/files
from rest_framework.views import APIView # DRF base class
from rest_framework.response import Response # HTTP responses
from rest_framework import status # HTTP codes
from rest_framework.permissions import IsAuthenticated # gate by auth
from rest_framework_simplejwt.authentication import JWTAuthentication # default JWT auth
from main_app.api.serializers import QuizCreateSerializer, QuizSerializer # our serializers
from main_app.models import Quiz, Question # ORM models
from main_app.services import pipeline
from main_app.services.pipeline import QuizPipelineError

class CookieJWTAuthentication(JWTAuthentication):
    """
    Simple JWT auth class that reads the access token from an HttpOnly cookie.


    This allows the frontend to authenticate without Authorization headers.
    """
    def authenticate(self, request): # override to read from cookie
        access_cookie_name = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token') # cookie key
        token = request.COOKIES.get(access_cookie_name) # read cookie value
        if not token:
            return None # let DRF continue to next authenticator → 401 by permission
        # Inject header-like structure so parent class can validate signature/exp/claims
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {token}' # fake header for parent logic
        return super().authenticate(request) # call into JWTAuthentication


class CreateQuizView(APIView):
    """
    POST /api/createQuiz/
    Creates a new quiz from a YouTube URL and returns the quiz with all questions.
    Requires authentication via JWT in HttpOnly cookies.
    """
    authentication_classes = [CookieJWTAuthentication] # use cookie-based JWT
    permission_classes = [IsAuthenticated] # require a valid user

    def post(self, request): # handle POST requests
        serializer = QuizCreateSerializer(data=request.data) # parse input
        if not serializer.is_valid(): # validate basic schema/URL
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) # 400 on input errors
        url = serializer.validated_data['url'] # safe YouTube URL

        # If a quiz for this video already exists, return it (idempotent behavior is handy)
        existing = Quiz.objects.filter(video_url=url).first() # try to reuse
        if existing: # if found
            return Response(QuizSerializer(existing).data, status=status.HTTP_200_OK) # return cached quiz

        try:
            # Work directory for temp artifacts
            with tempfile.TemporaryDirectory() as tmpdir: # ensure cleanup
                from pathlib import Path # local import to keep namespace small
                workdir = Path(tmpdir) # Path object for convenience

                # 1) Download and convert audio
                wav_path = pipeline.download_audio_from_youtube(url, workdir) # get 16k mono wav

                # 2) Transcribe with Whisper
                transcript = pipeline.transcribe_audio_with_whisper(wav_path) # extract spoken text

                # 3) Create questions via Gemini
                quiz_payload = pipeline.generate_quiz_with_gemini(transcript) # returns dict structure

                # 4) Persist models
                quiz = Quiz.objects.create( # create the quiz row
                    title=quiz_payload.get('title', 'Quiz'), # title from AI
                    description=quiz_payload.get('description', ''), # description from AI
                    video_url=url, # original YouTube link
                )

                # create all questions in bulk for efficiency
                question_objs = [] # build a list to bulk_create
                for item in quiz_payload['questions']: # iterate 10 entries
                    question_objs.append(
                    Question(
                    quiz=quiz, # FK
                    question_title=item['question_title'], # prompt text
                    question_options=item['options'], # list[str]
                    answer=item['answer'], # correct option
                )
                )
                Question.objects.bulk_create(question_objs) # insert in one query

                # refresh from DB to populate reverse relation
                quiz.refresh_from_db() # ensures questions are attached

                # serialize full quiz for response
                data = QuizSerializer(quiz).data # nested output
                return Response(data, status=status.HTTP_201_CREATED) # 201 per spec

        except QuizPipelineError as e: # known pipeline failure
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) # return clean 500
        except Exception: # unknown/unexpected errors
            return Response({'detail': 'Internal server error.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) # generic 500
          
