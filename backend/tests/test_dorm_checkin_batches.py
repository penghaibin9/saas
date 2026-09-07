from sqlalchemy import select

from tests.test_dorm_d3_allocation import BASE, TID, _admin, _create, _seed_authorities

CHECKIN = "/api/v1/student-affairs/dorm/checkin-batches"


def test_checkin_receipts_survive_resume_and_conflicts_without_replaying(client, db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import DormBed, DormStay, OrientationStudent, User
    from app.services import dorm_checkin_batch_service as service
    from app.core.exceptions import AppException

    seeded = _seed_authorities(students=3, beds=3)
    with get_sessionmaker()() as db:
        db.add(User(tenant_id=TID, login_name="school_admin01", real_name="入住验收管理员",
                    password_hash="test-only-not-login", user_type="TEACHER", status="ACTIVE"))
        db.commit()
    headers = _admin(client)
    allocation = _create(client, headers, seeded, "ADMIN_AUTO", "CHECKIN-RECEIPT")
    assert client.post(f"{BASE}/{allocation}/dry-run", headers=headers).status_code == 200
    assert client.post(f"{BASE}/{allocation}/publish", headers=headers).status_code == 200
    with get_sessionmaker()() as db:
        stays = db.scalars(select(DormStay).where(DormStay.tenant_id == TID).order_by(DormStay.id)).all()
        selections = [{"stayId": str(row.id), "version": row.version} for row in stays]
        stay_ids = [row.id for row in stays]
    payload = {"clientRequestId": "checkin-receipt-test", "arrivalConfirmed": True, "items": selections}
    assert client.post(CHECKIN, headers=headers, json={**payload, "arrivalConfirmed": False}).status_code == 400
    response = client.post(CHECKIN, headers=headers, json=payload)
    assert response.status_code == 200, response.text
    job_id = response.json()["data"]["jobId"]
    assert client.post(CHECKIN, headers=headers, json=payload).json()["data"]["jobId"] == job_id
    assert client.post(CHECKIN, headers=headers, json={**payload, "items": selections[:1]}).status_code == 409
    with get_sessionmaker()() as db:
        assert all(db.get(DormStay, sid).status == "RESERVED" for sid in stay_ids)
        # A stale reservation is not silently refreshed and overwritten.
        db.get(DormStay, stay_ids[1]).version += 1
        db.commit()

    # A failure after the business mutation must roll back both actual occupancy and receipt.
    original = service.checkin_in_transaction

    def fail_after_write(db, *args, **kwargs):
        result = original(db, *args, **kwargs)
        if kwargs["expected_stay_id"] == stay_ids[2]:
            raise AppException("DATA_CONFLICT", "模拟办理末尾冲突")
        return result

    monkeypatch.setattr(service, "checkin_in_transaction", fail_after_write)
    response = client.post(f"{CHECKIN}/{job_id}/continue", headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert (result["status"], result["success"], result["failed"], result["pending"]) == ("PARTIAL_SUCCESS", 1, 2, 0)
    details = client.get(f"{CHECKIN}/{job_id}?page=1&pageSize=2", headers=headers).json()["data"]
    assert len(details["items"]) == 2 and details["total"] == 3
    assert details["items"][1]["error"]
    with get_sessionmaker()() as db:
        first = db.get(DormStay, stay_ids[0])
        first_time, first_version = first.checkin_at, first.version
        assert first.status == "ACTIVE" and first_time is not None
        for sid in stay_ids[1:]:
            stay = db.get(DormStay, sid)
            assert stay.status == "RESERVED" and stay.checkin_at is None
            assert db.get(DormBed, stay.bed_id).status == "LOCKED"
        ori = db.scalars(select(OrientationStudent).where(OrientationStudent.student_id == first.student_id)).one()
        assert ori.dorm_status == "CHECKED_IN"
    # Reopen/repeat continues only PENDING, never falsely treats a new stay as the old receipt.
    monkeypatch.setattr(service, "checkin_in_transaction", original)
    repeated = client.post(f"{CHECKIN}/{job_id}/continue", headers=headers)
    assert repeated.json()["data"] == result
    with get_sessionmaker()() as db:
        first = db.get(DormStay, stay_ids[0])
        assert (first.checkin_at, first.version) == (first_time, first_version)
        assert db.scalar(select(DormBed.student_id).where(DormBed.id == first.bed_id)) == first.student_id
    # Access is re-evaluated on read and continuation, not frozen from creation.
    def revoke(*args, **kwargs):
        raise AppException("NO_DATA_SCOPE", "楼栋已移交")
    monkeypatch.setattr(service.dorm, "_require_dorm_scope", revoke)
    assert client.get(f"{CHECKIN}/{job_id}", headers=headers).status_code == 403
    assert client.post(f"{CHECKIN}/{job_id}/continue", headers=headers).status_code == 403
    assert client.get(CHECKIN, headers=headers).json()["data"]["items"] == []


def test_pending_checkins_resume_from_saved_chunk(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import DormStay, User
    seeded = _seed_authorities(students=21, beds=21)
    with get_sessionmaker()() as db:
        db.add(User(tenant_id=TID, login_name="school_admin01", real_name="入住验收管理员",
                    password_hash="test-only-not-login", user_type="TEACHER", status="ACTIVE"))
        db.commit()
    headers = _admin(client)
    allocation = _create(client, headers, seeded, "ADMIN_AUTO", "CHECKIN-CHUNKS")
    assert client.post(f"{BASE}/{allocation}/dry-run", headers=headers).status_code == 200
    assert client.post(f"{BASE}/{allocation}/publish", headers=headers).status_code == 200
    with get_sessionmaker()() as db:
        rows = db.scalars(select(DormStay).where(DormStay.tenant_id == TID)).all()
        selections = [{"stayId": str(row.id), "version": row.version} for row in rows]
    response = client.post(CHECKIN, headers=headers, json={
        "clientRequestId": "chunk-checkin-test", "arrivalConfirmed": True, "items": selections,
    })
    assert response.status_code == 200, response.text
    job_id = response.json()["data"]["jobId"]
    first = client.post(f"{CHECKIN}/{job_id}/continue", headers=headers)
    assert first.status_code == 200, first.text
    assert (first.json()["data"]["success"], first.json()["data"]["pending"]) == (20, 1)
    reopened = client.get(f"{CHECKIN}/{job_id}", headers=headers).json()["data"]
    assert sum(row["status"] == "PENDING" for row in reopened["items"]) == 1
    second = client.post(f"{CHECKIN}/{job_id}/continue", headers=headers)
    assert second.status_code == 200, second.text
    assert (second.json()["data"]["success"], second.json()["data"]["pending"]) == (21, 0)
    with get_sessionmaker()() as db:
        rows = db.scalars(select(DormStay).where(DormStay.tenant_id == TID)).all()
        assert len(rows) == 21 and all(row.status == "ACTIVE" for row in rows)
