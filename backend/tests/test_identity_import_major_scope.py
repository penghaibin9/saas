"""Canonical teacher identity import must support official MAJOR-scoped roles."""
from __future__ import annotations

import io

from openpyxl import load_workbook

TID = 1000000000000000001


def test_teacher_template_exposes_major_scope():
    from app.services.identity_import_file_service import build_teacher_template

    wb = load_workbook(io.BytesIO(build_teacher_template()))
    try:
        ws = wb["导入模板"]
        formulas = [str(item.formula1 or "") for item in ws.data_validations.dataValidation]
        assert any("MAJOR" in formula for formula in formulas)
    finally:
        wb.close()


def test_major_scope_requires_reference():
    from app.services import school_onboarding_service as onboarding

    errors = onboarding._validate_rows({
        "teachers": [{
            "_rowNo": 2,
            "loginName": "major_import_missing_ref",
            "name": "专业毕设负责人",
            "roleCodes": "GD_MAJOR_ADMIN",
            "scopeType": "MAJOR",
            "scopeRef": "",
        }],
    })
    assert any(
        item.get("field") == "scopeRef" and "MAJOR" in str(item.get("error") or "")
        for item in errors
    )


def test_identity_import_persists_major_teacher_scope(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College, Major, TeacherStudentScope
    from app.services import school_onboarding_service as onboarding

    db = get_sessionmaker()()
    try:
        college = College(
            tenant_id=TID,
            college_name="身份导入MAJOR学院",
            status="ACTIVE",
        )
        db.add(college)
        db.flush()
        major = Major(
            tenant_id=TID,
            college_id=college.id,
            major_name="身份导入MAJOR专业",
            status="ACTIVE",
        )
        db.add(major)
        db.commit()
    finally:
        db.close()

    user = {
        "userId": "major-import-contract",
        "userType": "SCHOOL_ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN",
        "tenantId": str(TID),
    }
    body = {
        "tenantId": str(TID),
        "atomic": True,
        "teachers": [{
            "_rowNo": 2,
            "loginName": "major_import_contract",
            "name": "专业毕设负责人",
            "departmentName": "身份导入MAJOR学院",
            "positionName": "专业毕设负责人",
            "roleCodes": "GD_MAJOR_ADMIN",
            "scopeType": "MAJOR",
            "scopeRef": "身份导入MAJOR专业",
        }],
    }

    preview = onboarding.run_onboarding(user, body, dry_run=True, identity_channel=True)
    assert preview["errors"] == []

    result = onboarding.run_onboarding(user, body, dry_run=False, identity_channel=True)
    assert result["errors"] == []
    assert result["entities"]["scopes"]["created"] == 1

    db = get_sessionmaker()()
    try:
        row = db.query(TeacherStudentScope).filter_by(
            tenant_id=TID,
            teacher_key="major_import_contract",
            role_code="GD_MAJOR_ADMIN",
            scope_type="MAJOR",
            ref_value="身份导入MAJOR专业",
        ).one_or_none()
        assert row is not None
        assert row.status == "ACTIVE"
        assert row.is_deleted is False
    finally:
        db.close()
