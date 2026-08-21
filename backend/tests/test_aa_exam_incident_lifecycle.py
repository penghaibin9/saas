"""W2 exam incident lifecycle: explicit resolution, scope, idempotency and finish gate."""
from __future__ import annotations

import inspect

import pytest

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _admin_headers(client):
    response = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['accessToken']}"}


def _student_headers():
    from app.core.security import create_access_token

    return {"Authorization": "Bearer " + create_access_token({
        "userId": "w2-student",
        "studentNo": "W2S001",
        "realName": "W2学生",
        "userType": "STUDENT",
        "tenantId": str(TID),
        "currentRoleCode": "STUDENT",
        "activeContextId": "w2-student-context",
    })}


def _other_tenant_admin_headers():
    from app.core.security import create_access_token

    return {"Authorization": "Bearer " + create_access_token({
        "userId": "w2-other-admin",
        "loginName": "w2_other_admin",
        "realName": "外租户管理员",
        "userType": "SCHOOL_ADMIN",
        "tenantId": str(TID + 99),
        "currentRoleCode": "SCHOOL_ADMIN",
        "activeContextId": "w2-other-context",
    })}


def _seed(db_mode):
    from datetime import datetime

    from app.db.session import get_sessionmaker
    from app.models import AaExamBatch, AaExamCourse, AaExamIncident, AaExamRoom

    db = get_sessionmaker()()
    try:
        batch = AaExamBatch(
            tenant_id=TID,
            batch_name="W2考务异常闭环验收",
            status="PUBLISHED",
        )
        db.add(batch)
        db.flush()
        course = AaExamCourse(
            tenant_id=TID,
            batch_id=batch.id,
            course_name="W2软件工程",
            class_name="W2-2601",
            status="CONFIRMED",
            exam_date="2029-06-21",
            start_time="09:00",
            end_time="11:00",
        )
        db.add(course)
        db.flush()
        room = AaExamRoom(
            tenant_id=TID,
            exam_course_id=course.id,
            room_seq=1,
            classroom_text="W2-A101",
            capacity=40,
            planned_count=0,
            seat_mode="SEQUENTIAL",
            source="MANUAL",
            status="ACTIVE",
        )
        db.add(room)
        db.flush()
        absent = AaExamIncident(
            tenant_id=TID,
            exam_room_id=room.id,
            exam_course_id=course.id,
            student_id=880001,
            student_no="W2A001",
            student_name="缺考待关闭",
            incident_type="ABSENT",
            description="缺考风险已经联动，但尚未由教务正式关闭",
            recorded_by="invigilator-w2",
            recorded_at=datetime(2029, 6, 21, 9, 30),
            risk_alert_sent=True,
            status="ACTIVE",
        )
        discipline = AaExamIncident(
            tenant_id=TID,
            exam_room_id=room.id,
            exam_course_id=course.id,
            student_id=880002,
            student_no="W2D002",
            student_name="违纪待移交",
            incident_type="DISCIPLINE_VIOLATION",
            description="考试中使用违规资料",
            recorded_by="invigilator-w2",
            recorded_at=datetime(2029, 6, 21, 9, 40),
            risk_alert_sent=False,
            status="ACTIVE",
        )
        other = AaExamIncident(
            tenant_id=TID,
            exam_room_id=room.id,
            exam_course_id=course.id,
            student_id=880003,
            student_no="W2O003",
            student_name="误登记待作废",
            incident_type="OTHER",
            description="监考误选学生",
            recorded_by="invigilator-w2",
            recorded_at=datetime(2029, 6, 21, 9, 45),
            risk_alert_sent=False,
            status="ACTIVE",
        )
        db.add_all([absent, discipline, other])
        db.commit()
        return {
            "batch": int(batch.id),
            "absent": int(absent.id),
            "discipline": int(discipline.id),
            "other": int(other.id),
        }
    finally:
        db.close()


def _workbench(client, headers, batch_id, view="ALL"):
    response = client.get(
        f"{BASE}/exam/incidents/workbench",
        headers=headers,
        params={"batchId": str(batch_id), "view": view, "page": 1, "pageSize": 50},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["code"] == 0, payload
    return payload["data"]


def _resolve(client, headers, incident_id, action, reason, case_ref=""):
    return client.post(
        f"{BASE}/exam/incidents/{incident_id}/resolve",
        headers=headers,
        json={
            "action": action,
            "reason": reason,
            "disciplineCaseRef": case_ref or None,
        },
    )


def test_risk_delivery_is_not_formal_close_and_finish_gate_waits_for_resolution(client, db_mode):
    ids = _seed(db_mode)
    admin = _admin_headers(client)

    before = _workbench(client, admin, ids["batch"])
    assert before["source"] == "CANONICAL_EXAM_INCIDENT_LIFECYCLE"
    assert before["openCount"] == 3
    assert before["closedCount"] == 0
    assert before["voidedCount"] == 0
    absent = next(row for row in before["items"] if row["incidentId"] == str(ids["absent"]))
    assert absent["riskAlertSent"] is True
    assert absent["closureStatus"] == "OPEN"
    assert absent["resolutionAction"] == ""

    blocked = client.post(f"{BASE}/exam/batches/{ids['batch']}/finish", headers=admin)
    assert blocked.status_code == 409, blocked.text
    assert "未闭环考场异常 3 条" in blocked.text


def test_close_handoff_void_are_server_authoritative_and_terminal(client, db_mode):
    ids = _seed(db_mode)
    admin = _admin_headers(client)

    close = _resolve(
        client,
        admin,
        ids["absent"],
        "CLOSE",
        "缺考风险已成功联动辅导员，确认完成考务侧闭环",
    )
    assert close.status_code == 200, close.text
    assert close.json()["data"]["closureStatus"] == "RISK_TRANSFERRED"

    handoff = _resolve(
        client,
        admin,
        ids["discipline"],
        "HANDOFF",
        "违纪事实已核验，移交学工处分流程继续处理",
        "DISC-W2-001",
    )
    assert handoff.status_code == 200, handoff.text
    assert handoff.json()["data"]["closureStatus"] == "CASE_LINKED"
    assert handoff.json()["data"]["disciplineCaseRef"] == "DISC-W2-001"

    voided = _resolve(
        client,
        admin,
        ids["other"],
        "VOID",
        "监考误选学生形成误登记，复核后正式作废保留历史",
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["data"]["closureStatus"] == "VOIDED"

    after = _workbench(client, admin, ids["batch"])
    assert after["openCount"] == 0
    assert after["closedCount"] == 2
    assert after["voidedCount"] == 1
    by_id = {row["incidentId"]: row for row in after["items"]}
    assert by_id[str(ids["absent"])]["resolutionAction"] == "CLOSE"
    assert "辅导员" in by_id[str(ids["absent"])]["resolutionReason"]
    assert by_id[str(ids["discipline"])]["resolutionAction"] == "HANDOFF"
    assert by_id[str(ids["discipline"])]["disciplineCaseRef"] == "DISC-W2-001"
    assert by_id[str(ids["other"])]["resolutionAction"] == "VOID"
    assert all(row["closureEvidenceConsistent"] is True for row in after["items"])

    # Every terminal mutation must re-read server truth; repeated/competing writes cannot overwrite it.
    repeat = _resolve(
        client,
        admin,
        ids["absent"],
        "VOID",
        "尝试覆盖已经正式关闭的缺考异常，应被状态机拒绝",
    )
    assert repeat.status_code == 409, repeat.text

    from app.db.session import get_sessionmaker
    from app.models import AaExamAuditTrail

    db = get_sessionmaker()()
    try:
        trails = db.query(AaExamAuditTrail).filter(
            AaExamAuditTrail.tenant_id == TID,
            AaExamAuditTrail.biz_type == "EXAM_INCIDENT",
            AaExamAuditTrail.biz_id == ids["absent"],
            AaExamAuditTrail.action.in_([
                "EXAM_INCIDENT_HANDOFF",
                "EXAM_INCIDENT_CLOSE",
                "EXAM_INCIDENT_VOID",
            ]),
        ).all()
        assert len(trails) == 1
        assert trails[0].action == "EXAM_INCIDENT_CLOSE"
        assert trails[0].before_val == "OPEN"
        assert trails[0].after_val == "RISK_TRANSFERRED"
    finally:
        db.close()

    # Once all three facts have a formal terminal event, the existing finish state machine may advance.
    finished = client.post(f"{BASE}/exam/batches/{ids['batch']}/finish", headers=admin)
    assert finished.status_code == 200, finished.text
    assert finished.json()["data"]["status"] == "FINISHED"


def test_view_pagination_and_terminal_history_are_queryable(client, db_mode):
    ids = _seed(db_mode)
    admin = _admin_headers(client)
    _resolve(client, admin, ids["absent"], "CLOSE", "缺考联动完成，确认关闭并保留正式审计")
    _resolve(client, admin, ids["discipline"], "HANDOFF", "违纪核验完成，移交处分线索继续办理", "DISC-W2-002")
    _resolve(client, admin, ids["other"], "VOID", "该条为误登记，复核后正式作废且不删除历史")

    opened = _workbench(client, admin, ids["batch"], "OPEN")
    assert opened["total"] == 0 and opened["items"] == []
    closed = _workbench(client, admin, ids["batch"], "CLOSED")
    assert closed["total"] == 2
    assert {row["closureStatus"] for row in closed["items"]} == {"RISK_TRANSFERRED", "CASE_LINKED"}
    voided = _workbench(client, admin, ids["batch"], "VOIDED")
    assert voided["total"] == 1
    assert voided["items"][0]["closureStatus"] == "VOIDED"


def test_resolve_requires_permission_and_is_tenant_scoped(client, db_mode):
    ids = _seed(db_mode)

    denied = _resolve(
        client,
        _student_headers(),
        ids["other"],
        "VOID",
        "学生端不能执行教务异常处置，必须由后端权限拒绝",
    )
    assert denied.status_code == 403, denied.text

    outsider = _resolve(
        client,
        _other_tenant_admin_headers(),
        ids["other"],
        "VOID",
        "其它租户不得通过可猜 ID 处置本租户考场异常",
    )
    assert outsider.status_code in {403, 404}, outsider.text

    admin = _admin_headers(client)
    still_open = _workbench(client, admin, ids["batch"], "OPEN")
    assert still_open["openCount"] == 3


def test_backend_lifecycle_source_has_row_lock_and_no_reopen_path():
    from app.modules.academic_affairs.services import academic_affairs_exam_incident_lifecycle_service as lifecycle

    source = inspect.getsource(lifecycle.resolve_incident)
    assert ".with_for_update()" in source
    assert "_latest_resolution_query" in source
    assert "APPROVAL_VERSION_CONFLICT" in source
    assert "EXAM_INCIDENT_" in source
    assert "reopen" not in source.lower()
    assert "status = \"ACTIVE\"" not in source


def test_resolve_body_requires_reason_at_router_contract():
    from app.modules.academic_affairs.routers.exam_incident_closure_router import IncidentResolveBody

    with pytest.raises(Exception):
        IncidentResolveBody(action="VOID", reason="短")
    accepted = IncidentResolveBody(action="VOID", reason="误登记复核后正式作废")
    assert accepted.reason == "误登记复核后正式作废"
