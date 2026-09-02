"""Newcomer self-activation: bulk-ready roster -> proof -> account -> WeChat -> login."""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001


def _seed_candidates(db_mode):
    from app.core.field_crypto import encrypt_field
    from app.db.session import get_sessionmaker
    from app.models import (
        College, Major, OrientationBatch, OrientationFlowStep,
        OrientationFlowVersion, OrientationStudent, SchoolClass, Tenant,
    )

    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, TID)
        if tenant is None:
            tenant = Tenant(
                id=TID, tenant_code="activation-school", school_name="自助激活测试学校",
                deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE",
            )
            db.add(tenant)
        else:
            tenant.tenant_code = "activation-school"
            tenant.school_name = "自助激活测试学校"
            tenant.status = "ACTIVE"
        college = College(
            tenant_id=TID, college_name="智能制造学院", status="ACTIVE",
        )
        db.add(college); db.flush()
        major = Major(
            tenant_id=TID, college_id=college.id, major_name="工业机器人技术", status="ACTIVE",
        )
        db.add(major); db.flush()
        school_class = SchoolClass(
            tenant_id=TID, major_id=major.id, class_name="机器人2601班", grade="2026",
            status="ACTIVE", class_status="NORMAL",
        )
        db.add(school_class); db.flush()
        flow = OrientationFlowVersion(
            tenant_id=TID, version_no=91001, version_name="新生自助流程",
            status="PUBLISHED", source_type="MANUAL", published_at=datetime.utcnow(),
        )
        db.add(flow); db.flush()
        db.add(OrientationFlowStep(
            tenant_id=TID, flow_version_id=flow.id, step_key="ACTIVATE",
            step_name="账号激活", enabled=True, required=True, sort_order=1,
        ))
        batch = OrientationBatch(
            tenant_id=TID, batch_name="2026级新生迎新", batch_no="ACTIVATE-2026",
            year="2026", status="ACTIVE", planned_count=3, flow_version_id=flow.id,
        )
        db.add(batch); db.flush()
        common = {
            "tenant_id": TID, "batch_id": batch.id, "gender": "男",
            "college_id": college.id, "college_name": college.college_name,
            "major_id": major.id, "major_name": major.major_name,
            "class_id": school_class.id, "class_name": school_class.class_name,
            "grade": "2026", "source_type": "DOMAIN_IMPORT",
            "identity_status": "UNLINKED", "record_status": "ACTIVE",
        }
        candidate = OrientationStudent(
            **common, name="自助激活新生", admission_no="LQ-ACT-0001",
            student_no="2026JQ0001", source_record_id="LQ-ACT-0001",
            phone_encrypted=encrypt_field("13800000001"),
            id_card_encrypted=encrypt_field("33010220080101999X"),
        )
        db.add(candidate)
        for index in (2, 3):
            db.add(OrientationStudent(
                **common, name=f"待批量编号{index}", admission_no=f"LQ-ACT-000{index}",
                source_record_id=f"LQ-ACT-000{index}",
                id_card_encrypted=encrypt_field(f"33010220080101000{index}"),
            ))
        db.commit()
        return {"candidate": int(candidate.id), "batch": int(batch.id)}
    finally:
        db.close()


def test_bulk_numbering_and_self_activation_are_one_stop(
    client, db_mode, auth_headers, monkeypatch,
):
    from app.core.security import verify_password
    from app.db.session import get_sessionmaker
    from app.models import (
        OrientationActivationChallenge, OrientationStudent, StudentAccountLink,
        StudentProfile, User, WxAccountBinding,
    )

    ids = _seed_candidates(db_mode)

    dry_run = client.post(
        f"/api/v1/orientation/batches/{ids['batch']}/student-numbers/assign",
        headers=auth_headers,
        json={"prefix": "2026JQ", "startNumber": 2, "width": 4, "dryRun": True},
    )
    assert dry_run.status_code == 200, dry_run.text
    assert dry_run.json()["data"]["missingCount"] == 2
    assigned = client.post(
        f"/api/v1/orientation/batches/{ids['batch']}/student-numbers/assign",
        headers=auth_headers,
        json={"prefix": "2026JQ", "startNumber": 2, "width": 4},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["data"]["assignedCount"] == 2
    assert assigned.json()["data"]["sample"] == ["2026JQ0002", "2026JQ0003"]

    nonce = "activation-test-nonce-0001"
    wrong = client.post("/api/v1/auth/orientation-activation/verify", json={
        "tenantCode": "activation-school", "admissionNo": "LQ-ACT-0001",
        "idCardLast6": "111111", "clientNonce": nonce,
    })
    assert wrong.status_code == 401
    assert "核验失败" in wrong.json()["message"]

    verified = client.post("/api/v1/auth/orientation-activation/verify", json={
        "tenantCode": "activation-school", "admissionNo": "LQ-ACT-0001",
        "idCardLast6": "01999X", "clientNonce": nonce,
    })
    assert verified.status_code == 200, verified.text
    proof = verified.json()["data"]
    assert proof["candidate"]["studentNo"] == "2026JQ0001"
    assert "idCardLast6" not in proof["candidate"]

    monkeypatch.setattr(
        "app.services.wx_auth_service.openid_from_bind_token",
        lambda _token: "openid-self-activation-001",
    )
    body = {
        "activationToken": proof["activationToken"], "clientNonce": nonce,
        "newPassword": "Freshman@2026", "confirmPassword": "Freshman@2026",
        "wxToken": "wx-token-for-test", "clientRequestId": "activate-request-000001",
        "clientType": "STUDENT_MINI",
    }
    completed = client.post("/api/v1/auth/orientation-activation/complete", json=body)
    assert completed.status_code == 200, completed.text
    result = completed.json()["data"]
    assert result["activation"]["completed"] is True
    assert result["activation"]["wechatBound"] is True
    assert result["activation"]["studentNo"] == "2026JQ0001"
    assert result["accessToken"]

    replay = client.post("/api/v1/auth/orientation-activation/complete", json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["activation"]["idempotent"] is True

    db = get_sessionmaker()()
    try:
        candidate = db.get(OrientationStudent, ids["candidate"])
        profiles = db.query(StudentProfile).filter_by(
            tenant_id=TID, student_no="2026JQ0001", is_deleted=False,
        ).all()
        users = db.query(User).filter_by(
            tenant_id=TID, login_name="2026JQ0001", is_deleted=False,
        ).all()
        assert len(profiles) == len(users) == 1
        assert verify_password("Freshman@2026", users[0].password_hash)
        assert candidate.student_id == profiles[0].id
        assert candidate.identity_status == "LINKED"
        assert candidate.steps_json["ACTIVATE"] == "DONE"
        assert db.query(StudentAccountLink).filter_by(
            tenant_id=TID, student_id=profiles[0].id, user_id=users[0].id,
            link_status="ACTIVE",
        ).count() == 1
        assert db.query(WxAccountBinding).filter_by(
            tenant_id=TID, user_id=users[0].id,
            wx_openid="openid-self-activation-001", status="ACTIVE",
        ).count() == 1
        challenge = db.query(OrientationActivationChallenge).filter_by(
            tenant_id=TID, orientation_student_id=candidate.id,
        ).one()
        assert challenge.status == "COMPLETED" and challenge.wechat_bound is True
    finally:
        db.close()
