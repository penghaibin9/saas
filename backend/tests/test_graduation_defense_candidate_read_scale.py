"""答辩候选学生必须 SQL 收窄并限制候选窗口，禁止全租户加载后 Python 过滤。"""
from __future__ import annotations

from contextlib import contextmanager

from app.modules.graduation.services import graduation_defense_candidate_read_service as candidate_read
from app.modules.graduation.services import graduation_service


def test_defense_candidate_read_model_is_installed():
    assert graduation_service.list_defense_eligible_students is candidate_read.list_defense_eligible_students


def test_defense_candidate_query_is_bounded_and_server_searchable(monkeypatch):
    class Rows:
        @staticmethod
        def all():
            return []

    class FakeDb:
        def __init__(self):
            self.statement = None

        def scalars(self, statement):
            self.statement = statement
            return Rows()

    db = FakeDb()

    @contextmanager
    def fake_session():
        yield db

    monkeypatch.setattr(candidate_read, "session", fake_session)
    monkeypatch.setattr(candidate_read, "_tid", lambda: 900001)
    monkeypatch.setattr(candidate_read, "has_full_scope", lambda: True)

    rows = candidate_read.list_defense_eligible_students(keyword="2026")

    assert rows == []
    assert db.statement is not None
    assert db.statement._limit_clause.value == candidate_read.CANDIDATE_LIMIT == 200
    sql = str(db.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "FINAL_CHECK" in sql and "DEFENSE" in sql and "COMPLETED" in sql
    assert "2026" in sql
    assert "student_no" in sql


def test_defense_candidate_source_does_not_load_all_active_students_before_filtering():
    source = candidate_read.__file__
    text = open(source, encoding="utf-8").read()
    assert ".stage.in_(ELIGIBLE_STAGES)" in text
    assert ".limit(CANDIDATE_LIMIT)" in text
    assert "GraduationStudent.student_no.contains(value)" in text
    assert "for s in stus" not in text
