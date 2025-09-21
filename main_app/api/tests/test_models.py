import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from main_app.models import Quiz, Question


@pytest.mark.django_db
def test_model_str_reprs():
    """
    Ensures the __str__ representations of Quiz and Question include helpful info.

    We create a user-owning quiz (user is required now) and a question, then
    assert their string representations contain IDs and basic context.
    """
    User = get_user_model()
    user = User.objects.create_user(username='alice', password='pw123456')

    qz = Quiz.objects.create(
        user=user,                       # required: non-nullable FK to user
        title='T',
        description='D',
        video_url='https://youtu.be/1',
    )
    qu = Question.objects.create(
        quiz=qz,
        question_title='What?',
        question_options=['A', 'B', 'C', 'D'],
        answer='A',
    )

    # Quiz.__str__ should include model name, id, and owner context
    s_quiz = str(qz)
    assert 'Quiz' in s_quiz
    assert f'{qz.id}' in s_quiz
    assert f'{user.id}' in s_quiz

    # Question.__str__ should mention the question id and parent quiz id
    s_question = str(qu)
    assert 'Question' in s_question
    assert f'{qu.id}' in s_question
    assert f'{qz.id}' in s_question


@pytest.mark.django_db
def test_video_url_unique_per_user_only():
    """
    Validates the (user, video_url) uniqueness constraint:

    - Same user + same URL -> IntegrityError (inside transaction.atomic()).
    - Different user + same URL -> allowed.
    """
    User = get_user_model()
    u1 = User.objects.create_user(username='alice', password='pw123456')
    u2 = User.objects.create_user(username='bob', password='pw123456')

    # First quiz for u1 with a given URL
    Quiz.objects.create(user=u1, title='A', description='', video_url='https://youtu.be/dup')

    # Same user + same URL must violate UniqueConstraint('user', 'video_url').
    # Wrap in transaction.atomic() so the failure doesn't poison the outer transaction.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Quiz.objects.create(user=u1, title='B', description='', video_url='https://youtu.be/dup')

    # Different user + same URL is fine (new transaction state is clean)
    Quiz.objects.create(user=u2, title='C', description='', video_url='https://youtu.be/dup')
