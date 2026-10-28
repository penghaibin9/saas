from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.modules.internship.services import internship_student_support_service as support


@pytest.fixture
def story(monkeypatch):
    row = SimpleNamespace(id=1, status='ACTIVE', unresolved_count=0, version=7,
        context_json=[{'question': '怎么请假', 'answer': '进入请假页面', 'askedAt': '2026-10-13T00:00:00Z', 'answerVersion': 7}],
        last_question='怎么请假', last_answer='进入请假页面', transferred_risk_id=None, transferred_at=None)
    db = SimpleNamespace(commit=lambda: None, flush=lambda: None,
        scalar=lambda query: SimpleNamespace(action='SUPPORT_FAQ_ASK', occurred_at=datetime(2026, 10, 13, 0, 0, 1)),
        scalars=lambda query: SimpleNamespace(first=lambda: row))
    @contextmanager
    def session():
        yield db
    monkeypatch.setattr(support, 'session', session)
    monkeypatch.setattr(support, '_tid', lambda: 991)
    monkeypatch.setattr(support, '_context', lambda *a, **k: (SimpleNamespace(id=3), SimpleNamespace(id=4), 5))
    monkeypatch.setattr(support, '_owned_session', lambda *a, **k: row)
    audits = []
    monkeypatch.setattr(support, 'add_audit', lambda *a, **k: audits.append(k))
    return row, db, audits


def test_current_reads_pending_answer_and_same_feedback_retry_counts_once(story):
    row, db, audits = story
    view = support.current({}, batch_id=5, internship_id=3)
    assert view['awaitingFeedback'] is True and view['answerVersion'] == 7
    first = support.unresolved({}, 1, {'answerVersion': 7})
    repeated = support.unresolved({}, 1, {'answerVersion': 7})
    assert first['unresolvedCount'] == repeated['unresolvedCount'] == 1
    assert repeated['awaitingFeedback'] is False and repeated['answerVersion'] == 7
    assert row.context_json[-1]['feedback'] == 'UNRESOLVED'
    assert len(audits) == 1
    with pytest.raises(AppException):
        support.solved({}, 1, {'answerVersion': 7})


@pytest.mark.parametrize('version', [None, True, '7', 7.0, 6])
def test_feedback_rejects_missing_noninteger_and_old_answer(story, version):
    row, db, audits = story
    with pytest.raises(AppException):
        support.unresolved({}, 1, {'answerVersion': version})
    assert row.unresolved_count == 0 and not audits


def test_legacy_answer_requires_trustworthy_latest_audit(story):
    row, db, audits = story
    row.context_json[-1].pop('answerVersion')
    view = support.current({}, batch_id=5, internship_id=3)
    assert view['awaitingFeedback'] is True and view['answerVersion'] == 7
    db.scalar = lambda query: SimpleNamespace(action='SUPPORT_UNRESOLVED', occurred_at=datetime(2026, 10, 13, 0, 0, 1))
    assert support.current({}, batch_id=5, internship_id=3)['awaitingFeedback'] is False
    db.scalar = lambda query: None
    view = support.current({}, batch_id=5, internship_id=3)
    assert view['awaitingFeedback'] is False and view['answerVersion'] is None
    assert '重新提问' in view['feedbackNotice']
    assert 'answerVersion' not in row.context_json[-1]


def test_legacy_audit_second_precision_matches_question_microseconds(story):
    row, db, audits = story
    row.context_json[-1].pop('answerVersion')
    row.context_json[-1]['askedAt'] = '2026-10-13T00:00:01.123456Z'
    db.scalar = lambda query: SimpleNamespace(action='SUPPORT_FAQ_ASK', occurred_at=datetime(2026, 10, 13, 0, 0, 1))
    assert support.current({}, batch_id=5, internship_id=3)['awaitingFeedback'] is True
    db.scalar = lambda query: SimpleNamespace(action='SUPPORT_FAQ_ASK', occurred_at=datetime(2026, 10, 13, 0, 0, 0))
    assert support.current({}, batch_id=5, internship_id=3)['awaitingFeedback'] is False


def test_old_answer_cannot_mark_new_answer_solved(story):
    row, db, audits = story
    row.context_json[-1]['answerVersion'] = 9
    row.version = 9
    with pytest.raises(AppException):
        support.solved({}, 1, {'answerVersion': 7})
    assert row.status == 'ACTIVE' and not audits
