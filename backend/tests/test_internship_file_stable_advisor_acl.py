"""Issue 7: internship file authorization uses stable advisor_user_id only."""
from __future__ import annotations

import inspect

import pytest

TID = 1000000000000000107
OTHER_TID = 1000000000000000108


def _teacher(uid: str, name: str = "同名指导老师") -> dict:
    return {
        "userId": uid,
        "realName": name,
        "name": name,
        "userType": "TEACHER",
        "tenantId": str(TID),
        "currentRoleCode": "TEACHER",
        "permissions": [],
    }


def test_db_prefixed_user_id_resolves_to_stable_advisor():
    from app.modules.internship.services.internship_identity import stable_user_id
    assert stable_user_id({"userId": "db-123"}) == 123
    assert stable_user_id({"userId": "u_456"}) == 456
    assert stable_user_id({"userId": "789"}) == 789
    assert stable_user_id({"userId": "teacher-name"}) is None
    assert stable_user_id({"userId": ""}) is None


def test_advisor_guard_uses_same_stable_identity_contract():
    from types import SimpleNamespace
    from app.modules.internship.services.internship_advisor_identity_guard import stable_advisor_matches
    row = SimpleNamespace(advisor_user_id=123, advisor_name="同名指导老师")
    assert stable_advisor_matches(row, _teacher("db-123")) is True
    assert stable_advisor_matches(row, _teacher("db-124")) is False
    legacy = SimpleNamespace(advisor_user_id=None, advisor_name="同名指导老师")
    assert stable_advisor_matches(legacy, _teacher("db-123")) is False


def test_file_resolver_source_has_no_advisor_name_authorization_fallback():
    from app.services.file_access_resolvers import _internship_staff_scope_allows
    source = inspect.getsource(_internship_staff_scope_allows)
    assert "stable_user_id(user)" in source
    assert "advisor_name" not in source
    assert "realName" not in source


def test_teacher_file_access_is_stable_id_only_and_cross_tenant_fail_closed(db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord, StudentProfile, Tenant
    from app.models.file import FileObject
    from app.services import file_access_resolvers  # noqa: F401 - registers authoritative resolvers
    from app.services.file_access_service import require_file_access
    from app.services.file_business_binding_service import bind_file_to_business

    set_tenant({"tenantId": str(TID), "tenantCode": "audit-d-stable-advisor"})
    seed_actor = _teacher("9001", "文件绑定老师")
    set_current_user(seed_actor)
    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, TID)
        if tenant is None:
            db.add(Tenant(
                id=TID,
                tenant_code="audit-d-stable-advisor",
                school_name="稳定导师文件授权测试学校",
                short_name="稳定导师ACL",
                deploy_mode="SAAS",
                db_mode="SHARED",
                status="ACTIVE",
            ))
            db.flush()
        student = StudentProfile(
            tenant_id=TID,
            student_no="AUDIT-D-FILE-001",
            real_name="文件授权学生",
            current_stage="INTERNSHIP",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add(student)
        db.flush()
        record = InternshipRecord(
            tenant_id=TID,
            student_id=student.id,
            advisor_user_id=None,
            advisor_name="同名指导老师",
            status="PREPARING",
            eligibility_status="QUALIFIED",
            destination_type="NONE",
            risk_level="NONE",
        )
        db.add(record)
        db.flush()
        file_obj = FileObject(
            tenant_id=TID,
            file_key="audit-d/stable-advisor.pdf",
            file_name="stable-advisor.pdf",
            ext="pdf",
            mime_type="application/pdf",
            size_bytes=10,
            sha256="d" * 64,
            biz_type="TEMP_PRIVATE",
            biz_id=None,
            owner_user_id=9001,
            visibility="PRIVATE",
            status="AVAILABLE",
            storage_backend="local",
            storage_zone="ACTIVE",
            upload_source="USER",
            scan_required=False,
            scan_status="NOT_REQUIRED",
        )
        db.add(file_obj)
        db.flush()
        bind_file_to_business(
            db,
            file_id=file_obj.id,
            biz_type="INTERNSHIP",
            biz_id=str(record.id),
            actor=seed_actor,
            subject_type="BUSINESS_OBJECT",
            subject_id=str(record.id),
            module_code="INTERNSHIP",
            student_id=student.id,
            scope={"internshipId": str(record.id), "studentId": str(student.id)},
        )
        db.commit()
        file_id = str(file_obj.id)

        # Legacy history with only the same display name must be invisible (404).
        with pytest.raises(AppException) as legacy_exc:
            require_file_access(file_id, user=_teacher("db-123"), action="download")
        assert legacy_exc.value.http_status == 404

        # Same display name but another stable advisor ID is also denied.
        db = get_sessionmaker()()
        row = db.get(InternshipRecord, record.id)
        row.advisor_user_id = 456
        db.commit()
        db.close()
        with pytest.raises(AppException) as wrong_id_exc:
            require_file_access(file_id, user=_teacher("db-123"), action="download")
        assert wrong_id_exc.value.http_status == 404

        # The exact stable DB identity can read the bound internship file.
        allowed = require_file_access(file_id, user=_teacher("db-456"), action="download")
        assert str(allowed.id) == file_id

        # Cross-tenant callers cannot enumerate the file even with the same stable ID.
        set_tenant({"tenantId": str(OTHER_TID), "tenantCode": "other-tenant"})
        with pytest.raises(AppException) as cross_tenant_exc:
            require_file_access(file_id, user={**_teacher("db-456"), "tenantId": str(OTHER_TID)}, action="download")
        assert cross_tenant_exc.value.http_status == 404
    finally:
        try:
            db.close()
        except Exception:
            pass
        set_current_user(None)
        set_tenant(None)
