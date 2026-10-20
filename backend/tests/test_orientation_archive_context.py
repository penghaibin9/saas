"""Real MySQL coverage for batch-scoped archives and closing/roster races."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from conftest import make_org_class
from test_affairs_security import _hdr


TID = 1000000000000000001
OTHER_TID = 1000000000000000002
BASE = "/api/v1/orientation"


def _seed_batches(_db_mode, count=2):
    from app.db.session import get_engine, get_sessionmaker
    from app.models import College, Major, OrientationBatch, SchoolClass
    from app.services.orientation_flow_service import ensure_published_flow_version

    assert get_engine().dialect.name == "mysql", "This concurrency contract requires real MySQL"
    class_id = int(make_org_class(TID))
    with get_sessionmaker()() as db:
        school_class = db.get(SchoolClass, class_id)
        major = db.get(Major, school_class.major_id)
        college = db.get(College, major.college_id)
        flow = ensure_published_flow_version(db, TID)
        batches = [OrientationBatch(
            tenant_id=TID, batch_no=f"ARCHIVE-CONTEXT-{index}",
            batch_name=f"归档验收批次{index}", year="2026", status="ACTIVE",
            flow_version_id=flow.id,
        ) for index in range(count)]
        db.add_all(batches)
        db.commit()
        return {
            "classId": str(class_id), "collegeName": college.college_name,
            "batches": [{"id": str(batch.id), "no": batch.batch_no, "name": batch.batch_name}
                        for batch in batches],
        }


def _create_student(client, headers, seeded):
    response = client.post(f"{BASE}/students", headers=headers, json={
        "name": "归档联调同学", "admissionNo": "ARCHIVE-RACE-STUDENT",
        "classId": seeded["classId"], "batchId": seeded["batches"][0]["id"],
    })
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_archive_batch_filter_precedes_pagination_and_keeps_tenant_context(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import OrientationArchive, OrientationBatch

    seeded = _seed_batches(db_mode)
    first, second = seeded["batches"]
    archive_ids = {first["id"]: [], second["id"]: []}
    # Deliberately interleave the batches so slicing before filtering is wrong.
    for index, batch in enumerate((first, second, first, second, first)):
        response = client.post(f"{BASE}/archives", headers=auth_headers, json={
            "archiveName": f"迎新归档-{index}", "batchNo": batch["no"],
        })
        assert response.status_code == 200, response.text
        archive_ids[batch["id"]].append(response.json()["data"]["id"])
    with get_sessionmaker()() as db:
        foreign = OrientationBatch(tenant_id=OTHER_TID, batch_no=first["no"],
                                   batch_name="另一学校同编号批次", status="DRAFT")
        shadow = OrientationArchive(tenant_id=OTHER_TID, archive_name="另一学校归档",
                                    batch_no=first["no"], status="PENDING")
        db.add_all([foreign, shadow]); db.commit()
        foreign_id = str(foreign.id)

    for batch in (first, second):
        expected_ids = list(reversed(archive_ids[batch["id"]]))
        for page, expected_id in enumerate(expected_ids, start=1):
            response = client.get(f"{BASE}/archives", headers=auth_headers, params={
                "batchId": batch["id"], "page": page, "pageSize": 1,
                "status": "PENDING", "keyword": "迎新归档",
            })
            assert response.status_code == 200, response.text
            data = response.json()["data"]
            assert data["total"] == len(expected_ids)
            assert len(data["items"]) == 1
            row = data["items"][0]
            assert row["id"] == expected_id
            assert row["batchId"] == batch["id"]
            assert row["batchName"] == batch["name"] and row["batchStatus"] == "ACTIVE"
        exhausted = client.get(f"{BASE}/archives", headers=auth_headers, params={
            "batchId": batch["id"], "page": len(expected_ids) + 1, "pageSize": 1,
        }).json()["data"]
        assert exhausted["items"] == [] and exhausted["total"] == len(expected_ids)

    for batch_id in ("999999999999999999", foreign_id):
        response = client.get(f"{BASE}/archives", headers=auth_headers, params={"batchId": batch_id})
        assert response.status_code == 200, response.text
        assert response.json()["data"]["items"] == []
        assert response.json()["data"]["total"] == 0
    all_rows = client.get(f"{BASE}/archives", headers=auth_headers).json()["data"]
    assert all_rows["total"] == 5


def test_only_school_scope_can_close_a_batch(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import OrientationAuditTrail, OrientationBatch, TeacherStudentScope

    seeded = _seed_batches(db_mode, count=1)
    batch_id = seeded["batches"][0]["id"]
    with get_sessionmaker()() as db:
        db.add(TeacherStudentScope(
            tenant_id=TID, teacher_key="college_admin01", teacher_name="学院管理老师",
            role_code="COLLEGE_ADMIN", scope_type="COLLEGE", ref_value=seeded["collegeName"],
            status="ACTIVE",
        ))
        db.commit()
    college_headers = _hdr(client, "college_admin01")
    denied = client.post(f"{BASE}/batches/{batch_id}/close", headers=college_headers)
    assert denied.status_code == 403 and denied.json()["bizCode"] == "NO_DATA_SCOPE", denied.text
    with get_sessionmaker()() as db:
        assert db.get(OrientationBatch, int(batch_id)).status == "ACTIVE"
        assert db.query(OrientationAuditTrail).filter_by(
            tenant_id=TID, biz_type="BATCH", biz_id=batch_id, action="结束迎新批次",
        ).count() == 0
    allowed = client.post(f"{BASE}/batches/{batch_id}/close", headers=auth_headers)
    assert allowed.status_code == 200 and allowed.json()["data"]["status"] == "CLOSED", allowed.text
    with get_sessionmaker()() as db:
        assert db.get(OrientationBatch, int(batch_id)).status == "CLOSED"
        assert db.query(OrientationAuditTrail).filter_by(
            tenant_id=TID, biz_type="BATCH", biz_id=batch_id, action="结束迎新批次",
        ).count() == 1


@pytest.mark.parametrize("roster_action", ["create", "resume"])
@pytest.mark.parametrize("first_action", ["roster", "close"])
def test_batch_close_serializes_with_roster_commands(
    client, auth_headers, db_mode, monkeypatch, roster_action, first_action,
):
    from sqlalchemy import event, select
    from app.db.session import get_engine, get_sessionmaker
    from app.models import OrientationAuditTrail, OrientationBatch, OrientationStudent
    from app.services import orientation_service as service

    seeded = _seed_batches(db_mode, count=1)
    batch_id = seeded["batches"][0]["id"]
    student = None
    if roster_action == "resume":
        student = _create_student(client, auth_headers, seeded)
        no_show = client.post(f"{BASE}/students/{student['id']}/disposition", headers=auth_headers, json={
            "status": "NO_SHOW", "reason": "已核实本批次暂不来校报到", "expectedVersion": student["version"],
        })
        assert no_show.status_code == 200, no_show.text
        student = no_show.json()["data"]

    def roster_command():
        if roster_action == "resume":
            return client.post(f"{BASE}/students/{student['id']}/disposition", headers=auth_headers, json={
                "status": "RESUME", "reason": "学生已联系学校申请恢复报到", "expectedVersion": student["version"],
            })
        return client.post(f"{BASE}/students", headers=auth_headers, json={
            "name": "归档联调同学", "admissionNo": "ARCHIVE-RACE-STUDENT",
            "classId": seeded["classId"], "batchId": batch_id,
        })

    def close_command():
        return client.post(f"{BASE}/batches/{batch_id}/close", headers=auth_headers)

    # Pause a genuine command before its commit while its batch lock is held.
    # The second command reaches its actual SQL query before the first is released.
    owner_paused, release_owner, waiter_reached_lock = Event(), Event(), Event()
    pause_action = "结束迎新批次" if first_action == "close" else (
        "新增新生记录" if roster_action == "create" else "调整报到安排")
    original_audit = service._audit

    def audit_gate(db, biz_type, biz_id, action, *args, **kwargs):
        row = original_audit(db, biz_type, biz_id, action, *args, **kwargs)
        if action == pause_action and not owner_paused.is_set():
            owner_paused.set()
            assert release_owner.wait(timeout=20), "Concurrent command did not reach the batch lock"
        return row

    def observe_waiter(_connection, _cursor, statement, _parameters, _context, _executemany):
        sql = statement.upper()
        if "SELECT" in sql and "T_ORIENTATION_BATCH" in sql and "FOR UPDATE" in sql:
            waiter_reached_lock.set()

    monkeypatch.setattr(service, "_audit", audit_gate)
    engine = get_engine()
    first_command, second_command = (roster_command, close_command) if first_action == "roster" else (close_command, roster_command)
    observing = False
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(first_command)
            try:
                assert owner_paused.wait(timeout=10), "First command did not reach its transactional audit"
                event.listen(engine, "before_cursor_execute", observe_waiter)
                observing = True
                second = pool.submit(second_command)
                assert waiter_reached_lock.wait(timeout=10), "Second command did not use the batch serialization lock"
            finally:
                release_owner.set()
            first_response, second_response = first.result(timeout=20), second.result(timeout=20)
    finally:
        if observing:
            event.remove(engine, "before_cursor_execute", observe_waiter)

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 400, second_response.text
    if first_action == "roster":
        assert "未办结" in second_response.json()["message"]
    else:
        assert ("已结束" if roster_action == "create" else "开放中") in second_response.json()["message"]
    with get_sessionmaker()() as db:
        batch = db.get(OrientationBatch, int(batch_id))
        rows = db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == TID, OrientationStudent.batch_id == int(batch_id),
            OrientationStudent.is_deleted.is_(False),
        )).all()
        assert batch.status == ("ACTIVE" if first_action == "roster" else "CLOSED")
        if first_action == "roster":
            assert len(rows) == 1 and rows[0].stage == "ADMITTED"
        elif roster_action == "create":
            assert rows == []
        else:
            assert len(rows) == 1 and rows[0].stage == "NO_SHOW"
        assert db.query(OrientationAuditTrail).filter_by(
            tenant_id=TID, biz_type="BATCH", biz_id=batch_id, action="结束迎新批次",
        ).count() == (1 if first_action == "close" else 0)

@pytest.mark.parametrize("batch_id", ["abc", "0", "-1", "1.5", " "])
def test_archive_batch_id_rejected_by_request_validation(client, auth_headers, batch_id):
    response = client.get(f"{BASE}/archives", headers=auth_headers, params={"batchId": batch_id})
    assert response.status_code == 400, response.text
    assert response.json()["bizCode"] == "VALIDATION_ERROR", response.text
