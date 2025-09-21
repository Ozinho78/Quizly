from django.conf import settings
import tempfile
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from main_app.api.serializers import QuizCreateSerializer, QuizSerializer, QuizPartialUpdateSerializer
from main_app.models import Quiz, Question
from main_app.services import pipeline
from main_app.services.pipeline import QuizPipelineError

class CookieJWTAuthentication(JWTAuthentication):
    """Simple JWT auth class that reads the access token from an HttpOnly cookie"""
    def authenticate(self, request):
        access_cookie_name = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')
        token = request.COOKIES.get(access_cookie_name)
        if not token:
            return None
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return super().authenticate(request)


class CreateQuizView(APIView):
    """Creates a new quiz from a YouTube URL and returns the quiz with all questions"""
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = QuizCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        url = serializer.validated_data['url']
        existing = Quiz.objects.filter(user=request.user, video_url=url).first()
        if existing:
            return Response(QuizSerializer(existing).data, status=status.HTTP_200_OK)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                from pathlib import Path
                workdir = Path(tmpdir)
                wav_path = pipeline.download_audio_from_youtube(url, workdir)
                transcript = pipeline.transcribe_audio_with_whisper(wav_path)
                quiz_payload = pipeline.generate_quiz_with_gemini(transcript)
                quiz = Quiz.objects.create(
                    user=request.user,
                    title=quiz_payload.get('title', 'Quiz'),
                    description=quiz_payload.get('description', ''),
                    video_url=url,
                )
                question_objs = []
                for item in quiz_payload['questions']:
                    question_objs.append(
                        Question(
                        quiz=quiz, # FK
                        question_title=item['question_title'],
                        question_options=item['options'],
                        answer=item['answer'],
                )
                )
                Question.objects.bulk_create(question_objs)
                quiz.refresh_from_db()
                data = QuizSerializer(quiz).data
                return Response(data, status=status.HTTP_201_CREATED)
        except QuizPipelineError as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception:
            return Response({'detail': 'Internal server error.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
          

class QuizListView(ListAPIView):
    """Returns all quizzes of the authenticated user, including nested questions"""
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = QuizSerializer

    def get_queryset(self):
        """Returns only the quizzes owned by the current user"""
        return Quiz.objects.filter(user=self.request.user).prefetch_related('questions')
    
    
class QuizDetailView(RetrieveAPIView):
    """Returns a specific quiz of the authenticated user including all questions"""
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = QuizSerializer
    queryset = Quiz.objects.all().prefetch_related('questions')

    def get_object(self):
        """Restricts lookup to the requesting user"""
        from rest_framework.exceptions import PermissionDenied, NotFound
        quiz_id = self.kwargs.get('pk')
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
        Partially update allowed fields ('title', 'description') of a quiz owned by the authenticated user.

        Returns:
          200: Updated quiz with full details (including nested questions).
          400: Invalid request data or unknown fields.
          401: Not authenticated.
          403: Forbidden (quiz belongs to someone else).
          404: Quiz not found.
        """
        # Resolve the target quiz or raise 404/403 based on ownership.
        quiz = self.get_object()  # enforces ownership in get_object()

        # Define a strict whitelist of fields allowed to be changed via PATCH.
        allowed_fields = {'title', 'description'}  # only these keys are legal

        # Compute any keys in the incoming payload that are not allowed.
        unknown = set(request.data.keys()) - allowed_fields  # detect foreign keys

        # If we found unknown keys, reject early with a 400 to satisfy the contract & tests.
        if unknown:
            # Build a human-readable message listing the offending fields.
            detail = f'Unknown field(s): {", ".join(sorted(unknown))}'
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)  # fail fast

        # Bind the incoming partial data to the dedicated write-serializer.
        serializer = QuizPartialUpdateSerializer(
            instance=quiz,      # model instance to update
            data=request.data,  # partial payload with allowed keys
            partial=True        # PATCH semantics (fields optional)
        )

        # Validate and return 400 with errors if invalid.
        if not serializer.is_valid():  # run field-level & object-level checks
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  # invalid data

        # Persist changes to DB.
        serializer.save()  # updates only provided fields

        # Refresh instance to capture updated timestamps (updated_at) before serializing.
        quiz.refresh_from_db()  # ensure latest state

        # Serialize the full quiz (read-only serializer) including nested questions.
        output = QuizSerializer(quiz).data  # full response shape

        # Return the updated resource.
        return Response(output, status=status.HTTP_200_OK)  # success
    
    def delete(self, request, *args, **kwargs):
        """
        DELETE /api/quizzes/{id}/
        Permanently delete a quiz owned by the authenticated user (including all related questions).

        Returns:
          - 204: Quiz successfully deleted (no response body).
          - 401: Not authenticated.
          - 403: Forbidden (quiz belongs to someone else).
          - 404: Quiz not found.
        Warning:
          This operation is permanent and cannot be undone.
        """
        # Load the quiz instance or raise 404; ownership checks should happen in get_object()
        quiz = self.get_object()  # retrieves the quiz instance for the current user or raises PermissionDenied/NotFound

        # Perform the deletion; related Question rows will be removed via FK cascade if defined on the model
        quiz.delete()  # delete the quiz record from the database

        # Return 204 No Content to indicate success with no response body
        return Response(status=status.HTTP_204_NO_CONTENT)  # comply with spec: null body on success