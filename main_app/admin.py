from django.contrib import admin
from .models import Quiz, Question

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """
    Admin config for Quiz to surface ID, owner, and basic metadata.
    """
    list_display = ('id', 'user', 'title', 'video_url', 'created_at')  # show key columns
    search_fields = ('title', 'description', 'video_url', 'user__username', 'user__email')
    list_filter = ('created_at',)
    readonly_fields = ('id', 'created_at', 'updated_at')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """
    Admin config for Question to aid debugging and manual checks.
    """
    list_display = ('id', 'quiz', 'question_title')
    search_fields = ('question_title', 'quiz__title', 'quiz__user__username')
    readonly_fields = ('id', 'created_at', 'updated_at')
