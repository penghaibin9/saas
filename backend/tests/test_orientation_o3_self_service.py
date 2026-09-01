"""O3 student pre-arrival canonical workflow (real MySQL via db_mode)."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

TID = 1000000000000000001
PORTAL = "/api/v1/portal/orientation"


def _token(*, user_id: int, student_id: int | None, student_no: str, name: str) -> dict:
    from app.core.security import create_access_token
    payload = {
        # u_<numeric> is the repository's synthetic-test form of a real DB account id:
        # resolve_student still requires StudentAccountLink, while tenant middleware does
        # not mistake the fixture-local tenant identity for a production-issued JWT.
        "userId": f"u_{user_id}", "realName": name, "studentNo": student_no,
        "userType": "STUDENT", "tenantId": str(TID), "tid": "x",
        "activeContextId": "ctx", "currentRoleCode": "STUDENT", "clientType": "PC",
    }
    if student_id is not None:
        payload["studentId"] = str(student_id)
    return {"Authorization": "Bearer " + create_access_token(payload)}


def _seed_o3(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (
        OrientationBatch, OrientationFlowStep, OrientationFlowVersion,
        OrientationStudent, StudentAccountLink, StudentProfile, User,
    )
    from app.services.orientation_flow_service import ensure_student_steps

    db = get_sessionmaker()()
    profile = db.get(StudentProfile, int(db_mode["student"]))
    profile.student_no = "O3-SELF-001"
    profile.real_name = "O3自助学生"
    profile.current_stage = "ORIENTATION"
    user = User(
        tenant_id=TID, login_name="o3-self-001", real_name=profile.real_name,
        password_hash="not-used", user_type="STUDENT", status="ACTIVE",
    )
    db.add(user); db.flush()
    db.add(StudentAccountLink(
        tenant_id=TID, student_id=profile.id, user_id=user.id, link_status="ACTIVE",
        bound_login_name=user.login_name, bound_student_no=profile.student_no,
        source="MANUAL", bound_at=datetime.utcnow(),
    ))
    flow = OrientationFlowVersion(
        tenant_id=TID, version_no=3003, version_name="O3 预报到流程",
        status="PUBLISHED", source_type="MANUAL", published_at=datetime.utcnow(),
    )
    db.add(flow); db.flush()
    for order, key in enumerate(("INFO", "MATERIAL")):
        db.add(OrientationFlowStep(
            tenant_id=TID, flow_version_id=flow.id, step_key=key,
            step_name={"INFO": "信息采集", "MATERIAL": "材料上传"}[key],
            enabled=True, required=True, sort_order=order,
        ))
    db.flush()
    now = datetime.utcnow()
    batch = OrientationBatch(
        tenant_id=TID, batch_name="2026 O3 预报到", batch_no="O3-SELF-2026",
        year="2026", start_date=now - timedelta(days=2), end_date=now + timedelta(days=10),
        report_start_date=now + timedelta(days=1), report_end_date=now + timedelta(days=5),
        status="ACTIVE", planned_count=1, flow_version_id=flow.id,
    )
    db.add(batch); db.flush()
    orientation = OrientationStudent(
        tenant_id=TID, batch_id=batch.id, student_id=profile.id,
        name=profile.real_name, admission_no="O3-ADMISSION-001",
        source_type="MANUAL", source_record_id="O3-ADMISSION-001",
        identity_status="LINKED", record_status="ACTIVE",
    )
    db.add(orientation); db.flush()
    ensure_student_steps(db, orientation, status_source="PROCESS_FACT")

    other = StudentProfile(
        tenant_id=TID, student_no="O3-OTHER-002", real_name="O3其他学生",
        current_stage="ORIENTATION", student_status="NORMAL", status="ACTIVE",
    )
    other_user = User(
        tenant_id=TID, login_name="o3-other-002", real_name=other.real_name,
        password_hash="not-used", user_type="STUDENT", status="ACTIVE",
    )
    db.add_all([other, other_user]); db.flush()
    db.add(StudentAccountLink(
        tenant_id=TID, student_id=other.id, user_id=other_user.id, link_status="ACTIVE",
        bound_login_name=other_user.login_name, bound_student_no=other.student_no,
        source="MANUAL", bound_at=datetime.utcnow(),
    ))
    unlinked = User(
        tenant_id=TID, login_name="o3-unlinked-003", real_name="O3未绑定账号",
        password_hash="not-used", user_type="STUDENT", status="ACTIVE",
    )
    db.add(unlinked)
    db.commit()
    result = {
        "profileId": profile.id, "classId": profile.class_id,
        "userId": user.id, "studentNo": profile.student_no,
        "name": profile.real_name, "orientationId": orientation.id,
        "otherProfileId": other.id, "otherUserId": other_user.id,
        "otherNo": other.student_no, "otherName": other.real_name,
        "unlinkedUserId": unlinked.id,
    }
    db.close()
    return result


def _upload(client, headers, name: str, content: bytes) -> str:
    response = client.post(
        "/api/v1/files", headers=headers,
        files={"file": (name, content, "text/plain")},
        data={"bizType": "ORIENTATION_MATERIAL"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == 0 and body["data"]["temporary"] is True
    return str(body["data"]["fileId"])


def test_o3_information_arrival_material_file_authority_and_fail_closed(
    client, db_mode, auth_headers,
):
    ids = _seed_o3(db_mode)
    headers = _token(
        user_id=ids["userId"], student_id=ids["profileId"],
        student_no=ids["studentNo"], name=ids["name"],
    )
    info = client.post(f"{PORTAL}/collect", headers=headers, json={
        "phone": "13800138000", "origin": "湖南长沙",
        "emergencyContactName": "家长甲", "emergencyPhone": "13900139000",
        "confirmed": True,
    })
    assert info.status_code == 200, info.text
    assert info.json()["data"]["reportStatus"] == "PREPARED"

    mine = client.get(f"{PORTAL}/my", headers=headers).json()["data"]
    # Missing material/payment/dorm facts remain visible follow-ups, but no longer
    # make a verified newcomer wait at the arrival desk.
    assert mine["reportCodeValid"] is False and mine["reportCodeStatus"] == "ELIGIBLE"
    assert mine["checkinCredential"]["canIssue"] is True
    assert mine["qualification"]["checkinEligibility"]["followUps"]
    assert mine["selfService"]["available"] is True
    assert mine["selfService"]["information"] == {
        "origin": "湖南长沙", "phoneMasked": "138****8000",
        "emergencyContactName": "家长甲", "emergencyPhoneMasked": "139****9000",
        "complete": True,
    }

    planned = (datetime.utcnow() + timedelta(days=2)).isoformat(timespec="seconds")
    arrival = client.put(f"{PORTAL}/arrival", headers=headers, json={
        "arrivalMode": "TRAIN", "plannedArrivalAt": planned,
        "stationName": "长沙南站", "transportNo": "G100",
        "pickupRequired": True, "companionCount": 1, "expectedVersion": 0,
    })
    assert arrival.status_code == 200, arrival.text
    assert arrival.json()["data"]["arrivalMode"] == "TRAIN"
    stale = client.put(f"{PORTAL}/arrival", headers=headers, json={
        "arrivalMode": "TRAIN", "plannedArrivalAt": planned,
        "stationName": "长沙南站", "transportNo": "G101",
        "pickupRequired": True, "companionCount": 0, "expectedVersion": 0,
    })
    assert stale.status_code == 409 and stale.json()["code"] != 0

    first_file = _upload(client, headers, "identity-v1.txt", b"orientation identity v1")
    first = client.post(f"{PORTAL}/materials", headers=headers, json={
        "materialType": "ID_CARD", "fileId": first_file,
        "clientSubmissionId": "o3-id-card-submit-0001",
    })
    assert first.status_code == 200, first.text
    first_data = first.json()["data"]
    assert first_data["submissionNo"] == 1 and first_data["assetId"] and first_data["fileVersionId"]
    replay = client.post(f"{PORTAL}/materials", headers=headers, json={
        "materialType": "ID_CARD", "fileId": first_file,
        "clientSubmissionId": "o3-id-card-submit-0001",
    })
    assert replay.status_code == 200 and replay.json()["data"]["id"] == first_data["id"]
    second_file = _upload(client, headers, "identity-v2.txt", b"orientation identity v2")
    conflict = client.post(f"{PORTAL}/materials", headers=headers, json={
        "materialType": "ID_CARD", "fileId": second_file,
        "clientSubmissionId": "o3-id-card-submit-0001",
    })
    assert conflict.status_code == 409 and conflict.json()["code"] != 0

    other_headers = _token(
        user_id=ids["otherUserId"], student_id=ids["otherProfileId"],
        student_no=ids["otherNo"], name=ids["otherName"],
    )
    assert client.get(f"/api/v1/files/{first_file}", headers=other_headers).status_code == 404
    unlinked_headers = _token(
        user_id=ids["unlinkedUserId"], student_id=None,
        student_no=ids["studentNo"], name=ids["name"],
    )
    denied = client.post(f"{PORTAL}/collect", headers=unlinked_headers, json={
        "phone": "13800138000", "origin": "湖南长沙",
        "emergencyContactName": "家长甲", "emergencyPhone": "13900139000",
        "confirmed": True,
    })
    assert denied.status_code == 403 and denied.json()["code"] != 0

    from app.db.session import get_sessionmaker
    from app.models import OrientationMaterial
    from app.models.file import FileAsset, FileBinding, FileVersion
    db = get_sessionmaker()()
    old = db.get(OrientationMaterial, int(first_data["id"]))
    old.status = "RETURNED"
    db.commit(); db.close()

    second = client.post(f"{PORTAL}/materials", headers=headers, json={
        "materialType": "ID_CARD", "fileId": second_file,
        "clientSubmissionId": "o3-id-card-submit-0002",
    })
    assert second.status_code == 200, second.text
    second_data = second.json()["data"]
    assert second_data["submissionNo"] == 2

    db = get_sessionmaker()()
    old = db.get(OrientationMaterial, int(first_data["id"]))
    new = db.get(OrientationMaterial, int(second_data["id"]))
    assert old.is_current is False and new.is_current is True
    assert new.supersedes_material_id == old.id and new.student_id == ids["profileId"]
    asset = db.get(FileAsset, int(new.asset_id))
    version = db.get(FileVersion, int(new.file_version_id))
    binding = db.query(FileBinding).filter_by(
        tenant_id=TID, biz_type="ORIENTATION_MATERIAL", biz_id=str(new.id)
    ).one()
    assert asset.current_version_id == version.id and asset.version_count == 2
    assert version.file_object_id == int(second_file) and version.is_current is True
    assert binding.asset_id == asset.id and binding.version_id == version.id
    assert binding.student_id == ids["profileId"] and binding.class_id == ids["classId"]
    db.close()

    approved = client.post(
        f"/api/v1/orientation/materials/{second_data['id']}/approve",
        headers=auth_headers,
        json={"comment": "O3 file-version approval"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "APPROVED"

    db = get_sessionmaker()()
    new = db.get(OrientationMaterial, int(second_data["id"]))
    version = db.get(FileVersion, int(new.file_version_id))
    assert new.status == "APPROVED" and version.status == "APPROVED"
    db.close()


def test_o3_migration_is_serial_and_has_preflight_and_safe_downgrade():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "20260901_orientation_self_o3.py"
    source = path.read_text(encoding="utf-8")
    assert 'down_revision = "20260901_dorm_allocation_d3"' in source
    assert "orientation material parent is missing or cross-tenant" in source
    assert "ROW_NUMBER() OVER" in source
    assert "downgrade blocked: pre-arrival runtime data exists" in source
