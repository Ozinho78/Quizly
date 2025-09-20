from rest_framework import serializers # DRF serializers base
from main_app.models import Quiz, Question # import our ORM models


class QuestionSerializer(serializers.ModelSerializer):
    """
    Read-only nested serializer for returning question data.
    """
    class Meta:
        model = Question # bind to Question model
        fields = (
        'id', 'question_title', 'question_options', 'answer', 'created_at', 'updated_at'
        ) # exact response contract
        read_only_fields = fields # ensure nested output only


class QuizSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for a quiz including nested questions.
    """
    questions = QuestionSerializer(many=True, read_only=True) # include nested questions

    class Meta:
        model = Quiz # bind to Quiz model
        fields = (
        'id', 'title', 'description', 'created_at', 'updated_at', 'video_url', 'questions'
        ) # match the API spec
        read_only_fields = fields # output-only


class QuizCreateSerializer(serializers.Serializer):
    """
    Write-only input serializer for the createQuiz endpoint.
    Accepts only the YouTube URL and performs basic validation.
    """
    url = serializers.URLField(required=True) # required YouTube link

    def validate_url(self, value: str) -> str:
        """Ensure the URL looks like a YouTube link and is not empty."""
        if not value:
          raise serializers.ValidationError('URL must not be empty.') # guard empty
        # naive YouTube check; you may swap in your custom validator
        if 'youtube.com/watch' not in value and 'youtu.be/' not in value:
          raise serializers.ValidationError('Only YouTube URLs are allowed for now.')
        return value # ok