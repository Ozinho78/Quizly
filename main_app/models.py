from django.db import models

class Quiz(models.Model):
    """
    Represents a generated quiz for a single source video.
    Fields:
    - title: Human-friendly quiz title.
    - description: Short summary/intro of the quiz.
    - video_url: Original YouTube link used to generate the quiz.
    - created_at/updated_at: Timestamps managed by Django.
    """
    title = models.CharField(max_length=255) # store quiz title text up to 255 chars
    description = models.TextField(blank=True) # optional free-form description text
    video_url = models.URLField(unique=True) # unique YouTube URL to avoid duplicates for same video
    created_at = models.DateTimeField(auto_now_add=True) # set on first save
    updated_at = models.DateTimeField(auto_now=True) # updated on each save

    def __str__(self) -> str: # debug-friendly string representation
      """Return readable representation with id and title."""
      return f"Quiz({self.id}): {self.title}" # include primary key and title


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
    quiz = models.ForeignKey( # link each question to its parent quiz
    'Quiz', on_delete=models.CASCADE, related_name='questions'
    )
    question_title = models.CharField(max_length=500) # the question prompt
    # Use JSONField to store exactly 4 options as a simple list of strings
    question_options = models.JSONField() # e.g. ["A", "B", "C", "D"]
    answer = models.CharField(max_length=500) # must match one of the options
    created_at = models.DateTimeField(auto_now_add=True) # set on create
    updated_at = models.DateTimeField(auto_now=True) # set on update

    def __str__(self) -> str: # helpful for admin/debug
        """Return the question string preview."""
        return f"Question({self.id}) for Quiz({self.quiz_id})"