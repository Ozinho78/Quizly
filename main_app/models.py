from django.conf import settings
from django.db import models


class Quiz(models.Model):
    """
    Represents a generated quiz for a single source video.
    Fields:
    - user: Owner/creator of the quiz (foreign key to AUTH_USER_MODEL).
    - title: Human-friendly quiz title.
    - description: Short summary/intro of the quiz.
    - video_url: Original YouTube link used to generate the quiz.
    - created_at/updated_at: Timestamps managed by Django.

    Notes:
    - We enforce uniqueness per user+video_url (so different users can quiz the same video).
    """
    user = models.ForeignKey(  # link the quiz to its owner
        settings.AUTH_USER_MODEL,  # keep it flexible to custom user model
        on_delete=models.CASCADE,  # if the user is deleted, delete their quizzes
        related_name='quizzes',    # reverse relation: user.quizzes
    )
    title = models.CharField(max_length=255)  # store quiz title text up to 255 chars
    description = models.TextField(blank=True)  # optional free-form description text
    # not globally unique: uniqueness is enforced together with user
    video_url = models.URLField()  # YouTube URL used to generate the quiz
    created_at = models.DateTimeField(auto_now_add=True)  # set on first save
    updated_at = models.DateTimeField(auto_now=True)  # updated on each save

    class Meta:
        """Django model meta configuration for constraints and ordering."""
        constraints = [
            models.UniqueConstraint(  # enforce one quiz per (user, video_url)
                fields=['user', 'video_url'],
                name='uq_quiz_user_video_url',
            )
        ]
        ordering = ['-created_at']  # newest first

    def __str__(self) -> str:
        """Return readable representation with id and title."""
        return f'Quiz({self.id}) by User({self.user_id}): {self.title}'  # include owner for clarity


class Question(models.Model):
    """
    Represents an individual question belonging to a quiz.

    Fields:
    - quiz: FK to Quiz; cascade delete keeps integrity.
    - question_title: The actual question text.
    - question_options: Array of 4 strings (stored in JSONField for simplicity).
    - answer: The correct option string (must be one of question_options).
    - created_at/updated_at: Timestamps for auditing.
    """
    quiz = models.ForeignKey(  # link each question to its parent quiz
        'Quiz', on_delete=models.CASCADE, related_name='questions'
    )
    question_title = models.CharField(max_length=500)  # the question prompt
    # Use JSONField to store exactly 4 options as a simple list of strings
    question_options = models.JSONField()  # e.g. ["A", "B", "C", "D"]
    answer = models.CharField(max_length=500)  # must match one of the options
    created_at = models.DateTimeField(auto_now_add=True)  # set on create
    updated_at = models.DateTimeField(auto_now=True)  # set on update

    def __str__(self) -> str:
        """Return the question string preview."""
        return f'Question({self.id}) for Quiz({self.quiz_id})'