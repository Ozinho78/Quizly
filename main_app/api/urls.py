from django.urls import path
from main_app.api.views import CreateQuizView, QuizListView


urlpatterns = [
    path('createQuiz/', CreateQuizView.as_view(), name='create-quiz'),
    path('quizzes/', QuizListView.as_view(), name='quiz-list'),
]
