import pytest
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from main_app.models import Quiz, Question


@pytest.fixture
def api():
    """Return a DRF APIClient instance for tests."""
    # create and return a fresh APIClient per test
    return APIClient()


@pytest.fixture
def users(db):
    """Create and return two users for scoping tests."""
    # use the active AUTH_USER_MODEL (built-in or custom)
    User = get_user_model()  # get the user model dynamically
    # create two simple users with passwords (not used directly)
    u1 = User.objects.create_user(username='alice', email='alice@example.com', password='pw123456')
    u2 = User.objects.create_user(username='bob',   email='bob@example.com',   password='pw123456')
    # return them in a small dict for convenient access in tests
    return {'u1': u1, 'u2': u2}


@pytest.fixture
def sample_data(db, users):
    """
    Create quizzes and nested questions for both users.

    We also tweak created_at timestamps to ensure deterministic ordering
    (newest first) regardless of database timestamp precision.
    """
    # create two quizzes for user 1
    q1 = Quiz.objects.create(user=users['u1'], title='Q1', description='D1', video_url='https://youtu.be/1')
    q2 = Quiz.objects.create(user=users['u1'], title='Q2', description='D2', video_url='https://youtu.be/2')

    # create one quiz for user 2 (to verify scoping)
    q3 = Quiz.objects.create(user=users['u2'], title='Q3', description='D3', video_url='https://youtu.be/3')

    # add one simple question to each quiz (nested data must exist)
    for quiz, ans in ((q1, 'A'), (q2, 'B'), (q3, 'C')):
        Question.objects.create(
            quiz=quiz,
            question_title=f'Question for {quiz.title}',
            question_options=['A', 'B', 'C', 'D'],
            answer=ans,
        )

    # enforce deterministic ordering by adjusting timestamps explicitly:
    # set q2 newer than q1 for user u1
    now = timezone.now()
    Quiz.objects.filter(id=q1.id).update(created_at=now - timezone.timedelta(minutes=1))
    Quiz.objects.filter(id=q2.id).update(created_at=now)

    # return ids for optional debugging/use
    return {'u1_quizzes': [q1.id, q2.id], 'u2_quizzes': [q3.id]}


def test_requires_authentication_returns_401(api):
    """
    Unauthenticated requests to /api/quizzes/ should be rejected with 401.
    """
    # build the URL using the route name from urls.py
    url = reverse('quiz-list')  # resolves to /api/quizzes/
    # call endpoint without authentication
    res = api.get(url)
    # expect '401 Unauthorized' per spec
    assert res.status_code == 401
    # DRF typically provides a "detail" key on errors
    assert 'detail' in res.data


def test_returns_only_authenticated_users_quizzes(api, users, sample_data):
    """
    Authenticated user should receive only their own quizzes, newest first,
    and each quiz should include nested questions with the expected shape.
    """
    # authenticate as user u1 (bypasses cookie/JWT in tests)
    api.force_authenticate(users['u1'])
    # call the endpoint
    url = reverse('quiz-list')
    res = api.get(url)
    # expect OK
    assert res.status_code == 200

    data = res.json()  # response is a list
    # user u1 has exactly two quizzes in our fixture
    assert isinstance(data, list)
    assert len(data) == 2

    # ensure titles match and order is newest first (Q2 newer than Q1)
    titles = [item['title'] for item in data]
    assert titles == ['Q2', 'Q1']

    # verify a reasonable subset of the payload shape on the first quiz
    item = data[0]
    # top-level keys that must exist (others may also be present)
    for key in ('id', 'title', 'description', 'created_at', 'updated_at', 'video_url', 'questions'):
        assert key in item

    # nested questions must be a non-empty list with the expected fields
    questions = item['questions']
    assert isinstance(questions, list) and len(questions) >= 1
    q0 = questions[0]
    for key in ('id', 'question_title', 'question_options', 'answer'):
        assert key in q0
    # ensure options are a list of 4 strings and answer is one of them
    assert isinstance(q0['question_options'], list) and len(q0['question_options']) == 4
    assert q0['answer'] in q0['question_options']


def test_returns_empty_list_when_user_has_no_quizzes(api, users):
    """
    When the authenticated user owns no quizzes, return an empty list (200).
    """
    # authenticate as user u2 *before* any quizzes exist for them in this test
    api.force_authenticate(users['u2'])
    url = reverse('quiz-list')
    res = api.get(url)
    # since this test created no quizzes, it should be empty but 200 OK
    assert res.status_code == 200
    assert res.json() == []
