"""正式考场逐生到考：仅冻结座位、准确责任范围、版本与封存并发。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from tests.test_aa_exam import BASE, TID, _batch_with_confirmed_course, _hdr, _seed


def _published_room(client, db_mode, *, publish=True):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    bid, cid = _batch_with_confirmed_course(client, admin, ids["tt1"], term_id=ids["term"])
    room = client.post(f"{BASE}/exam/courses/{cid}/rooms", headers=admin,
                       json={"classroomText": "A101", "capacity": 50})
    assert room.status_code == 200, room.text
    rid = room.json()["data"]["examRoomId"]
    seats = client.post(f"{BASE}/exam/rooms/{rid}/seats", headers=admin,
                        json={"studentIds": [str(ids["s1"]), str(ids["s2"])]})
    assert seats.status_code == 200, seats.text
    invigilator = client.post(f"{BASE}/exam/rooms/{rid}/invigilators", headers=admin,
                              json={"teacherKey": "teacher_a", "teacherName": "甲老师"})
    assert invigilator.status_code == 200, invigilator.text
    if publish:
        result = client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin)
        assert result.status_code == 200, result.text
    return ids, admin, bid, cid, rid


def _mark(client, headers, room_id, student_id, version=0):
    return client.put(f"{BASE}/exam/rooms/{room_id}/attendance/{student_id}", headers=headers,
                      json={"expectedVersion": version, "status": "PRESENT"})


def test_exam_attendance_marks_real_seats_once_and_unblocks_finish(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaExamAuditTrail, AaExamRoomStudent

    ids, admin, bid, _cid, rid = _published_room(client, db_mode)
    roster = client.get(f"{BASE}/exam/rooms/{rid}/attendance", headers=admin)
    assert roster.status_code == 200, roster.text
    data = roster.json()["data"]
    assert data["examRoomId"] == rid and data["batchId"] == bid and data["batchStatus"] == "PUBLISHED"
    assert {row["studentId"] for row in data["items"]} == {str(ids["s1"]), str(ids["s2"])}
    assert all(row["attendanceStatus"] == "NOT_STARTED" and row["version"] == 0
               and row["markPresentAction"]["allowed"] for row in data["items"])

    first = _mark(client, admin, rid, ids["s1"])
    assert first.status_code == 200, first.text
    assert first.json()["data"]["attendanceStatus"] == "PRESENT"
    assert first.json()["data"]["version"] == 1
    assert _mark(client, admin, rid, ids["s1"]).status_code == 409
    assert client.post(f"{BASE}/exam/batches/{bid}/finish", headers=admin).status_code == 409
    assert _mark(client, admin, rid, ids["s2"]).status_code == 200
    assert client.post(f"{BASE}/exam/batches/{bid}/finish", headers=admin).status_code == 200
    assert client.post(f"{BASE}/exam/batches/{bid}/archive", headers=admin).status_code == 200
    assert _mark(client, admin, rid, ids["s2"], version=1).status_code == 409

    with get_sessionmaker()() as db:
        seats = db.query(AaExamRoomStudent).filter(AaExamRoomStudent.tenant_id == TID,
            AaExamRoomStudent.exam_room_id == int(rid)).all()
        audits = db.query(AaExamAuditTrail).filter(AaExamAuditTrail.tenant_id == TID,
            AaExamAuditTrail.action == "EXAM_ATTENDANCE_PRESENT").all()
        assert len(seats) == 2 and all(row.attendance_status == "PRESENT" and row.version == 1 for row in seats)
        assert len(audits) == 2


def test_exam_attendance_rejects_draft_absence_and_archived_term(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaExamRoomStudent, AaTerm

    ids, admin, bid, _cid, rid = _published_room(client, db_mode, publish=False)
    draft = client.get(f"{BASE}/exam/rooms/{rid}/attendance", headers=admin)
    assert draft.status_code == 200
    assert not draft.json()["data"]["items"][0]["markPresentAction"]["allowed"]
    assert _mark(client, admin, rid, ids["s1"]).status_code == 409
    assert client.post(f"{BASE}/exam/batches/{bid}/publish", headers=admin).status_code == 200

    with get_sessionmaker()() as db:
        seat = db.query(AaExamRoomStudent).filter(AaExamRoomStudent.tenant_id == TID,
            AaExamRoomStudent.exam_room_id == int(rid), AaExamRoomStudent.student_id == ids["s1"]).one()
        seat.attendance_status = "ABSENT"
        seat.version += 1
        db.commit()
    assert _mark(client, admin, rid, ids["s1"], version=1).status_code == 409
    assert _mark(client, admin, rid, ids["s2"], version=1).status_code == 409

    with get_sessionmaker()() as db:
        db.get(AaTerm, ids["term"]).status = "ARCHIVED"
        db.commit()
    assert _mark(client, admin, rid, ids["s2"]).status_code == 409
    blocked = client.get(f"{BASE}/exam/rooms/{rid}/attendance", headers=admin)
    assert blocked.status_code == 200
    assert all(not row["markPresentAction"]["allowed"] for row in blocked.json()["data"]["items"])


def test_exam_attendance_two_writers_only_one_succeeds(client, db_mode):
    ids, admin, _bid, _cid, rid = _published_room(client, db_mode)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _i: _mark(client, admin, rid, ids["s1"]).status_code, range(2)))
    assert sorted(results) == [200, 409]


def test_exam_attendance_student_other_teacher_and_foreign_college_denied(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingTask, AaTeachingTaskBatch, College, Role, RolePermission
    from tests.support_grade_review_identity import _ensure_permission
    from tests.test_aa_exam import _stu_token

    ids, admin, _bid, _cid, rid = _published_room(client, db_mode)
    with get_sessionmaker()() as db:
        teacher_role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == "ACADEMIC_TEACHER").one()
        permission = _ensure_permission(db, "academicAffairs.exam.recordAbnormal")
        db.add(RolePermission(tenant_id=TID, role_id=teacher_role.id, permission_id=permission.id, status="ACTIVE"))
        db.commit()
    teacher = _hdr(client, "teacher_a")
    other_teacher = _hdr(client, "teacher_b")
    assert client.get(f"{BASE}/exam/rooms/{rid}/attendance", headers=teacher).status_code == 200
    assert client.get(f"{BASE}/exam/rooms/{rid}/attendance", headers=other_teacher).status_code == 403
    assert client.get(f"{BASE}/exam/rooms/{rid}/attendance", headers=_stu_token("考甲", "EX2401")).status_code == 403

    with get_sessionmaker()() as db:
        foreign = College(tenant_id=TID, college_name="另一学院", status="ACTIVE")
        db.add(foreign)
        db.flush()
        task = db.get(AaTeachingTask, ids["tt1"])
        db.get(AaTeachingTaskBatch, task.batch_id).college_id = foreign.id
        db.commit()
    college = _hdr(client, "college_admin01")
    assert client.get(f"{BASE}/exam/rooms/{rid}/attendance", headers=college).status_code == 403
    assert client.get(f"{BASE}/exam/rooms/{rid}/attendance", headers=teacher).status_code == 200


def test_incident_and_archive_share_batch_lock_and_cannot_both_succeed(client, db_mode, monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_exam_facade as exam

    ids, admin, bid, cid, rid = _published_room(client, db_mode)
    assert _mark(client, admin, rid, ids["s1"]).status_code == 200
    assert _mark(client, admin, rid, ids["s2"]).status_code == 200
    assert client.post(f"{BASE}/exam/batches/{bid}/finish", headers=admin).status_code == 200

    incident_at_audit = Event()
    release_incident = Event()
    archive_at_lock = Event()
    original_audit = exam._legacy._audit
    original_lock = exam._lock_exam_batch

    def pause_incident(db, biz_type, biz_id, action, *args):
        if action == "EXAM_INCIDENT_RECORD":
            incident_at_audit.set()
            assert release_incident.wait(15)
        return original_audit(db, biz_type, biz_id, action, *args)

    def observe_archive(db, batch):
        if incident_at_audit.is_set():
            archive_at_lock.set()
        return original_lock(db, batch)

    monkeypatch.setattr(exam._legacy, "_audit", pause_incident)
    monkeypatch.setattr(exam, "_lock_exam_batch", observe_archive)
    with ThreadPoolExecutor(max_workers=2) as pool:
        incident = pool.submit(client.post, f"{BASE}/exam/incidents", headers=admin,
                               json={"examCourseId": cid, "studentId": str(ids["s1"]), "incidentType": "OTHER"})
        assert incident_at_audit.wait(15)
        archive = pool.submit(client.post, f"{BASE}/exam/batches/{bid}/archive", headers=admin)
        try:
            assert archive_at_lock.wait(15)
            assert not archive.done()
        finally:
            release_incident.set()
        assert incident.result(timeout=20).status_code == 200
        assert archive.result(timeout=20).status_code == 409
