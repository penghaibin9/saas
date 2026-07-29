"""学工中心四端联动加固目标测试。

只覆盖本分支新增/修复的跨端契约，不运行教务、实习、毕设等无关模块。
测试数据库沿用仓库统一 MySQL db_mode 夹具，禁止 SQLite 替代。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

TID = 1000000000000000001
BASE = "/api/v1/student-affairs"
MB = "/api/v1/mobile"


def _hdr(client, login_name):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": login_name, "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _stu_token(real_name, student_no):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": real_name,
        "studentNo": student_no, "userType": "STUDENT",
        "tid": "x", "tenantId": str(TID),
        "activeContextId": "ctx", "currentRoleCode": "STUDENT",
        "clientType": "MP",
    })}


def _set_ctx(user):
    from app.core.context import set_current_user, set_tenant
    set_tenant({"tenantId": str(TID)})
    set_current_user(user)


def _clear_ctx():
    from app.core.context import set_current_user, set_tenant
    set_current_user(None)
    set_tenant(None)


def _seed_students(db_mode, *, prefix="FE4"):
    from datetime import datetime, timedelta
    from app.db.session import get_sessionmaker
    from app.models import (
        AffairsCounselorAssignment, College, Major, Role, SchoolClass,
        StudentProfile, TeacherStudentScope, User, UserRole,
    )
    db = get_sessionmaker()()

    def ensure_user(login_name, real_name, role_code, role_name):
        user = db.query(User).filter_by(tenant_id=TID, login_name=login_name).first()
        if user is None:
            user = User(
                tenant_id=TID, login_name=login_name, real_name=real_name,
                password_hash="test-hash", user_type="TEACHER", status="ACTIVE",
            )
            db.add(user)
            db.flush()
        role = db.query(Role).filter_by(tenant_id=TID, role_code=role_code).first()
        if role is None:
            role = Role(
                tenant_id=TID, role_code=role_code, role_name=role_name,
                role_type="SYSTEM", status="ACTIVE",
            )
            db.add(role)
            db.flush()
        if db.query(UserRole).filter_by(
            tenant_id=TID, user_id=user.id, role_id=role.id,
        ).first() is None:
            db.add(UserRole(
                tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE",
            ))
        return user

    counselor = ensure_user("counselor01", "王莉", "COUNSELOR", "辅导员")
    college_reviewer = ensure_user("fe_college01", "学院受理人", "COLLEGE_ADMIN", "学院管理员")
    ensure_user("fe_sa01", "学工处受理人", "STUDENT_AFFAIRS_ADMIN", "学工处管理员")
    college = College(
        tenant_id=TID, college_name=f"{prefix}学院", code=f"{prefix}-COL", status="ACTIVE",
    )
    db.add(college)
    db.flush()
    major = Major(
        tenant_id=TID, college_id=college.id, major_name=f"{prefix}专业",
        code=f"{prefix}-MAJ", status="ACTIVE",
    )
    db.add(major)
    db.flush()
    cls = SchoolClass(
        tenant_id=TID, major_id=major.id, class_name=f"{prefix}软件2401",
        grade="2024", counselor_id=counselor.id, status="ACTIVE",
    )
    db.add(cls)
    db.flush()
    one = StudentProfile(
        tenant_id=TID, student_no=f"{prefix}001", real_name="四端学生甲",
        class_id=cls.id, college_id=college.id, gender="M", current_stage="CAMPUS",
        student_status="NORMAL", status="ACTIVE",
    )
    two = StudentProfile(
        tenant_id=TID, student_no=f"{prefix}002", real_name="四端学生乙",
        class_id=cls.id, college_id=college.id, gender="M", current_stage="CAMPUS",
        student_status="NORMAL", status="ACTIVE",
    )
    db.add_all([one, two])
    db.flush()
    db.add_all([
        AffairsCounselorAssignment(
            tenant_id=TID, class_id=cls.id, user_id=counselor.id,
            duty_type="PRIMARY", status="ACTIVE",
            effective_from=datetime.utcnow() - timedelta(days=1),
        ),
        TeacherStudentScope(
            tenant_id=TID, teacher_key="counselor01", teacher_name="王莉",
            role_code="COUNSELOR", scope_type="CLASS", ref_value=cls.class_name,
            status="ACTIVE",
        ),
        TeacherStudentScope(
            tenant_id=TID, teacher_key=college_reviewer.login_name,
            teacher_name=college_reviewer.real_name, role_code="COLLEGE_ADMIN",
            scope_type="COLLEGE", ref_value=college.college_name, status="ACTIVE",
        ),
    ])
    ids = {
        "class": cls.id, "one": one.id, "two": two.id,
        "oneNo": one.student_no, "twoNo": two.student_no,
    }
    db.commit()
    db.close()
    return ids

def test_four_end_routes_registered(client, db_mode):
    paths = set(client.app.openapi().get("paths", {}))
    assert "/api/v1/mobile/affairs/leave/{leave_id}/editable" in paths
    assert "/api/v1/mobile/affairs/dorm/transfers" in paths
    assert "/api/v1/mobile/affairs/activities/{activity_id}/secure-checkin" in paths
    assert "/api/v1/mobile/teacher/affairs/appeals/{kind}/{appeal_id}/review" in paths
    assert "/api/v1/mobile/affairs/second-class/report" in paths


def test_student_leave_and_teacher_mobile_share_version_contract(client, db_mode):
    ids = _seed_students(db_mode, prefix="FE41")
    admin = _hdr(client, "school_admin01")
    counselor = _hdr(client, "counselor01")
    leave = client.post(f"{BASE}/leave", headers=admin, json={
        "studentId": str(ids["one"]), "leaveType": "PERSONAL",
        "startTime": "2026-08-01", "endTime": "2026-08-02",
        "reason": "回家处理家庭事务",
    }).json()["data"]
    leave_id = leave["id"]

    student_data = client.get(
        f"{MB}/affairs/leave/my",
        headers=_stu_token("四端学生甲", ids["oneNo"]),
    ).json()["data"]
    mine = next(x for x in student_data["items"] if str(x["leaveId"]) == str(leave_id))
    assert isinstance(mine["version"], int)

    pending = client.get(
        f"{MB}/teacher/affairs/leaves/pending", headers=counselor,
    ).json()["data"]["list"]
    row = next(x for x in pending if str(x["id"]) == str(leave_id))
    assert row["version"] == mine["version"]
    assert "APPROVE" in row["allowedActions"]

    missing = client.post(
        f"{MB}/teacher/affairs/leaves/{leave_id}/approve",
        headers=counselor, json={"comment": "同意"},
    )
    assert missing.status_code == 400
    assert missing.json()["bizCode"] == "VALIDATION_ERROR"

    ok = client.post(
        f"{MB}/teacher/affairs/leaves/{leave_id}/approve",
        headers=counselor, json={"comment": "同意", "version": row["version"]},
    )
    assert ok.status_code == 200 and ok.json()["code"] == 0


def test_named_student_scope_does_not_expand_to_whole_class(db_mode):
    from app.core.affairs_security import build_affairs_context
    from app.db.session import get_sessionmaker
    from app.models import TeacherStudentScope

    ids = _seed_students(db_mode, prefix="FE42")
    db = get_sessionmaker()()
    db.add(TeacherStudentScope(
        tenant_id=TID, teacher_key="only-one", teacher_name="逐生老师",
        role_code="COUNSELOR", scope_type="STUDENT", ref_value=ids["oneNo"],
        status="ACTIVE",
    ))
    db.commit()
    user = {
        "userId": "db-99001", "loginName": "only-one", "realName": "逐生老师",
        "userType": "TEACHER", "currentRoleCode": "COUNSELOR",
        "tenantId": str(TID), "permissions": ["studentAffairs.student.view"],
    }
    _set_ctx(user)
    try:
        ctx = build_affairs_context(user, db)
        assert ctx.scope_type == "STUDENT"
        assert int(ids["one"]) in ctx.student_ids
        assert int(ids["two"]) not in ctx.student_ids
        ctx.require_student(db, ids["one"])
        with pytest.raises(Exception):
            ctx.require_student(db, ids["two"])
    finally:
        db.close()
        _clear_ctx()


def test_mental_sensitive_detail_fails_closed_when_audit_db_fails(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import PsyReferral
    from app.services import audit_log

    ids = _seed_students(db_mode, prefix="FE43")
    db = get_sessionmaker()()
    referral = PsyReferral(
        tenant_id=TID, student_id=ids["one"], level="FOCUS",
        reason_summary="需要持续关注", note="强敏感心理明细",
        referrer="心理老师", status="REFERRED",
    )
    db.add(referral)
    db.commit()
    rid = referral.id
    db.close()

    monkeypatch.setattr(audit_log, "record", lambda *_args, **_kwargs: None)
    user = {
        "userId": "db-1", "loginName": "school_admin01", "realName": "学校管理员",
        "userType": "ADMIN", "currentRoleCode": "SCHOOL_ADMIN", "tenantId": str(TID),
    }
    _set_ctx(user)
    try:
        from app.services import affairs_mental_service as mental
        with pytest.raises(Exception) as exc:
            mental.get_referral(user, rid, reason="处理心理危机必须查看")
        assert getattr(exc.value, "http_status", None) == 503
    finally:
        _clear_ctx()


def test_existing_bed_cannot_bypass_transfer_approval(client, db_mode):
    ids = _seed_students(db_mode, prefix="FE44")
    admin = _hdr(client, "school_admin01")
    student = _stu_token("四端学生甲", ids["oneNo"])
    building_id = client.post(f"{BASE}/dorm/buildings", headers=admin, json={
        "buildingName": "四端1号楼", "genderLimit": "MALE",
        "floors": 1, "roomsPerFloor": 1, "bedsPerRoom": 2,
    }).json()["data"]["buildingId"]
    client.put(f"{BASE}/dorm/config/self-select", headers=admin, json={"enabled": True})
    rooms = client.get(
        f"{MB}/affairs/dorm/buildings/{building_id}/rooms", headers=student,
    ).json()["data"]["items"]
    beds = client.get(
        f"{MB}/affairs/dorm/rooms/{rooms[0]['roomId']}/beds", headers=student,
    ).json()["data"]["items"]
    first = client.post(
        f"{MB}/affairs/dorm/beds/{beds[0]['bedId']}/self-select", headers=student,
    )
    assert first.status_code == 200
    bypass = client.post(
        f"{MB}/affairs/dorm/beds/{beds[1]['bedId']}/self-select", headers=student,
    )
    assert bypass.status_code == 409
    options = client.get(f"{MB}/affairs/dorm/transfer-options", headers=student)
    assert options.status_code == 200 and options.json()["data"]["items"]


def test_dynamic_activity_code_replaces_student_manual_checkin(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AffairsActivity, AffairsActivitySignup

    ids = _seed_students(db_mode, prefix="FE45")
    db = get_sessionmaker()()
    activity = AffairsActivity(
        tenant_id=TID, activity_name="四端现场活动", activity_type="ACTIVITY",
        status="ONGOING", publisher_name="学工处",
    )
    db.add(activity)
    db.flush()
    db.add(AffairsActivitySignup(
        tenant_id=TID, activity_id=activity.id, student_id=ids["one"],
        signup_status="ENROLLED",
    ))
    db.commit()
    activity_id = activity.id
    db.close()

    admin = _hdr(client, "school_admin01")
    student = _stu_token("四端学生甲", ids["oneNo"])
    code_data = client.get(
        f"{MB}/teacher/affairs/activities/{activity_id}/checkin-token",
        headers=admin,
    ).json()["data"]
    assert len(code_data["checkinCode"]) == 6

    old = client.post(
        f"{MB}/affairs/activities/{activity_id}/checkin",
        headers=student, json={"method": "MANUAL"},
    )
    assert old.status_code == 400
    checked = client.post(
        f"{MB}/affairs/activities/{activity_id}/secure-checkin",
        headers=student, json={"token": code_data["checkinCode"]},
    )
    assert checked.status_code == 200 and checked.json()["data"]["signupStatus"] == "CHECKED_IN"


def test_aid_application_rolls_back_when_confirmation_record_fails(db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import AidApply, AidBatch, SchoolClass, StudentProfile
    from app.services import affairs_aid_service as aid
    from app.services import affairs_student_atomic_service as atomic
    from app.student_portal.services import common_service

    db = get_sessionmaker()()
    cls = SchoolClass(
        tenant_id=TID, major_id=1, class_name="FE46软件2401", grade="2024", status="ACTIVE",
    )
    db.add(cls)
    db.flush()
    student = StudentProfile(
        tenant_id=TID, student_no="FE46001", real_name="原子事务学生",
        class_id=cls.id, gender="F", current_stage="CAMPUS",
        student_status="NORMAL", status="ACTIVE",
    )
    batch = AidBatch(
        tenant_id=TID, batch_name="2026困难认定", year_code="2026-2027",
        publicity_days=3, status="OPEN",
    )
    db.add_all([student, batch])
    db.commit()
    sid, bid = student.id, batch.id
    db.close()

    monkeypatch.setattr(aid, "_assignee_for", lambda *_args, **_kwargs: 10001)
    monkeypatch.setattr(aid, "_open_wf", lambda *_args, **_kwargs: SimpleNamespace(id=90001))
    monkeypatch.setattr(aid, "_todo_upsert", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(aid, "_audit", lambda *_args, **_kwargs: None)

    def fail_confirmation(*_args, **_kwargs):
        raise RuntimeError("confirmation insert failed")

    monkeypatch.setattr(common_service, "create_sign_record_in_session", fail_confirmation)
    user = {
        "userId": f"u-FE46001", "realName": "原子事务学生", "studentNo": "FE46001",
        "userType": "STUDENT", "currentRoleCode": "STUDENT", "tenantId": str(TID),
    }
    _set_ctx(user)
    try:
        with pytest.raises(RuntimeError):
            atomic.aid_apply(user, {
                "batchId": str(bid), "applyLevel": "GENERAL",
                "statement": "家庭经济情况困难，需要申请认定支持",
                "memberCount": 3, "annualIncome": 20000, "confirm": True,
            })
    finally:
        _clear_ctx()
    db = get_sessionmaker()()
    assert db.scalars(select(AidApply).where(
        AidApply.tenant_id == TID, AidApply.student_id == sid, AidApply.batch_id == bid,
    )).first() is None
    db.close()
