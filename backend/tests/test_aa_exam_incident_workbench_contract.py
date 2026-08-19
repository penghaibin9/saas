from __future__ import annotations

from datetime import datetime

import pytest

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _admin_headers(client):
    response = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaExamAuditTrail, AaExamBatch, AaExamCourse, AaExamIncident, AaExamRoom

    db = get_sessionmaker()()
    batch = AaExamBatch(tenant_id=TID, batch_name="C-W3异常工作台", status="PUBLISHED")
    db.add(batch)
    db.flush()
    course = AaExamCourse(
        tenant_id=TID,
        batch_id=batch.id,
        course_name="C-W3异常课程",
        class_name="C-W3-2801",
        college_id=None,
        exam_date="2029-01-19",
        start_time="09:00",
        end_time="11:00",
        status="CONFIRMED",
    )
    db.add(course)
    db.flush()
    room = AaExamRoom(
        tenant_id=TID,
        exam_course_id=course.id,
        room_seq=1,
        classroom_text="C-W3-601",
        capacity=30,
        planned_count=4,
        seat_mode="SEQUENTIAL",
        source="MANUAL",
        status="ACTIVE",
    )
    db.add(room)
    db.flush()

    closed_absent = AaExamIncident(
        tenant_id=TID,
        exam_room_id=room.id,
        exam_course_id=course.id,
        student_id=910001,
        student_no="CW3I001",
        student_name="缺考已联动",
        incident_type="ABSENT",
        description="正式缺考",
        recorded_by="cw3_invigilator",
        recorded_at=datetime(2029, 1, 19, 9, 30),
        risk_alert_sent=True,
        status="ACTIVE",
    )
    handed_off = AaExamIncident(
        tenant_id=TID,
        exam_room_id=room.id,
        exam_course_id=course.id,
        student_id=910002,
        student_no="CW3I002",
        student_name="违纪已移交",
        incident_type="CHEAT",
        description="携带违规资料",
        recorded_by="cw3_invigilator",
        recorded_at=datetime(2029, 1, 19, 9, 40),
        risk_alert_sent=False,
        discipline_case_ref="DISC-CW3-001",
        status="ACTIVE",
    )
    voided = AaExamIncident(
        tenant_id=TID,
        exam_room_id=room.id,
        exam_course_id=course.id,
        student_id=910003,
        student_no="CW3I003",
        student_name="误登记已作废",
        incident_type="OTHER",
        description="误登记",
        recorded_by="cw3_invigilator",
        recorded_at=datetime(2029, 1, 19, 9, 50),
        risk_alert_sent=False,
        status="VOIDED",
    )
    open_incident = AaExamIncident(
        tenant_id=TID,
        exam_room_id=room.id,
        exam_course_id=course.id,
        student_id=910004,
        student_no="CW3I004",
        student_name="待处理违纪",
        incident_type="DISCIPLINE",
        description="待移交处理",
        recorded_by="cw3_invigilator",
        recorded_at=datetime(2029, 1, 19, 10, 0),
        risk_alert_sent=False,
        status="ACTIVE",
    )
    db.add_all([closed_absent, handed_off, voided, open_incident])
    db.flush()
    db.add_all([
        AaExamAuditTrail(
            tenant_id=TID,
            biz_type="EXAM_INCIDENT",
            biz_id=closed_absent.id,
            action="EXAM_INCIDENT_CLOSE",
            operator="school_admin01",
            role_name="SCHOOL_ADMIN",
            detail="closure=RISK_TRANSFERRED;caseRef=;reason=缺考风险已转辅导员跟进",
            occurred_at=datetime(2029, 1, 19, 12, 0),
        ),
        AaExamAuditTrail(
            tenant_id=TID,
            biz_type="EXAM_INCIDENT",
            biz_id=handed_off.id,
            action="EXAM_INCIDENT_HANDOFF",
            operator="school_admin01",
            role_name="SCHOOL_ADMIN",
            detail="closure=CASE_LINKED;caseRef=DISC-CW3-001;reason=移交学工处分流程",
            occurred_at=datetime(2029, 1, 19, 12, 10),
        ),
        AaExamAuditTrail(
            tenant_id=TID,
            biz_type="EXAM_INCIDENT",
            biz_id=voided.id,
            action="EXAM_INCIDENT_VOID",
            operator="school_admin01",
            role_name="SCHOOL_ADMIN",
            detail="closure=VOIDED;caseRef=;reason=监考老师误点学生",
            occurred_at=datetime(2029, 1, 19, 12, 20),
        ),
    ])

    draft_batch = AaExamBatch(tenant_id=TID, batch_name="C-W3未发布异常", status="ARRANGED")
    db.add(draft_batch)
    db.flush()
    draft_course = AaExamCourse(
        tenant_id=TID,
        batch_id=draft_batch.id,
        course_name="未发布课程",
        status="CONFIRMED",
    )
    db.add(draft_course)
    db.flush()
    db.add(AaExamIncident(
        tenant_id=TID,
        exam_course_id=draft_course.id,
        student_id=919999,
        incident_type="OTHER",
        description="不应进入正式异常工作台",
        risk_alert_sent=False,
        status="ACTIVE",
    ))
    db.commit()
    ids = {"batch": int(batch.id)}
    db.close()
    return ids


def test_incident_workbench_keeps_closed_voided_and_open_history(client, db_mode):
    ids = _seed(db_mode)
    admin = _admin_headers(client)

    response = client.get(f"{BASE}/exam/incidents/workbench", headers=admin)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["source"] == "CANONICAL_EXAM_INCIDENT_FACTS"
    assert data["total"] == 4
    assert data["openCount"] == 1
    assert data["closedCount"] == 2
    assert data["voidedCount"] == 1
    assert {item["batchId"] for item in data["items"]} == {str(ids["batch"])}

    by_name = {item["studentName"]: item for item in data["items"]}
    assert by_name["缺考已联动"]["closureStatus"] == "RISK_TRANSFERRED"
    assert by_name["缺考已联动"]["riskAlertSent"] is True
    assert by_name["缺考已联动"]["resolutionAction"] == "CLOSE"
    assert by_name["缺考已联动"]["resolutionReason"] == "缺考风险已转辅导员跟进"
    assert by_name["缺考已联动"]["resolvedBy"] == "school_admin01"
    assert by_name["缺考已联动"]["closureEvidenceConsistent"] is True

    assert by_name["违纪已移交"]["closureStatus"] == "CASE_LINKED"
    assert by_name["违纪已移交"]["disciplineCaseRef"] == "DISC-CW3-001"
    assert by_name["违纪已移交"]["resolutionAction"] == "HANDOFF"
    assert by_name["误登记已作废"]["status"] == "VOIDED"
    assert by_name["误登记已作废"]["closureStatus"] == "VOIDED"
    assert by_name["待处理违纪"]["closureStatus"] == "OPEN"


def _assert_scope_counts(data):
    assert data["openCount"] == 1
    assert data["closedCount"] == 2
    assert data["voidedCount"] == 1


def test_incident_workbench_view_filters_after_canonical_closure_projection(client, db_mode):
    _seed(db_mode)
    admin = _admin_headers(client)

    opened = client.get(f"{BASE}/exam/incidents/workbench?view=OPEN", headers=admin).json()["data"]
    assert opened["total"] == 1
    assert opened["items"][0]["studentName"] == "待处理违纪"
    _assert_scope_counts(opened)

    closed = client.get(f"{BASE}/exam/incidents/workbench?view=CLOSED", headers=admin).json()["data"]
    assert closed["total"] == 2
    assert {item["closureStatus"] for item in closed["items"]} == {"CASE_LINKED", "RISK_TRANSFERRED"}
    _assert_scope_counts(closed)

    voided = client.get(f"{BASE}/exam/incidents/workbench?view=VOIDED", headers=admin).json()["data"]
    assert voided["total"] == 1
    assert voided["items"][0]["closureStatus"] == "VOIDED"
    _assert_scope_counts(voided)


def test_incident_workbench_is_read_only_and_student_fails_closed(db_mode):
    import inspect
    from app.core.exceptions import AppException
    from app.db.session import get_sessionmaker
    from app.modules.academic_affairs.services import academic_affairs_exam_incident_workbench_service as workbench

    source = inspect.getsource(workbench.project_incident_workbench)
    for forbidden in (
        "db.add(",
        "db.flush(",
        "db.commit(",
        "record_incident(",
        "resolve_incident(",
    ):
        assert forbidden not in source

    db = get_sessionmaker()()
    with pytest.raises(AppException) as exc:
        workbench.project_incident_workbench(
            db,
            {"userType": "STUDENT", "userId": "student-cw3"},
        )
    assert exc.value.code in {"NO_DATA_SCOPE", "NO_PERMISSION"}
    db.close()
