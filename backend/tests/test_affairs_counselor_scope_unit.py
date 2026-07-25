"""辅导员责任关系：服务层同源 scope / TEMP 到期 / 待办迁移（绕过 HTTP 认证存储抖动）。"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

TID = 1000000000000000001


def _admin():
    return {
        "userId": "900001",
        "loginName": "school_admin01",
        "tenantId": str(TID),
        "currentRoleCode": "SCHOOL_ADMIN",
        "activeContextId": "role:admin",
        "permissionCodes": ["studentAffairs.class.view", "studentAffairs.class.create"],
    }


def _ensure_core_tables():
    """并发 DDL 环境下保证本用例所需表存在（幂等 create）。"""
    from app.db.base import metadata
    from app.db.session import get_engine
    from app.models import (AffairsCounselorAssignment, AffairsRiskRecord, College, Major,
                            SchoolClass, StudentProfile, TeacherStudentScope, UnifiedTodo, User)
    tables = [
        User.__table__, College.__table__, Major.__table__, SchoolClass.__table__,
        StudentProfile.__table__, TeacherStudentScope.__table__,
        AffairsCounselorAssignment.__table__, AffairsRiskRecord.__table__,
        UnifiedTodo.__table__,
    ]
    metadata.create_all(bind=get_engine(), tables=tables)


def _seed_entities(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import College, Major, SchoolClass, StudentProfile, User

    _ensure_core_tables()
    db = get_sessionmaker()()
    college = College(tenant_id=TID, college_name="同源学院", status="ACTIVE")
    db.add(college); db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name="同源专业", status="ACTIVE")
    db.add(major); db.flush()
    c = SchoolClass(tenant_id=TID, major_id=major.id, class_name="同源2601", status="ACTIVE")
    db.add(c); db.flush()
    s = StudentProfile(tenant_id=TID, student_no="TY001", real_name="同源生", class_id=c.id,
                       current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE")
    u1 = User(tenant_id=TID, login_name="ty_c1", real_name="辅导甲", password_hash="x",
              user_type="TEACHER", status="ACTIVE")
    u2 = User(tenant_id=TID, login_name="ty_c2", real_name="辅导乙", password_hash="x",
              user_type="TEACHER", status="ACTIVE")
    db.add_all([s, u1, u2]); db.commit()
    out = {"class_id": c.id, "student_id": s.id, "u1": u1.id, "u2": u2.id}
    db.close()
    return out


def test_primary_scope_sync_temp_expire_and_todo_migrate(db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AffairsRiskRecord, TeacherStudentScope, UnifiedTodo
    from app.services import affairs_counselor_service as svc

    ids = _seed_entities(db_mode)
    set_tenant({"tenantId": str(TID)})
    set_current_user(_admin())
    try:
        row = svc.assign(_admin(), ids["class_id"], ids["u1"], "PRIMARY", reason="首任")
        assert row["dutyType"] == "PRIMARY" and row["status"] == "ACTIVE"

        db = get_sessionmaker()()
        scopes = db.scalars(select(TeacherStudentScope).where(
            TeacherStudentScope.tenant_id == TID,
            TeacherStudentScope.ref_value == "同源2601",
            TeacherStudentScope.status == "ACTIVE",
            TeacherStudentScope.is_deleted.is_(False))).all()
        assert {x.teacher_key for x in scopes} == {"ty_c1"}
        db.add(UnifiedTodo(
            tenant_id=TID, source_module="student-affairs", source_biz_type="LEAVE",
            source_biz_id=8001, todo_type="LEAVE_APPROVAL", assignee_id=ids["u1"],
            student_id=ids["student_id"], title="请假", status="PENDING"))
        risk = AffairsRiskRecord(
            tenant_id=TID, student_id=ids["student_id"], source="UNIT_MIGRATE", source_ref_id=1,
            risk_level="MEDIUM", title="迁移风险", owner_id=ids["u1"], status="ASSIGNED")
        db.add(risk); db.commit()
        risk_id = risk.id
        db.close()

        moved = svc.handover(_admin(), ids["class_id"], ids["u1"], ids["u2"], "交接", int(row["version"]))
        assert moved["userId"] == str(ids["u2"])

        db = get_sessionmaker()()
        scopes2 = {x.teacher_key for x in db.scalars(select(TeacherStudentScope).where(
            TeacherStudentScope.tenant_id == TID, TeacherStudentScope.ref_value == "同源2601",
            TeacherStudentScope.status == "ACTIVE", TeacherStudentScope.is_deleted.is_(False))).all()}
        assert scopes2 == {"ty_c2"}
        todos = db.scalars(select(UnifiedTodo).where(
            UnifiedTodo.tenant_id == TID, UnifiedTodo.source_biz_id == 8001)).all()
        assert any(t.assignee_id == ids["u2"] and t.status == "PENDING" for t in todos)
        assert not any(t.assignee_id == ids["u1"] and t.status == "PENDING" for t in todos)
        assert db.get(AffairsRiskRecord, risk_id).owner_id == ids["u2"]
        db.close()

        past = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        start = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
        temp = svc.assign(_admin(), ids["class_id"], ids["u1"], "TEMP",
                         effective_from=start, effective_to=past, reason="过期代班")
        assert temp["status"] == "ENDED"
        assert svc.scan_expired_temps()["ended"] == 0
    finally:
        set_current_user(None)
        set_tenant(None)
