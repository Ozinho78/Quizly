from django.conf import settings # access settings (cookie names) if needed
import tempfile # for safe temp dirs/files
from rest_framework.views import APIView # DRF base class
from rest_framework.response import Response # HTTP responses
from rest_framework import status # HTTP codes
from rest_framework.generics import ListAPIView, RetrieveAPIView # generic views
from rest_framework.permissions import IsAuthenticated # gate by auth
from rest_framework_simplejwt.authentication import JWTAuthentication # default JWT auth
from main_app.api.serializers import QuizCreateSerializer, QuizSerializer, QuizPartialUpdateSerializer  # our serializers
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

    def post(self, request):
        serializer = QuizCreateSerializer(data=request.data)  # parse input
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        url = serializer.validated_data['url']  # safe YouTube URL

        # IMPORTANT: reuse only if the same user already created this quiz for the same video
        existing = Quiz.objects.filter(user=request.user, video_url=url).first()
        if existing:
            return Response(QuizSerializer(existing).data, status=status.HTTP_200_OK)

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
                # NEW: attach quiz to the authenticated user
                quiz = Quiz.objects.create(
                    user=request.user,  # <— owner set
                    title=quiz_payload.get('title', 'Quiz'),
                    description=quiz_payload.get('description', ''),
                    video_url=url,
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
          

class QuizListView(ListAPIView):
    """
    GET /api/quizzes/
    Returns all quizzes of the authenticated user, including nested questions.
    Authentication:
      - JWT via HttpOnly cookie (see CookieJWTAuthentication above).
    Responses:
      - 200: List of quizzes (may be empty).
      - 401: Not authenticated.
      - 500: Unexpected server error.
    """
    authentication_classes = [CookieJWTAuthentication]  # read JWT from cookie
    permission_classes = [IsAuthenticated]              # require logged-in user
    serializer_class = QuizSerializer                   # nested questions included

    def get_queryset(self):
        """
        Return only the quizzes owned by the current user.

        We rely on the new user foreign key on Quiz and default ordering (newest first).
        """
        # self.request.user is guaranteed by IsAuthenticated
        return Quiz.objects.filter(user=self.request.user).prefetch_related('questions')
    
    
class QuizDetailView(RetrieveAPIView):
    """
    GET /api/quizzes/{id}
    Returns a specific quiz of the authenticated user including all questions.
    Permissions:
      - Authenticated via JWT in HttpOnly cookies.
      - User can only access their own quizzes.
    Responses:
      - 200: Quiz with nested questions.
      - 401: Not authenticated.
      - 403: Quiz belongs to another user.
      - 404: Quiz not found.
      - 500: Internal server error.
    """
    authentication_classes = [CookieJWTAuthentication]  # read JWT from cookie
    permission_classes = [IsAuthenticated]              # require login
    serializer_class = QuizSerializer                   # nested questions included
    queryset = Quiz.objects.all().prefetch_related('questions')  # base queryset

    def get_object(self):
        """
        Restrict lookup to the requesting user.  
        Raises 403 if the quiz exists but belongs to another user.
        """
        from rest_framework.exceptions import PermissionDenied, NotFound

        quiz_id = self.kwargs.get('pk')  # quiz id from URL
        try:
            quiz = Quiz.objects.prefetch_related('questions').get(pk=quiz_id)
        except Quiz.DoesNotExist:
            raise NotFound('Quiz not found.')

        if quiz.user != self.request.user:
            raise PermissionDenied('You do not have permission to access this quiz.')

        return quiz
    
    def patch(self, request, *args, **kwargs):
        """
        PATCH /api/quizzes/{id}/
        Partially update allowed fields ('title', 'description') of a quiz
        owned by the authenticated user, then return the full quiz payload.

        Responses:
          - 200: Quiz successfully updated (full serialized quiz returned).
          - 400: Invalid request data (e.g., unknown fields or validation errors).
          - 401: Not authenticated.
          - 403: Quiz belongs to another user.
          - 404: Quiz not found.
          - 500: Internal server error (handled by DRF or outer middleware).
        """
        # Resolve the quiz instance while enforcing ownership (may raise 403/404).
        quiz = self.get_object()

        # Bind incoming data to a write-serializer for partial update.
        serializer = QuizPartialUpdateSerializer(
            instance=quiz,          # the DB object we are updating
            data=request.data,      # incoming partial fields
            partial=True            # allow omitting fields (PATCH semantics)
        )

        # Validate input; on error we return 400 with details.
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Persist the changes to the database.
        serializer.save()  # updates only the provided fields

        # Refresh from DB to ensure we serialize the latest state (timestamps updated).
        quiz.refresh_from_db()

        # Return the full quiz representation including nested questions.
        return Response(QuizSerializer(quiz).data, status=status.HTTP_200_OK)