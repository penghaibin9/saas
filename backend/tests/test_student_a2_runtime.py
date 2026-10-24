"""A2 学生事实/写入真实化运行态回归。"""
from __future__ import annotations

import uuid

import pytest

TID = 1000000000000000001


@pytest.fixture()
def a2_class(db_mode):
    from app.db.session import get_sessionmaker
    from app.models.org import College, Major, SchoolClass

    db = get_sessionmaker()()
    suffix = uuid.uuid4().hex[:8]
    try:
        college = College(
            tenant_id=TID,
            college_name=f"A2学院-{suffix}",
            status="ACTIVE",
        )
        db.add(college)
        db.flush()
        major = Major(
            tenant_id=TID,
            college_id=college.id,
            major_name=f"A2专业-{suffix}",
            status="ACTIVE",
        )
        db.add(major)
        db.flush()
        school_class = SchoolClass(
            tenant_id=TID,
            major_id=major.id,
            class_name=f"A2班-{suffix}",
            grade="2026",
            status="ACTIVE",
            class_status="NORMAL",
        )
        db.add(school_class)
        db.commit()
        return str(school_class.id)
    finally:
        db.close()


def _create_minimal_student(client, auth_headers, class_id: str, *, no: str):
    response = client.post(
        "/api/v1/students",
        headers={
            **auth_headers,
            "Idempotency-Key": f"a2-create-{no}",
        },
        json={
            "studentNo": no,
            "realName": "A2事实学生",
            "classId": class_id,
        },
    )
    body = response.json()
    assert body["code"] == 0, body
    return body["data"]


def test_missing_identity_and_account_facts_never_become_success_defaults(
    client, auth_headers, db_mode, a2_class
):
    no = f"A2{uuid.uuid4().hex[:10].upper()}"
    created = _create_minimal_student(client, auth_headers, a2_class, no=no)

    body = client.get(f"/api/v1/students/{created['id']}", headers=auth_headers).json()
    assert body["code"] == 0, body
    row = body["data"]

    assert row["identityVerifyStatus"] == "NOT_CONFIGURED"
    assert row["identityVerificationCapability"]["status"] == "NOT_CONFIGURED"
    assert row["accountBindStatus"] == "UNBOUND"
    assert row["dataCompleteness"] < 100
    assert "phone" in row["missingFields"]
    assert "idCard" in row["missingFields"]
    assert row["phoneMasked"] == ""


def test_real_account_link_changes_authoritative_bind_status(
    client, auth_headers, db_mode, a2_class
):
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.models import User
    from app.services import student_account_link_service as link_svc

    no = f"A2{uuid.uuid4().hex[:10].upper()}"
    created = _create_minimal_student(client, auth_headers, a2_class, no=no)
    student_id = int(created["id"])

    db = get_sessionmaker()()
    try:
        user = User(
            tenant_id=TID,
            login_name=f"login-{uuid.uuid4().hex[:10]}",
            real_name="A2绑定账号",
            password_hash=hash_password("Test@123456"),
            user_type="STUDENT",
            status="ACTIVE",
        )
        db.add(user)
        db.flush()
        link_svc.bind_in_session(
            db,
            tenant_id=TID,
            student_id=student_id,
            user_id=int(user.id),
            source="MANUAL",
        )
        db.commit()
    finally:
        db.close()

    body = client.get(f"/api/v1/students/{student_id}", headers=auth_headers).json()
    assert body["code"] == 0, body
    assert body["data"]["accountBindStatus"] == "BOUND"


def test_student_summary_is_scoped_server_fact_not_frontend_estimate(
    client, auth_headers, db_mode, a2_class
):
    no = f"A2{uuid.uuid4().hex[:10].upper()}"
    _create_minimal_student(client, auth_headers, a2_class, no=no)

    body = client.get("/api/v1/students/summary", headers=auth_headers).json()
    assert body["code"] == 0, body
    data = body["data"]
    assert data["totalStudents"] >= 1
    assert data["identityVerification"]["status"] == "NOT_CONFIGURED"
    assert data["accountBinding"]["bound"] >= 0
    assert data["accountBinding"]["unbound"] >= 0
    assert data["scopeType"] in {"TENANT", "CLASS", "STUDENT"}
    assert data["asOf"].endswith("Z")


def test_same_student_create_idempotency_key_replays_single_fact(
    client, auth_headers, db_mode, a2_class
):
    no = f"A2{uuid.uuid4().hex[:10].upper()}"
    key = f"a2-idempotency-{uuid.uuid4().hex}"
    payload = {
        "studentNo": no,
        "realName": "A2幂等学生",
        "classId": a2_class,
    }
    headers = {**auth_headers, "Idempotency-Key": key}

    first = client.post("/api/v1/students", headers=headers, json=payload).json()
    second = client.post("/api/v1/students", headers=headers, json=payload).json()

    assert first["code"] == 0, first
    assert second["code"] == 0, second
    assert str(first["data"]["id"]) == str(second["data"]["id"])
