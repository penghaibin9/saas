"""岗位实习参与人冻结即启用的生产语义回归。"""
from __future__ import annotations

import uuid

TID = 1000000000000000001


def _user():
    return {"userId": "db-1", "realName": "实习管理员", "currentRoleCode": "SCHOOL_ADMIN"}


def test_freeze_preserves_plan_and_writes_canonical_activate(db_mode):
    """冻结名单启用批次时，计划人数不被实际人数覆盖，并留下正式 ACTIVATE 事实。"""
    from sqlalchemy import select

    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import InternshipAuditTrail, InternshipBatch, InternshipRecord, StudentProfile
    from app.models.org import College, Major, SchoolClass
    from app.modules.internship.services import internship_participant_service as svc

    suffix = uuid.uuid4().hex[:10]
    set_tenant({"tenantId": str(TID)})
    set_current_user(_user())
    db = get_sessionmaker()()
    try:
        college = College(
            tenant_id=TID, college_name=f"冻结契约学院-{suffix}", code=f"FC{suffix}", status="ACTIVE"
        )
        db.add(college); db.flush()
        major = Major(
            tenant_id=TID, college_id=college.id, major_name=f"冻结契约专业-{suffix}",
            code=f"FM{suffix}", status="ACTIVE"
        )
        db.add(major); db.flush()
        school_class = SchoolClass(
            tenant_id=TID, major_id=major.id, class_name=f"冻结契约班-{suffix}",
            class_code=f"FK{suffix}", grade="2026", status="ACTIVE"
        )
        db.add(school_class); db.flush()
        student = StudentProfile(
            tenant_id=TID, student_no=f"FC{suffix}", real_name="冻结契约学生",
            college_id=college.id, major_id=major.id, class_id=school_class.id, grade="2026",
            current_stage="ENROLLED", student_status="NORMAL", status="ACTIVE"
        )
        db.add(student); db.flush()
        batch = InternshipBatch(
            tenant_id=TID, batch_name=f"冻结启用契约-{suffix}", batch_no=f"FB{suffix}",
            status="DRAFT", planned_count=37,
            rules_config={"checkin": {"requireDaily": True, "geofenceRadiusM": 500}},
        )
        db.add(batch); db.flush()
        batch_id = int(batch.id)
        student_id = int(student.id)
        db.commit()
    finally:
        db.close()

    try:
        out = svc.freeze(batch_id, {"rule": {"studentIds": [student_id]}}, _user())
        assert out["batchStatus"] == "RUNNING"
        assert out["total"] == 1

        db = get_sessionmaker()()
        try:
            batch = db.get(InternshipBatch, batch_id)
            assert batch.status == "RUNNING"
            assert batch.previous_status == "DRAFT"
            assert int(batch.planned_count or 0) == 37
            assert batch.transition_reason == "冻结参与人名单并启用批次"
            assert (batch.rules_config or {}).get("_complianceFrozen") is True
            assert (batch.rules_config or {}).get("_frozenAt")

            records = db.scalars(select(InternshipRecord).where(
                InternshipRecord.tenant_id == TID,
                InternshipRecord.batch_id == batch_id,
                InternshipRecord.student_id == student_id,
                InternshipRecord.is_deleted.is_(False),
            )).all()
            assert len(records) == 1

            actions = [row.action for row in db.scalars(select(InternshipAuditTrail).where(
                InternshipAuditTrail.tenant_id == TID,
                InternshipAuditTrail.target_type == "BATCH",
                InternshipAuditTrail.target_id == batch_id,
            ).order_by(InternshipAuditTrail.id)).all()]
            assert "冻结参与人名单" in actions
            assert "ACTIVATE" in actions
            assert actions.index("冻结参与人名单") < actions.index("ACTIVATE")
        finally:
            db.close()
    finally:
        set_current_user(None)
        set_tenant(None)
