from urllib.parse import urlparse, parse_qs
from rest_framework import serializers
from main_app.models import Quiz, Question


class QuestionSerializer(serializers.ModelSerializer):
    """Read-only nested serializer for returning question data"""
    class Meta:
        model = Question
        fields = (
            'id', 'question_title', 'question_options', 'answer', 'created_at', 'updated_at'
        )
        read_only_fields = fields


class QuizSerializer(serializers.ModelSerializer):
    """Read-only serializer for a quiz including nested questions"""
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = (
        'id', 'title', 'description', 'created_at', 'updated_at', 'video_url', 'questions'
        )
        read_only_fields = fields


class QuizCreateSerializer(serializers.Serializer):
    """Write-only input serializer for the createQuiz endpoint. Accepts only the YouTube URL and performs basic validation"""
    url = serializers.URLField(required=True)

    def validate_url(self, value: str) -> str:
        """Ensures the URL is an HTTP(S) YouTube link and points to a playable video"""
        parsed = urlparse(value)
        if parsed.scheme not in ('http', 'https'):
            raise serializers.ValidationError('Only http/https YouTube URLs are allowed.')
        host = (parsed.netloc or '').lower()
        if host.endswith('youtube.com'):
            if '/watch' not in parsed.path:
                raise serializers.ValidationError('Only youtube.com/watch URLs are allowed.')
            qs = parse_qs(parsed.query)
            vvals = qs.get('v', [])
            if not vvals or not (vvals[0] or '').strip():
                raise serializers.ValidationError('YouTube URL must include a non-empty v parameter.')
            return value

        if host.endswith('youtu.be'):
            video_id = (parsed.path or '').strip('/')
            if not video_id:
                raise serializers.ValidationError('Short youtu.be URL must include a video id in the path.')
            return value
        raise serializers.ValidationError('Only YouTube URLs are allowed.')
    
    
class QuizPartialUpdateSerializer(serializers.ModelSerializer):
    """Serializer used for PATCH updates on a Quiz"""
    class Meta:
        model = Quiz
        fields = ('title', 'description')
        extra_kwargs = {
            'title': {'required': False},
            'description': {'required': False},
        }

    def validate_title(self, value: str) -> str:
        """Ensures provided 'title' is non-empty after trimming and within length limits"""
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Title must not be empty when provided.')
        if len(value) > 255:
            raise serializers.ValidationError('Title must be at most 255 characters.')
        return value