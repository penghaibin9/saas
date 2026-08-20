"""D-W0 Graduation batch list scale contract.

The batch page is a high-frequency read path during graduation season. Its counters must
stay data-scope safe without issuing one result query per batch or materializing every
student result row in Python.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import event

from app.modules.academic_affairs.services import academic_affairs_graduation_scope_guard as guard

TID = 1000000000000000001


def _ctx(scope_type, college_ids=()):
    return SimpleNamespace(scope_type=scope_type, college_ids=set(college_ids))


@pytest.mark.usefixtures("db_mode")
def test_graduation_batch_page_uses_constant_query_count(monkeypatch):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaGraduationAuditBatch, AaGraduationAuditResult, College, StudentProfile
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as grad_svc

    set_tenant({"tenantId": str(TID)})
    seed = get_sessionmaker()()
    try:
        college = College(
            tenant_id=TID,
            college_name="D-W0毕业批次规模学院",
            code="DW0-GRAD-BATCH-SCALE",
            status="ACTIVE",
        )
        seed.add(college)
        seed.flush()
        student = StudentProfile(
            tenant_id=TID,
            student_no="DW0SCALE001",
            real_name="毕业批次规模学生",
            college_id=college.id,
            student_status="REGISTERED",
            status="ACTIVE",
        )
        seed.add(student)
        seed.flush()
        batch_ids = []
        for index in range(4):
            batch = AaGraduationAuditBatch(
                tenant_id=TID,
                batch_name=f"D-W0毕业批次规模-{index}",
                grade_year="2026",
                status="PRECHECKED",
            )
            seed.add(batch)
            seed.flush()
            seed.add(AaGraduationAuditResult(
                tenant_id=TID,
                batch_id=batch.id,
                student_id=student.id,
                overall="SYSTEM_PASSED" if index % 2 == 0 else "SYSTEM_ABNORMAL",
                conclusion="GRADUATED" if index == 0 else None,
                status="ARCHIVED" if index == 0 else "SYSTEM_PASSED",
            ))
            batch_ids.append(int(batch.id))
        seed.commit()
        college_id = int(college.id)
        engine = seed.get_bind()
    finally:
        seed.close()

    guard.install(grad_svc)
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db: _ctx("COLLEGE", {college_id}))

    statements: list[str] = []

    def _capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = statement.lstrip().upper()
        if normalized.startswith("SELECT") and "T_AA_GRADUATION_AUDIT_" in normalized:
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", _capture)
    try:
        items, total = grad_svc.list_batches(
            {"currentRoleCode": "CUSTOM_GRAD_VIEW", "userType": "TEACHER"},
            page=1,
            page_size=50,
        )
    finally:
        event.remove(engine, "before_cursor_execute", _capture)
        set_tenant(None)

    assert total == 4
    assert {int(row["batchId"]) for row in items} == set(batch_ids)
    assert sum(row["total"] for row in items) == 4
    assert sum(row["passed"] for row in items) == 2
    assert sum(row["abnormal"] for row in items) == 2
    assert sum(row["concluded"] for row in items) == 1
    assert sum(row["archived"] for row in items) == 1
    assert len(statements) == 3, (
        "graduation batch list must stay constant-query: visible count + page + grouped counters; "
        f"actual business SELECTs={len(statements)}"
    )
