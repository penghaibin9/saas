"""A-W3 TeachingTask batch management-scope contract."""
from __future__ import annotations

import inspect

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
