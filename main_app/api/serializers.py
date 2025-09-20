from urllib.parse import urlparse, parse_qs
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
        """
        Ensure the URL is an HTTP(S) YouTube link and points to a playable video.

        Rules:
          - Scheme must be http or https (reject ftp, file, etc.).
          - Host must be youtube.com (watch?v=...) or youtu.be (/<id>).
          - For youtube.com: path should include /watch and query must contain a non-empty 'v'.
          - For youtu.be: path must contain a non-empty video id segment.
        """
        # Parse the URL once using urllib for robust checks.
        parsed = urlparse(value)  # break URL into components

        # 1) Enforce allowed schemes only.
        if parsed.scheme not in ('http', 'https'):  # reject ftp and others
            raise serializers.ValidationError('Only http/https YouTube URLs are allowed.')

        # 2) Normalize host for comparison.
        host = (parsed.netloc or '').lower()  # safe lowercased host

        # 3) Accept full YouTube watch links.
        if host.endswith('youtube.com'):
            # Require the canonical watch path.
            if '/watch' not in parsed.path:  # e.g., /watch
                raise serializers.ValidationError('Only youtube.com/watch URLs are allowed.')
            # Require a non-empty v parameter.
            qs = parse_qs(parsed.query)  # parse query string
            vvals = qs.get('v', [])  # list of values for 'v'
            if not vvals or not (vvals[0] or '').strip():  # missing or empty video id
                raise serializers.ValidationError('YouTube URL must include a non-empty v parameter.')
            return value  # valid full YouTube URL

        # 4) Accept shortened youtu.be links with a path segment as the video id.
        if host.endswith('youtu.be'):
            video_id = (parsed.path or '').strip('/')  # extract path segment
            if not video_id:  # empty path → no id
                raise serializers.ValidationError('Short youtu.be URL must include a video id in the path.')
            return value  # valid short link

        # 5) Everything else is rejected.
        raise serializers.ValidationError('Only YouTube URLs are allowed.')