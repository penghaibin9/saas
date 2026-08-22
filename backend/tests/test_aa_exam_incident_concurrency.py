"""W2 concurrent exam-incident resolution: one terminal writer wins under row lock."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier

import pytest

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker

TID = 1000000000000000001


def _user(user_id: int, login: str) -> dict:
    return {
        "userId": str(user_id),
        "loginName": login,
        "realName": login,
        "userType": "SCHOOL_ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN",
    }


def _activate(user: dict) -> None:
    set_tenant({"tenantId": str(TID), "tenantCode": "demo"})
    set_current_user(user)


def _seed_incident() -> int:
    from app.models import AaExamBatch, AaExamCourse, AaExamIncident, AaExamRoom

    db = get_sessionmaker()()
    try:
        batch = AaExamBatch(
            tenant_id=TID,
            batch_name="W2并发终态验收",
            status="PUBLISHED",
        )
        db.add(batch)
        db.flush()
        course = AaExamCourse(
            tenant_id=TID,
            batch_id=batch.id,
            course_name="W2并发测试课程",
            class_name="W2-C01",
            status="CONFIRMED",
            exam_date="2029-06-22",
            start_time="09:00",
            end_time="11:00",
        )
        db.add(course)
        db.flush()
        room = AaExamRoom(
            tenant_id=TID,
            exam_course_id=course.id,
            room_seq=1,
            classroom_text="W2-C101",
            capacity=30,
            planned_count=1,
            seat_mode="SEQUENTIAL",
            source="MANUAL",
            status="ACTIVE",
        )
        db.add(room)
        db.flush()
        incident = AaExamIncident(
            tenant_id=TID,
            exam_room_id=room.id,
            exam_course_id=course.id,
            student_id=991001,
            student_no="W2CON001",
            student_name="并发处置学生",
            incident_type="ABSENT",
            description="风险已联动，两个管理员同时尝试不同终态",
            recorded_by="w2_invigilator",
            recorded_at=datetime(2029, 6, 22, 9, 30),
            risk_alert_sent=True,
            status="ACTIVE",
        )
        db.add(incident)
        db.commit()
        return int(incident.id)
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_concurrent_close_vs_void_has_exactly_one_terminal_audit():
    from app.models import AaExamAuditTrail, AaExamIncident
    from app.modules.academic_affairs.services import academic_affairs_exam_incident_lifecycle_service as lifecycle

    incident_id = _seed_incident()
    barrier = Barrier(2)

    def worker(action: str, user_id: int):
        user = _user(user_id, f"w2_reviewer_{user_id}")
        _activate(user)
        try:
            barrier.wait(timeout=5)
            return (
                "ok",
                lifecycle.resolve_incident(
                    user,
                    incident_id,
                    action,
                    reason=f"W2并发验收：管理员 {user_id} 尝试 {action} 终态",
                ),
            )
        except AppException as exc:
            return ("error", exc)
        finally:
            set_current_user(None)
            set_tenant(None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda args: worker(*args),
            [("CLOSE", 55101), ("VOID", 55102)],
        ))

    successes = [payload for status, payload in results if status == "ok"]
    errors = [payload for status, payload in results if status == "error"]
    assert len(successes) == 1, results
    assert len(errors) == 1, results
    assert errors[0].code in {"APPROVAL_VERSION_CONFLICT", "DATA_CONFLICT"}
    assert errors[0].http_status == 409

    db = get_sessionmaker()()
    try:
        incident = db.get(AaExamIncident, incident_id)
        trails = db.query(AaExamAuditTrail).filter(
            AaExamAuditTrail.tenant_id == TID,
            AaExamAuditTrail.biz_type == "EXAM_INCIDENT",
            AaExamAuditTrail.biz_id == incident_id,
            AaExamAuditTrail.action.in_([
                "EXAM_INCIDENT_HANDOFF",
                "EXAM_INCIDENT_CLOSE",
                "EXAM_INCIDENT_VOID",
            ]),
        ).order_by(AaExamAuditTrail.id).all()
        assert len(trails) == 1
        assert trails[0].before_val == "OPEN"
        assert trails[0].action in {"EXAM_INCIDENT_CLOSE", "EXAM_INCIDENT_VOID"}
        if trails[0].action == "EXAM_INCIDENT_CLOSE":
            assert trails[0].after_val == "RISK_TRANSFERRED"
            assert incident.status == "ACTIVE"
        else:
            assert trails[0].after_val == "VOIDED"
            assert incident.status == "VOIDED"
    finally:
        db.close()
