"""D-W0 Graduation read data-scope contract.

Permission grants and organization data scope are independent authorities. Tenant-defined
roles with graduation.view must never inherit tenant-wide visibility merely because their
role code is unknown to the Graduation service.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.academic_affairs.services import academic_affairs_graduation_scope_guard as guard

TID = 1000000000000000001


def _ctx(scope_type, college_ids=()):
    return SimpleNamespace(scope_type=scope_type, college_ids=set(college_ids))


def test_tenant_all_scope_stays_unrestricted(monkeypatch):
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db: _ctx("TENANT_ALL"))
    assert guard.graduation_college_scope_ids(object(), {"currentRoleCode": "ACADEMIC_ADMIN"}) is None


def test_custom_college_scope_uses_shared_context(monkeypatch):
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db: _ctx("COLLEGE", {21, 22}))
    assert guard.graduation_college_scope_ids(object(), {"currentRoleCode": "CUSTOM_GRAD_VIEW"}) == {21, 22}


@pytest.mark.parametrize("scope_type", ["NONE", "CLASS", "STUDENT", "SELF", "DORM_BUILDING"])
def test_non_college_custom_scope_never_falls_back_to_tenant_all(monkeypatch, scope_type):
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db: _ctx(scope_type, {99}))
    assert guard.graduation_college_scope_ids(object(), {"currentRoleCode": "CUSTOM_GRAD_VIEW"}) == set()


def test_public_graduation_router_installs_scope_guard():
    from app.modules.academic_affairs.routers import graduation_core_router

    installed = graduation_core_router.grad_svc._college_scope_ids
    assert getattr(installed, "_graduation_scope_guard", False) is True
    assert getattr(graduation_core_router.grad_svc.list_batches, "_graduation_scope_guard", False) is True


@pytest.mark.usefixtures("db_mode")
def test_custom_college_scope_resolves_real_teacher_scope_row():
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import College, TeacherStudentScope

    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        college = College(
            tenant_id=TID,
            college_name="D-W0自定义毕业审核范围学院",
            code="DW0-GRAD-SCOPE-COL",
            status="ACTIVE",
        )
        db.add(college)
        db.flush()
        db.add(TeacherStudentScope(
            tenant_id=TID,
            teacher_key="dw0_custom_grad_view",
            teacher_name="自定义毕业审核员",
            role_code="CUSTOM_GRAD_VIEW",
            scope_type="COLLEGE",
            ref_value=college.college_name,
            status="ACTIVE",
        ))
        db.commit()

        scoped_user = {
            "loginName": "dw0_custom_grad_view",
            "realName": "自定义毕业审核员",
            "userType": "TEACHER",
            "currentRoleCode": "CUSTOM_GRAD_VIEW",
            "tenantId": str(TID),
        }
        assert guard.graduation_college_scope_ids(db, scoped_user) == {int(college.id)}

        no_scope_user = {
            "loginName": "dw0_custom_grad_no_scope",
            "realName": "未配置范围审核员",
            "userType": "TEACHER",
            "currentRoleCode": "CUSTOM_GRAD_VIEW",
            "tenantId": str(TID),
        }
        assert guard.graduation_college_scope_ids(db, no_scope_user) == set()
    finally:
        db.close()
        set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_college_scope_filters_batch_visibility_and_aggregates(monkeypatch):
    """Batch counters are student data and must not leak another college's rows."""
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AaGraduationAuditBatch, AaGraduationAuditResult, College, StudentProfile
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as grad_svc

    set_tenant({"tenantId": str(TID)})
    db = get_sessionmaker()()
    try:
        college_a = College(
            tenant_id=TID,
            college_name="D-W0批次范围学院A",
            code="DW0-BATCH-SCOPE-A",
            status="ACTIVE",
        )
        college_b = College(
            tenant_id=TID,
            college_name="D-W0批次范围学院B",
            code="DW0-BATCH-SCOPE-B",
            status="ACTIVE",
        )
        db.add_all([college_a, college_b])
        db.flush()
        student_a = StudentProfile(
            tenant_id=TID,
            student_no="DW0BATCHA",
            real_name="批次范围学生A",
            college_id=college_a.id,
            student_status="REGISTERED",
            status="ACTIVE",
        )
        student_b = StudentProfile(
            tenant_id=TID,
            student_no="DW0BATCHB",
            real_name="批次范围学生B",
            college_id=college_b.id,
            student_status="REGISTERED",
            status="ACTIVE",
        )
        db.add_all([student_a, student_b])
        db.flush()
        shared = AaGraduationAuditBatch(
            tenant_id=TID,
            batch_name="D-W0共享毕业审核批次",
            grade_year="2026",
            status="PRECHECKED",
        )
        foreign_only = AaGraduationAuditBatch(
            tenant_id=TID,
            batch_name="D-W0外院毕业审核批次",
            grade_year="2026",
            status="PRECHECKED",
        )
        db.add_all([shared, foreign_only])
        db.flush()
        db.add_all([
            AaGraduationAuditResult(
                tenant_id=TID,
                batch_id=shared.id,
                student_id=student_a.id,
                overall="SYSTEM_PASSED",
                status="SYSTEM_PASSED",
            ),
            AaGraduationAuditResult(
                tenant_id=TID,
                batch_id=shared.id,
                student_id=student_b.id,
                overall="SYSTEM_ABNORMAL",
                status="SYSTEM_ABNORMAL",
            ),
            AaGraduationAuditResult(
                tenant_id=TID,
                batch_id=foreign_only.id,
                student_id=student_b.id,
                overall="SYSTEM_PASSED",
                status="SYSTEM_PASSED",
            ),
        ])
        db.commit()
        shared_id = int(shared.id)
        college_a_id = int(college_a.id)
    finally:
        db.close()

    guard.install(grad_svc)
    monkeypatch.setattr(guard, "build_affairs_context", lambda _user, _db: _ctx("COLLEGE", {college_a_id}))
    try:
        items, total = grad_svc.list_batches(
            {"currentRoleCode": "CUSTOM_GRAD_VIEW", "userType": "TEACHER"},
            page=1,
            page_size=50,
        )
        assert total == 1
        assert [row["batchId"] for row in items] == [str(shared_id)]
        assert items[0]["total"] == 1
        assert items[0]["passed"] == 1
        assert items[0]["abnormal"] == 0
    finally:
        set_tenant(None)
