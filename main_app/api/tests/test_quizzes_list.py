import pytest
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from main_app.models import Quiz, Question


@pytest.fixture
def api():
    """Returns a DRF APIClient instance for tests"""
    return APIClient()


@pytest.fixture
def users(db):
    """Creates and returns two users for scoping tests"""
    User = get_user_model()
    u1 = User.objects.create_user(username='alice', email='alice@example.com', password='pw123456')
    u2 = User.objects.create_user(username='bob',   email='bob@example.com',   password='pw123456')
    return {'u1': u1, 'u2': u2}


@pytest.fixture
def sample_data(db, users):
    """Creates quizzes and nested questions for both users"""
    q1 = Quiz.objects.create(user=users['u1'], title='Q1', description='D1', video_url='https://youtu.be/1')
    q2 = Quiz.objects.create(user=users['u1'], title='Q2', description='D2', video_url='https://youtu.be/2')
    q3 = Quiz.objects.create(user=users['u2'], title='Q3', description='D3', video_url='https://youtu.be/3')
    for quiz, ans in ((q1, 'A'), (q2, 'B'), (q3, 'C')):
        Question.objects.create(
            quiz=quiz,
            question_title=f'Question for {quiz.title}',
            question_options=['A', 'B', 'C', 'D'],
            answer=ans,
        )
    now = timezone.now()
    Quiz.objects.filter(id=q1.id).update(created_at=now - timezone.timedelta(minutes=1))
    Quiz.objects.filter(id=q2.id).update(created_at=now)
    return {'u1_quizzes': [q1.id, q2.id], 'u2_quizzes': [q3.id]}


def test_requires_authentication_returns_401(api):
    """Unauthenticated requests to /api/quizzes/ should be rejected with 401"""
    url = reverse('quiz-list')
    res = api.get(url)
    assert res.status_code == 401
    assert 'detail' in res.data


def test_returns_only_authenticated_users_quizzes(api, users, sample_data):
    """Authenticated user should receive only their own quizzes"""
    api.force_authenticate(users['u1'])
    url = reverse('quiz-list')
    res = api.get(url)
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 2
    titles = [item['title'] for item in data]
    assert titles == ['Q2', 'Q1']
    item = data[0]
    for key in ('id', 'title', 'description', 'created_at', 'updated_at', 'video_url', 'questions'):
        assert key in item
    questions = item['questions']
    assert isinstance(questions, list) and len(questions) >= 1
    q0 = questions[0]
    for key in ('id', 'question_title', 'question_options', 'answer'):
        assert key in q0
    assert isinstance(q0['question_options'], list) and len(q0['question_options']) == 4
    assert q0['answer'] in q0['question_options']


def test_returns_empty_list_when_user_has_no_quizzes(api, users):
    """When the authenticated user owns no quizzes, return an empty list with 200"""
    api.force_authenticate(users['u2'])
    url = reverse('quiz-list')
    res = api.get(url)
    assert res.status_code == 200
    assert res.json() == []