from django.urls import path
from main_app.api.views import CreateQuizView


urlpatterns = [
    path('createQuiz/', CreateQuizView.as_view(), name='create-quiz'),
]
