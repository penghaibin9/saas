"""A-W3 TeachingTask batch management-scope contract."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import mysql


def _service():
    from app.modules.academic_affairs.services import academic_affairs_task_generation_service as service
    return service


def _compiled_batch_lookup(monkeypatch, college_id):
    from app.models import AaTeachingTaskBatch

    service = _service()
    monkeypatch.setattr(service, "_tid", lambda: 1000000000000000001)
    conditions = service._draft_batch_conditions(AaTeachingTaskBatch, 202601, college_id)
    statement = select(AaTeachingTaskBatch.id).where(*conditions)
    return str(statement.compile(
        dialect=mysql.dialect(),
        compile_kwargs={"literal_binds": True},
    ))


def _compiled_integrity_probe(monkeypatch, college_id=17):
    service = _service()
    monkeypatch.setattr(service, "_tid", lambda: 1000000000000000001)
    statement = service._college_draft_batch_integrity_statement(
        SimpleNamespace(id=8801, college_id=college_id)
    )
    return str(statement.compile(
        dialect=mysql.dialect(),
        compile_kwargs={"literal_binds": True},
    ))


def test_school_wide_generation_reuses_only_school_wide_draft(monkeypatch):
    sql = _compiled_batch_lookup(monkeypatch, None)
    assert "t_aa_teaching_task_batch.term_id = 202601" in sql
    assert "t_aa_teaching_task_batch.college_id IS NULL" in sql
    assert "t_aa_teaching_task_batch.status = 'DRAFT'" in sql


def test_college_generation_reuses_only_exact_college_draft(monkeypatch):
    sql = _compiled_batch_lookup(monkeypatch, 17)
    assert "t_aa_teaching_task_batch.college_id = 17" in sql
    assert "t_aa_teaching_task_batch.college_id IS NULL" not in sql


def test_generate_batch_tx_uses_exact_draft_scope_helper():
    source = inspect.getsource(_service().generate_batch_tx)
    assert "conditions = _draft_batch_conditions(AaTeachingTaskBatch, term_id, college_id)" in source
    assert "conditions.append(AaTeachingTaskBatch.college_id == college_id)" not in source


def test_college_draft_integrity_probe_is_one_bounded_task_class_major_query(monkeypatch):
    sql = _compiled_integrity_probe(monkeypatch)
    assert "FROM t_aa_teaching_task" in sql
    assert "LEFT OUTER JOIN t_class" in sql
    assert "LEFT OUTER JOIN t_major" in sql
    assert "t_aa_teaching_task.batch_id = 8801" in sql
    assert "t_aa_teaching_task.class_id IS NULL" in sql
    assert "t_class.id IS NULL" in sql
    assert "t_major.id IS NULL" in sql
    assert "t_major.college_id != 17" in sql
    assert "LIMIT 21" in sql
    assert "t_student_profile" not in sql
    assert "t_aa_teaching_class_member" not in sql


class _ScalarResult:
    def __init__(self, values):
        self._values = list(values)

    def all(self):
        return list(self._values)


class _Db:
    def __init__(self, values):
        self.values = list(values)
        self.statement = None

    def scalars(self, statement):
        self.statement = statement
        return _ScalarResult(self.values)


def test_college_draft_integrity_fails_closed_with_bounded_task_samples(monkeypatch):
    from app.core.exceptions import AppException

    service = _service()
    monkeypatch.setattr(service, "_tid", lambda: 1000000000000000001)
    db = _Db(range(1001, 1023))
    batch = SimpleNamespace(id=8801, college_id=17)

    with pytest.raises(AppException) as exc:
        service._guard_college_draft_batch_integrity(db, batch)

    assert exc.value.code == "DATA_CONFLICT"
    details = exc.value.details or {}
    assert details["blocker"] == "TASK_BATCH_SCOPE_CONTAMINATED"
    assert details["batchId"] == "8801"
    assert details["collegeId"] == "17"
    assert details["sampleTaskIds"] == [str(value) for value in range(1001, 1021)]
    assert details["sampleTruncated"] is True


def test_school_wide_draft_does_not_apply_college_integrity_guard(monkeypatch):
    service = _service()
    monkeypatch.setattr(service, "_tid", lambda: 1000000000000000001)

    class _NoQueryDb:
        def scalars(self, _statement):
            raise AssertionError("school-wide batch must not run college integrity query")

    service._guard_college_draft_batch_integrity(
        _NoQueryDb(), SimpleNamespace(id=9901, college_id=None)
    )


def test_generate_batch_checks_existing_college_draft_before_appending():
    source = inspect.getsource(_service().generate_batch_tx)
    guard = "_guard_college_draft_batch_integrity(db, batch)"
    assert guard in source
    assert source.index(guard) < source.index("if not batch:")
