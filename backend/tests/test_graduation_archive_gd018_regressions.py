"""GD-018 archive gate regressions discovered by real Browser First audit."""
from __future__ import annotations

import uuid
from pathlib import Path

TID = 1000000000000000001


def _set_ctx():
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    set_current_user({
        "userId": "1", "tenantId": str(TID), "realName": "归档审计管理员",
        "currentRoleCode": "SCHOOL_ADMIN", "userType": "TEACHER", "activeContextId": "ctx",
    })


def _clear_ctx():
    from app.core.context import set_current_user, set_tenant

    set_current_user(None)
    set_tenant(None)


def test_gdr12_is_not_an_archive_blocker_but_other_open_risks_remain_blocking(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationRiskCase, GraduationStudent
    from app.modules.graduation.services.graduation_archive_service import _count_open_risks

    _set_ctx()
    db = get_sessionmaker()()
    try:
        suffix = uuid.uuid4().hex[:10].upper()
        student = GraduationStudent(
            tenant_id=TID, student_no=f"GD18-{suffix}", name="GD18风险门禁生",
            stage="COMPLETED", record_status="ACTIVE",
        )
        db.add(student)
        db.flush()
        db.add(GraduationRiskCase(
            tenant_id=TID, risk_code="GD-R12", risk_name="材料未归档",
            gd_student_id=int(student.id), level="HIGH", status="OPEN",
        ))
        db.commit()
        assert _count_open_risks(db, student) == 0

        db.add(GraduationRiskCase(
            tenant_id=TID, risk_code="GD-R06", risk_name="指导记录不足",
            gd_student_id=int(student.id), level="MEDIUM", status="OPEN",
        ))
        db.commit()
        assert _count_open_risks(db, student) == 1
    finally:
        db.close()
        _clear_ctx()


def test_gdr12_exclusion_and_system_snapshot_fallback_are_bound_to_batch_preview():
    root = Path(__file__).resolve().parents[2]
    scale = (root / "backend/app/modules/graduation/services/graduation_archive_batch_scale.py").read_text(encoding="utf-8")
    preview = (root / "backend/app/modules/graduation/services/graduation_archive_v2_preview.py").read_text(encoding="utf-8")

    assert '_ARCHIVE_NON_BLOCKING_RISK_CODES = ("GD-R12",)' in scale
    assert "GraduationRiskCase.risk_code.notin_(_ARCHIVE_NON_BLOCKING_RISK_CODES)" in scale
    assert "if material is not None and material.current_version_id:" in preview
    assert "elif item.material_code in _SYSTEM_SNAPSHOT_CODES:" in preview
    assert "present = _source_ready(" in preview
    assert "legacy_present, sid, guidance_ids, plagiarism, proposal_defense_ids" in preview
