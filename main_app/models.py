from django.conf import settings
from django.db import models


class Quiz(models.Model):
    """Represents a generated quiz for a single source video"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quizzes',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    video_url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Django model meta configuration for constraints and ordering"""
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'video_url'],
                name='uq_quiz_user_video_url',
            )
        ]
        ordering = ['-created_at']

    def __str__(self) -> str:
        """Returns readable representation with id and title"""
        return f'Quiz({self.id}) by User({self.user_id}): {self.title}'


class Question(models.Model):
    """Represents an individual question belonging to a quiz"""
    quiz = models.ForeignKey(
        'Quiz', on_delete=models.CASCADE, related_name='questions'
    )
    question_title = models.CharField(max_length=500)
    
    question_options = models.JSONField()
    answer = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        """Returns the question string preview"""
        return f'Question({self.id}) for Quiz({self.quiz_id})'