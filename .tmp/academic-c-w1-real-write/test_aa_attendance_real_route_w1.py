"""C-W1 focused real route write proof.

No mock-login, no service monkeypatch, no direct attendance-service invocation.
The business action traverses FastAPI -> auth context -> mobile facade/public service ->
ScopeHead/calendar occurrence authority -> versioned TeachingRoster -> MySQL.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.context import set_current_user, set_tenant
from app.core.security import create_access_token
from app.db.session import get_sessionmaker
from app.main import app
from app.models import (
    AaAttendanceSession,
    AaCourse,
    AaScheduleBatch,
    AaScheduleItem,
    AaTeachingClass,
    AaTeachingClassMember,
    AaTeachingClassRosterVersion,
    AaTeachingClassTeacher,
    AaTeachingTask,
    AaTeachingTaskBatch,
    AaTerm,
    SchoolClass,
    StudentProfile,
    Tenant,
)
from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot
from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as schedule_truth


TID = 1000000000000007311
TENANT_CODE = "cw1-route-school"
BASE = "/api/v1/mobile/teacher/academic/attendance"
TEACHER_KEY = "CW1-ROUTE-T1"


def _headers() -> dict:
    claims = {
        "userId": "u_CW1-ROUTE-T1",
        "loginName": TEACHER_KEY,
        "realName": "C-W1路由验收教师",
        "userType": "TEACHER",
        "currentRoleCode": "ACADEMIC_TEACHER",
        "clientType": "MP",
        "tid": TENANT_CODE,
        "tenantId": str(TID),
        "activeContextId": "ctx_CW1-ROUTE-T1",
    }
    return {"Authorization": "Bearer " + create_access_token(claims)}


def _ok(response, label: str) -> dict:
    assert response.status_code == 200, f"{label}: HTTP {response.status_code} {response.text}"
    payload = response.json()
    assert payload.get("code") == 0, f"{label}: {payload}"
    return payload.get("data") or {}


def _seed_authority() -> dict:
    # Seed the real tenant registry row as well as current academic authority facts.
    # POST routes traverse the production tenant lifecycle write guard; omitting t_tenant
    # would only prove that the guard correctly fails closed, not the attendance route.
    set_tenant({"tenantId": str(TID), "tenantCode": TENANT_CODE, "status": "ACTIVE"})
    set_current_user({
        "userId": "seed-cw1-route",
        "loginName": "seed-cw1-route",
        "realName": "C-W1路由验收种子",
        "currentRoleCode": "ACADEMIC_ADMIN",
        "tenantId": str(TID),
    })
    db = get_sessionmaker()()
    try:
        db.add(Tenant(
            id=TID,
            tenant_code=TENANT_CODE,
            school_name="C-W1路由验收学校",
            status="ACTIVE",
        ))
        db.flush()

        school_class = SchoolClass(
            tenant_id=TID,
            major_id=1,
            class_name="C-W1路由验收班",
            grade="2026",
            status="ACTIVE",
        )
        db.add(school_class)
        db.flush()

        student = StudentProfile(
            tenant_id=TID,
            student_no="CW1-ROUTE-S001",
            real_name="C-W1路由验收学生",
            class_id=school_class.id,
            current_stage="ON_CAMPUS",
            student_status="REGISTERED",
            status="ACTIVE",
        )
        db.add(student)
        db.flush()

        course = AaCourse(
            tenant_id=TID,
            course_code="CW1-ROUTE-C001",
            course_name="C-W1正式点名课",
            credit=2,
            status="ENABLED",
        )
        db.add(course)
        db.flush()

        term = AaTerm(
            tenant_id=TID,
            year_code="2026-2027",
            term_no=1,
            term_name="C-W1路由验收学期",
            start_date=datetime(2026, 3, 2),
            end_date=datetime(2026, 7, 5),
            teaching_weeks=18,
            is_current=True,
            status="PUBLISHED",
        )
        db.add(term)
        db.flush()

        task_batch = AaTeachingTaskBatch(
            tenant_id=TID,
            term_id=term.id,
            college_id=31,
            batch_name="C-W1路由验收教学任务批次",
            status="APPROVED",
        )
        db.add(task_batch)
        db.flush()

        task = AaTeachingTask(
            tenant_id=TID,
            batch_id=task_batch.id,
            course_id=course.id,
            course_code=course.course_code,
            course_name=course.course_name,
            teacher_key=TEACHER_KEY,
            teacher_name="C-W1路由验收教师",
            class_id=school_class.id,
            status="APPROVED",
            weekly_hours=2,
            total_hours=36,
            start_week=1,
            end_week=18,
            expected_students=1,
        )
        db.add(task)
        db.flush()

        teaching_class = AaTeachingClass(
            tenant_id=TID,
            teaching_task_id=task.id,
            term_id=term.id,
            course_id=course.id,
            class_code=f"CW1-ROUTE-TC-{task.id}",
            class_name="C-W1路由验收教学班",
            class_type="ADMIN",
            source_type="TEACHING_TASK",
            source_id=task.id,
            capacity=1,
            current_roster_version_no=0,
            roster_status="DRAFT",
            status="ACTIVE",
            source_snapshot_json="{}",
        )
        db.add(teaching_class)
        db.flush()

        digest = hashlib.sha256(str(student.id).encode("utf-8")).hexdigest()
        roster_version = AaTeachingClassRosterVersion(
            tenant_id=TID,
            teaching_class_id=teaching_class.id,
            version_no=1,
            source_type="ADMIN_CLASS",
            source_id=school_class.id,
            member_count=1,
            roster_hash=digest,
            status="LOCKED",
            reason="C-W1路由验收正式名单",
            locked_at=datetime(2026, 2, 20, 8, 0, 0),
            locked_by="seed-cw1-route",
        )
        db.add(roster_version)
        db.flush()
        db.add(AaTeachingClassMember(
            tenant_id=TID,
            teaching_class_id=teaching_class.id,
            roster_version_id=roster_version.id,
            student_id=student.id,
            source_type="ADMIN_CLASS",
            source_id=school_class.id,
            status="ACTIVE",
        ))
        db.add(AaTeachingClassTeacher(
            tenant_id=TID,
            teaching_class_id=teaching_class.id,
            teacher_key=TEACHER_KEY,
            teacher_name="C-W1路由验收教师",
            role_type="PRIMARY",
            status="ACTIVE",
        ))
        teaching_class.current_roster_version_id = roster_version.id
        teaching_class.current_roster_version_no = 1
        teaching_class.roster_status = "LOCKED"

        schedule_batch = AaScheduleBatch(
            tenant_id=TID,
            term_id=term.id,
            college_id=31,
            batch_name="C-W1路由验收正式课表",
            status="PUBLISHED",
        )
        db.add(schedule_batch)
        db.flush()
        schedule_item = AaScheduleItem(
            tenant_id=TID,
            batch_id=schedule_batch.id,
            task_id=task.id,
            course_id=course.id,
            course_name=course.course_name,
            teacher_key=TEACHER_KEY,
            teacher_name="C-W1路由验收教师",
            class_id=school_class.id,
            weekday=1,
            slot_no=2,
            start_week=1,
            end_week=18,
            week_parity="ALL",
            status="EFFECTIVE",
        )
        db.add(schedule_item)
        db.flush()

        head = schedule_truth.lock_scope_head(db, int(term.id), "COLLEGE", 31)
        head.active_batch_id = schedule_batch.id
        head.version = 4
        head.published_at = datetime(2026, 2, 21, 9, 0, 0)
        db.commit()
        return {
            "taskId": str(task.id),
            "classId": str(school_class.id),
            "studentId": str(student.id),
            "scheduleItemId": str(schedule_item.id),
            "rosterVersionId": str(roster_version.id),
        }
    finally:
        db.close()


def test_cw1_real_mobile_route_freezes_formal_occurrence_and_roster(db_mode):
    ids = _seed_authority()
    headers = _headers()

    with TestClient(app) as client:
        options = _ok(client.get(f"{BASE}/class-options", headers=headers), "class-options")
        task = next(row for row in options["items"] if row["teachingTaskId"] == ids["taskId"])
        assert task["formalOccurrenceReady"] is True
        assert task["formalScheduleStatus"] == "READY"
        assert len(task["formalSchedulePatterns"]) == 1
        pattern = task["formalSchedulePatterns"][0]
        assert pattern["scheduleItemId"] == ids["scheduleItemId"]
        assert pattern["slotNo"] == 2
        assert pattern["weekday"] == 1

        stale = client.post(f"{BASE}/sessions", headers=headers, json={
            "teachingTaskId": ids["taskId"],
            "classId": ids["classId"],
            "sessionDate": "2026-03-02",
            "slotNo": 2,
            "scheduleItemId": str(int(ids["scheduleItemId"]) + 99999),
            "sessionType": "常规",
        })
        assert stale.status_code == 409, stale.text
        assert stale.json().get("code") != 0

        created = _ok(client.post(f"{BASE}/sessions", headers=headers, json={
            "teachingTaskId": ids["taskId"],
            "classId": ids["classId"],
            "sessionDate": "2026-03-02",
            "slotNo": 2,
            "scheduleItemId": pattern["scheduleItemId"],
            "sessionType": "常规",
        }), "create formal attendance")
        assert created["sourceType"] == "FORMAL_TEACHING"
        assert created["status"] == "DRAFT"
        assert created["totalCount"] == 1
        assert created["occurrenceEvidence"]["scheduleItemId"] == ids["scheduleItemId"]
        assert created["occurrenceEvidence"]["scopeType"] == "COLLEGE"
        assert created["occurrenceEvidence"]["scopeHeadVersion"] == 4
        assert created["rosterIdentity"]["rosterVersionId"] == ids["rosterVersionId"]
        session_id = created["sessionId"]

        detail = _ok(client.get(f"{BASE}/sessions/{session_id}", headers=headers), "detail")
        assert detail["sourceType"] == "FORMAL_TEACHING"
        assert detail["rosterIdentity"]["rosterVersionId"] == ids["rosterVersionId"]
        assert len(detail["items"]) == 1
        assert detail["items"][0]["studentId"] == ids["studentId"]

        marked = _ok(client.post(f"{BASE}/sessions/{session_id}/mark", headers=headers, json={
            "studentId": ids["studentId"],
            "status": "ABSENT",
        }), "mark absent")
        assert marked["absentCount"] == 1
        assert marked["presentCount"] == 0

        submitted = _ok(client.post(f"{BASE}/sessions/{session_id}/submit", headers=headers), "submit")
        assert submitted["status"] == "SUBMITTED"

        final = _ok(client.get(f"{BASE}/sessions/{session_id}", headers=headers), "final detail")
        assert final["status"] == "SUBMITTED"
        assert final["items"][0]["status"] == "ABSENT"
        assert final["rosterIdentity"]["status"] == "ACTIVE"

    db = get_sessionmaker()()
    try:
        attendance = db.scalar(select(AaAttendanceSession).where(
            AaAttendanceSession.tenant_id == TID,
            AaAttendanceSession.id == int(session_id),
            AaAttendanceSession.is_deleted.is_(False),
        ))
        assert attendance is not None
        assert attendance.status == "SUBMITTED"
        assert attendance.session_date == "2026-03-02"
        assert int(attendance.slot_no or 0) == 2
        assert attendance.teacher_key == TEACHER_KEY

        snapshot = db.scalar(select(AaRosterConsumerSnapshot).where(
            AaRosterConsumerSnapshot.tenant_id == TID,
            AaRosterConsumerSnapshot.consumer_type == "ATTENDANCE_SESSION",
            AaRosterConsumerSnapshot.consumer_id == int(session_id),
            AaRosterConsumerSnapshot.status == "ACTIVE",
            AaRosterConsumerSnapshot.is_deleted.is_(False),
        ))
        assert snapshot is not None
        assert str(snapshot.roster_version_id) == ids["rosterVersionId"]
        assert int(snapshot.member_count or 0) == 1
    finally:
        db.close()
