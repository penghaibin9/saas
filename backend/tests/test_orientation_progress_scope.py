"""Progress and legacy student commands must share the stable profile scope."""
import pytest

from test_orientation_o3_self_service import TID, _seed_o3


def _records(db_mode, monkeypatch):
    from app.core import affairs_security as security
    from app.db.session import get_sessionmaker
    from app.models import OrientationStudent
    from app.services.orientation_flow_service import ensure_student_steps
    ids = _seed_o3(db_mode)
    with get_sessionmaker()() as db:
        own = db.get(OrientationStudent, ids["orientationId"])
        own.blocked_step = "INFO"
        others = [OrientationStudent(
            tenant_id=TID, batch_id=own.batch_id, student_id=profile_id,
            name="范围核验新生", admission_no="SCOPE-PROGRESS-" + str(index),
            source_type="MANUAL", source_record_id="SCOPE-PROGRESS-" + str(index),
            identity_status="LINKED" if profile_id else "UNLINKED", record_status="ACTIVE",
            blocked_step="INFO", blocked_reason="需要核实资料归属",
        ) for index, profile_id in enumerate([ids["otherProfileId"], None])]
        db.add_all(others); db.flush()
        for student in others:
            ensure_student_steps(db, student, status_source="PROCESS_FACT")
        result = own.id, [s.id for s in others], own.batch_id, own.student_id
        db.commit()
    ctx = security.StudentAffairsSecurityContext(
        user_id="scope-review", login_name="scope-review", tenant_id=TID,
        role_codes={"COUNSELOR"}, permission_codes=set(), sensitive_permissions=set(),
        scope_type="STUDENT", student_ids={result[3]}, is_scope_configured=True,
    )
    monkeypatch.setattr(security, "build_affairs_context", lambda user, db=None: ctx)
    return result, ctx


@pytest.mark.parametrize("method,suffix,body", [
    ("post", "students/{sid}/void", {"reason": "核实后作废该学生记录"}),
    ("put", "progress/{sid}/blocked", {"blockedStep": "INFO", "blockedReason": "需要补充核实身份资料"}),
    ("post", "progress/{sid}/resolve", {"note": "已经审核并登记豁免依据"}),
])
def test_student_commands_reject_foreign_and_unlinked_then_allow_own(
    client, db_mode, auth_headers, monkeypatch, method, suffix, body
):
    from app.db.session import get_sessionmaker
    from app.models import OrientationStudent
    (own, others, batch, profile), ctx = _records(db_mode, monkeypatch)
    for sid in others:
        response = getattr(client, method)("/api/v1/orientation/" + suffix.format(sid=sid),
                                           headers=auth_headers, json=body)
        assert response.status_code == 403, response.text
    with get_sessionmaker()() as db:
        for sid in others:
            row = db.get(OrientationStudent, sid)
            assert row.is_deleted is False
            assert row.blocked_reason == "需要核实资料归属"
    allowed = getattr(client, method)("/api/v1/orientation/" + suffix.format(sid=own),
                                      headers=auth_headers, json=body)
    assert allowed.status_code == 200, allowed.text


def test_progress_scope_filters_count_before_paging(client, db_mode, auth_headers, monkeypatch):
    (own, others, batch, profile), ctx = _records(db_mode, monkeypatch)
    url = "/api/v1/orientation/progress"
    scoped = client.get(url, headers=auth_headers, params={"batchId": batch, "pageSize": 1})
    assert scoped.status_code == 200, scoped.text
    data = scoped.json()["data"]
    assert data["total"] == 1 and data["items"][0]["id"] == str(own)
    ctx.student_ids.clear()
    assert client.get(url, headers=auth_headers, params={"batchId": batch}).json()["data"]["total"] == 0
    ctx.scope_type = "TENANT_ALL"
    second = client.get(url, headers=auth_headers, params={"batchId": batch, "pageSize": 1, "page": 2})
    assert second.status_code == 200, second.text
    data = second.json()["data"]
    assert data["total"] == 3
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(others[0])
