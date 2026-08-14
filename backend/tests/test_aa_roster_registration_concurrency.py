"""D2-U 注册并发合同：批量 confirm 与旧单笔 API 共用数据库级临界区。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from app.db.session import get_sessionmaker

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _hdr(client):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_students(db_mode, count=2):
    del db_mode
    from app.models import Major, SchoolClass, StudentProfile

    suffix = uuid4().hex[:8]
    db = get_sessionmaker()()
    major = Major(
        tenant_id=TID,
        college_id=880001,
        major_name=f"并发专业-{suffix}",
        code=f"CON-{suffix}",
        status="ACTIVE",
    )
    db.add(major)
    db.flush()
    klass = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name=f"并发班-{suffix}",
        grade="2026",
        status="ACTIVE",
    )
    db.add(klass)
    db.flush()
    rows = []
    for i in range(count):
        row = StudentProfile(
            tenant_id=TID,
            student_no=f"D2U-CON-{suffix}-{i}",
            real_name=f"并发学生{suffix}-{i}",
            college_id=major.college_id,
            major_id=major.id,
            class_id=klass.id,
            current_stage="ORIENTATION",
            student_status="PENDING_REGISTER",
            status="ACTIVE",
        )
        db.add(row)
        db.flush()
        rows.append(row.id)
    db.commit()
    db.close()
    return rows


def _open_batch(client, headers):
    response = client.post(
        f"{BASE}/registration-batches",
        headers=headers,
        json={
            "batchName": f"D2U并发批次-{uuid4().hex[:8]}",
            "registerType": "ENROLL",
            "open": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["batchId"]


def _assert_single_registration_fact(batch_id, student_id):
    from app.models import AaRegistration, AaStatusChange, StudentStageEvent

    db = get_sessionmaker()()
    try:
        assert db.query(AaRegistration).filter_by(
            tenant_id=TID,
            batch_id=int(batch_id),
            student_id=int(student_id),
            status="REGISTERED",
        ).count() == 1
        assert db.query(AaStatusChange).filter_by(
            tenant_id=TID,
            student_id=int(student_id),
            to_status="REGISTERED",
        ).count() == 1
        assert db.query(StudentStageEvent).filter_by(
            tenant_id=TID,
            student_id=int(student_id),
            to_stage="REGISTERED",
            source_module="academic-affairs",
        ).count() == 1
    finally:
        db.close()


def test_d2u_same_preview_token_concurrent_confirm_never_duplicates_registration_facts(client, db_mode):
    student_id = _seed_students(db_mode, 1)[0]
    headers = _hdr(client)
    batch_id = _open_batch(client, headers)

    preview = client.post(
        f"{BASE}/registration-batches/{batch_id}/bulk-register-preview",
        headers=headers,
        json={"studentIds": [student_id]},
    )
    assert preview.status_code == 200, preview.text
    token = preview.json()["data"]["previewToken"]
    assert token

    barrier = Barrier(2)

    def confirm_once():
        barrier.wait()
        return client.post(
            f"{BASE}/registration-batches/{batch_id}/bulk-register",
            headers=headers,
            json={"previewToken": token},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _i: confirm_once(), range(2)))

    assert all(r.status_code < 500 for r in responses), [r.text for r in responses]
    success_items = 0
    for response in responses:
        if response.status_code == 200:
            success_items += int(response.json()["data"]["succeeded"])
        else:
            assert response.status_code in (400, 409), response.text
    assert success_items == 1
    _assert_single_registration_fact(batch_id, student_id)


def test_d2u_legacy_single_register_concurrent_double_submit_is_serialized_not_500(client, db_mode):
    student_id = _seed_students(db_mode, 1)[0]
    headers = _hdr(client)
    batch_id = _open_batch(client, headers)
    barrier = Barrier(2)

    def register_once():
        barrier.wait()
        return client.post(
            f"{BASE}/registration-batches/{batch_id}/register",
            headers=headers,
            json={"studentId": str(student_id)},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _i: register_once(), range(2)))

    statuses = [r.status_code for r in responses]
    assert statuses.count(200) == 1, [r.text for r in responses]
    assert all(code < 500 for code in statuses), [r.text for r in responses]
    assert all(code in (200, 400, 409) for code in statuses), [r.text for r in responses]
    _assert_single_registration_fact(batch_id, student_id)
