"""V9.2 U5/M8 · 大校毕设学生列表 SQL 分页/dataScope 合同。"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import select

from app.models import GraduationStudent
from app.modules.graduation.services import graduation_student_read_service as student_read
from app.modules.graduation.services import graduation_student_service as student_service

ROOT = Path(__file__).resolve().parents[1]


def test_u5_student_list_is_bound_to_sql_read_model_only():
    assert student_service.list_students is student_read.list_students


def test_u5_student_list_source_forbids_python_scope_and_n_plus_one():
    source = (ROOT / "app/modules/graduation/services/graduation_student_read_service.py").read_text(
        encoding="utf-8"
    )
    assert "student_scope_select" in source
    assert "accessible_student_ids" not in source
    assert "can_access_student" not in source
    assert "select(func.count())" in source
    assert ".offset(" in source
    assert ".limit(" in source
    assert "_material_snapshot(db" not in source


def test_u5_student_list_executes_count_plus_one_paged_select(monkeypatch):
    class Rows:
        @staticmethod
        def all():
            return []

    class FakeDb:
        def __init__(self):
            self.statements = []

        def scalar(self, statement):
            self.statements.append(("count", statement))
            return 25000

        def execute(self, statement):
            self.statements.append(("page", statement))
            return Rows()

    db = FakeDb()

    @contextmanager
    def fake_session():
        yield db

    monkeypatch.setattr(student_read, "session", fake_session)
    monkeypatch.setattr(student_read, "_tid", lambda: 900001)
    monkeypatch.setattr(
        student_read,
        "student_scope_select",
        lambda _db, tenant_id, batch_id=None: select(GraduationStudent.id).where(
            GraduationStudent.tenant_id == tenant_id,
            GraduationStudent.batch_id == int(batch_id),
        ),
    )

    items, total = student_read.list_students(
        100,
        200,
        batch_id="17",
        keyword="2026",
        material_complete=False,
    )

    assert items == []
    assert total == 25000
    assert [kind for kind, _ in db.statements] == ["count", "page"]
    page_stmt = db.statements[1][1]
    assert page_stmt._limit_clause.value == 200
    assert page_stmt._offset_clause.value == 19800
