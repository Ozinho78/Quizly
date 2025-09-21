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
        """Partially updates allowed fields ('title', 'description') of a quiz owned by the authenticated user"""
        quiz = self.get_object()
        allowed_fields = {'title', 'description'}
        unknown = set(request.data.keys()) - allowed_fields
        if unknown:
            detail = f'Unknown field(s): {", ".join(sorted(unknown))}'
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
        serializer = QuizPartialUpdateSerializer(
            instance=quiz,
            data=request.data,
            partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        quiz.refresh_from_db()
        output = QuizSerializer(quiz).data
        return Response(output, status=status.HTTP_200_OK)
    
    def delete(self, request, *args, **kwargs):
        """Permanently deletes a quiz owned by the authenticated user"""
        quiz = self.get_object()
        quiz.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)