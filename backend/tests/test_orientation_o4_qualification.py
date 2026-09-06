"""O4 server-side material/payment/green/dorm qualification authority."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

TID = 1000000000000000001


def _student_headers(user_id: int, student_id: int, student_no: str, name: str):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u_{user_id}", "studentId": str(student_id),
        "studentNo": student_no, "realName": name, "userType": "STUDENT",
        "tenantId": str(TID), "tid": "x", "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "PC",
    })}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (
        DormBed, DormBuilding, DormRoom, DormStay,
        OrientationBatch, OrientationFlowStep, OrientationFlowVersion,
        OrientationMaterial, OrientationMaterialRequirement, OrientationPaymentAccount,
        OrientationStudent, StudentAccountLink, StudentProfile, User,
    )
    from app.models.file import FileAsset, FileBinding, FileObject, FileVersion
    from app.services.orientation_flow_service import ensure_student_steps, set_student_step_status

    db = get_sessionmaker()()
    profile = db.get(StudentProfile, int(db_mode["student"]))
    profile.student_no = "O4-QUAL-001"
    profile.real_name = "O4资格学生"
    profile.current_stage = "ORIENTATION"
    user = User(
        tenant_id=TID, login_name="o4-qual-001", real_name=profile.real_name,
        password_hash="unused", user_type="STUDENT", status="ACTIVE",
    )
    db.add(user); db.flush()
    db.add(StudentAccountLink(
        tenant_id=TID, student_id=profile.id, user_id=user.id, link_status="ACTIVE",
        bound_login_name=user.login_name, bound_student_no=profile.student_no,
        source="MANUAL", bound_at=datetime.utcnow(),
    ))
    flow = OrientationFlowVersion(
        tenant_id=TID, version_no=4004, version_name="O4资格流程",
        status="PUBLISHED", source_type="MANUAL", published_at=datetime.utcnow(),
    )
    db.add(flow); db.flush()
    for order, (key, label) in enumerate((
        ("ACTIVATE", "账号激活"), ("INFO", "信息核对"),
        ("MATERIAL", "材料上传"), ("PAYMENT", "缴费/绿色通道"),
        ("DORM", "宿舍确认"),
    )):
        db.add(OrientationFlowStep(
            tenant_id=TID, flow_version_id=flow.id, step_key=key,
            step_name=label, enabled=True, required=True, sort_order=order,
        ))
    for order, (material_type, label) in enumerate((
        ("ID_CARD", "身份证明"), ("ADMISSION_LETTER", "录取通知书"),
    )):
        db.add(OrientationMaterialRequirement(
            tenant_id=TID, flow_version_id=flow.id, material_type=material_type,
            material_name=label, required=True, requires_scan_clean=True,
            allowed_exts_json=["txt"], max_size_bytes=1024, sort_order=order,
            source_type="MANUAL",
        ))
    db.flush()
    batch = OrientationBatch(
        tenant_id=TID, batch_name="O4资格批次", batch_no="O4-QUAL-2026",
        year="2026", status="ACTIVE", planned_count=1, flow_version_id=flow.id,
    )
    db.add(batch); db.flush()
    orientation = OrientationStudent(
        tenant_id=TID, batch_id=batch.id, student_id=profile.id,
        name=profile.real_name, admission_no="O4-ADMISSION-001",
        source_type="MANUAL", source_record_id="O4-ADMISSION-001",
        identity_status="LINKED", record_status="ACTIVE",
        payment_status="UNPAID", material_status="NOT_UPLOADED",
    )
    db.add(orientation); db.flush()
    ensure_student_steps(db, orientation, status_source="PROCESS_FACT")
    set_student_step_status(
        db, orientation, "INFO", "DONE", status_source="PROCESS_FACT",
        source_biz_id=f"student:{orientation.id}:info",
    )
    account = OrientationPaymentAccount(
        tenant_id=TID, orientation_student_id=orientation.id, student_id=profile.id,
        payable_amount=100, paid_amount=0, status="UNPAID",
        source_type="LEGACY_BACKFILL", source_biz_id=f"orientation-student:{orientation.id}",
        synced_at=datetime.utcnow(),
    )
    db.add(account)

    building = DormBuilding(
        tenant_id=TID, building_name="O4资格楼", gender_limit="MIXED",
        floor_count=6, manager_teacher_key="o4-manager", status="ENABLED",
    )
    db.add(building); db.flush()
    room = DormRoom(
        tenant_id=TID, building_id=building.id, room_no="401", floor_no=4,
        capacity=4, room_type="STANDARD", status="ENABLED",
    )
    db.add(room); db.flush()
    bed = DormBed(
        tenant_id=TID, building_id=building.id, room_id=room.id,
        bed_no="1", status="VACANT",
    )
    db.add(bed); db.flush()
    stay = DormStay(
        tenant_id=TID, student_id=profile.id, bed_id=bed.id,
        building_id=building.id, room_id=room.id, stay_type="ALLOCATION",
        source_type="ALLOCATION", source_biz_id="o4-qualification-reservation",
        status="RESERVED",
    )
    db.add(stay)

    for order, material_type in enumerate(("ID_CARD", "ADMISSION_LETTER"), start=1):
        file_obj = FileObject(
            tenant_id=TID, file_key=f"o4/{material_type}.txt",
            file_name=f"{material_type}.txt", ext="txt", mime_type="text/plain",
            size_bytes=20, sha256=(str(order) * 64)[:64], biz_type="ORIENTATION_MATERIAL",
            owner_user_id=user.id, visibility="PRIVATE", security_level="PERSONAL",
            status="AVAILABLE", storage_backend="local", storage_zone="ACTIVE",
            upload_source="USER", scan_required=False, scan_status="NOT_REQUIRED",
        )
        db.add(file_obj); db.flush()
        asset = FileAsset(
            tenant_id=TID, asset_code=f"o4-material-{orientation.id}-{material_type}",
            title=file_obj.file_name, category_code="ORIENTATION_MATERIAL",
            owner_type="STUDENT", owner_id=str(profile.id), lifecycle_status="ACTIVE",
            version_count=1, sensitivity_level="PERSONAL",
        )
        db.add(asset); db.flush()
        version = FileVersion(
            tenant_id=TID, asset_id=asset.id, file_object_id=file_obj.id,
            version_no=1, source_channel="ORIENTATION_SELF_SERVICE",
            uploader_user_id=str(user.id), status="APPROVED", is_current=True,
            submitted_at=datetime.utcnow(),
        )
        db.add(version); db.flush()
        asset.current_version_id = version.id
        material = OrientationMaterial(
            tenant_id=TID, ori_student_id=orientation.id, student_id=profile.id,
            material_type=material_type, file_name=file_obj.file_name,
            submission_no=1, is_current=True, source_type="STUDENT_SELF_SERVICE",
            client_submission_id=f"o4-{material_type.lower()}-0001",
            asset_id=asset.id, file_version_id=version.id,
            submit_time=datetime.utcnow(), status="APPROVED",
        )
        db.add(material); db.flush()
        db.add(FileBinding(
            tenant_id=TID, file_id=file_obj.id, biz_type="ORIENTATION_MATERIAL",
            biz_id=str(material.id), relation_type="MATERIAL_SUBMISSION",
            subject_type="STUDENT", subject_id=str(profile.id), batch_id=str(batch.id),
            version_no=1, is_current=True, status="ACTIVE", asset_id=asset.id,
            version_id=version.id, module_code="ORIENTATION", student_id=profile.id,
            class_id=profile.class_id,
        ))
    orientation.material_status = "APPROVED"
    db.commit()
    result = {
        "profile": profile.id, "user": user.id, "studentNo": profile.student_no,
        "name": profile.real_name, "orientation": orientation.id,
        "paymentVersion": int(account.version or 0),
    }
    db.close()
    return result


def test_o4_server_verdict_green_idempotency_payment_cas_and_exception(
    client, db_mode, auth_headers,
):
    ids = _seed(db_mode)
    student_headers = _student_headers(
        ids["user"], ids["profile"], ids["studentNo"], ids["name"],
    )

    initial = client.get(
        f"/api/v1/orientation/qualifications/{ids['orientation']}", headers=auth_headers,
    )
    assert initial.status_code == 200, initial.text
    initial_data = initial.json()["data"]
    assert initial_data["verdict"] == "NOT_QUALIFIED"
    assert {item["code"] for item in initial_data["blockers"]} >= {"PAYMENT_INCOMPLETE"}
    assert initial_data["checkinEligibility"]["eligible"] is True
    assert {
        item["code"] for item in initial_data["checkinEligibility"]["followUps"]
    } >= {"PAYMENT_INCOMPLETE"}
    # 财务同步属于学校后台事项：不阻止学生领取到校二维码，学院最终确认仍用严格 verdict。
    issued_before_payment = client.post(
        "/api/v1/mobile/orientation/checkin-token", headers=student_headers,
    )
    assert issued_before_payment.status_code == 200, issued_before_payment.text

    submit_body = {
        "applyType": "缓缴学费", "applyAmount": 100, "remark": "家庭困难申请缓缴",
        "clientRequestId": "o4-green-submit-0001", "fileIds": [],
    }
    created = client.post(
        "/api/v1/portal/orientation/green-channel", headers=student_headers, json=submit_body,
    )
    assert created.status_code == 200, created.text
    green = created.json()["data"]
    replay = client.post(
        "/api/v1/portal/orientation/green-channel", headers=student_headers, json=submit_body,
    )
    assert replay.status_code == 200 and replay.json()["data"]["id"] == green["id"]
    changed = client.post(
        "/api/v1/portal/orientation/green-channel", headers=student_headers,
        json={**submit_body, "applyAmount": 99},
    )
    assert changed.status_code == 409

    approved = client.post(
        f"/api/v1/orientation/green-channels/{green['id']}/approve",
        headers=auth_headers, json={"expectedVersion": green["version"], "remark": "材料核验通过"},
    )
    assert approved.status_code == 200, approved.text
    stale = client.post(
        f"/api/v1/orientation/green-channels/{green['id']}/approve",
        headers=auth_headers, json={"expectedVersion": green["version"], "remark": "重复确认"},
    )
    assert stale.status_code == 409

    qualified = client.post(
        f"/api/v1/orientation/qualifications/{ids['orientation']}/recalculate",
        headers=auth_headers,
    )
    assert qualified.status_code == 200, qualified.text
    assert qualified.json()["data"]["verdict"] == "QUALIFIED"

    payment = client.put(
        f"/api/v1/orientation/payments/{ids['orientation']}", headers=auth_headers,
        json={
            "expectedVersion": ids["paymentVersion"], "payableAmount": 100,
            "paidAmount": 100, "status": "PAID", "sourceType": "MANUAL_VERIFIED",
            "sourceBizId": "finance-o4-0001",
        },
    )
    assert payment.status_code == 200, payment.text
    assert payment.json()["data"]["qualification"]["verdict"] == "QUALIFIED"
    stale_payment = client.put(
        f"/api/v1/orientation/payments/{ids['orientation']}", headers=auth_headers,
        json={
            "expectedVersion": ids["paymentVersion"], "payableAmount": 100,
            "paidAmount": 100, "status": "PAID", "sourceType": "MANUAL_VERIFIED",
            "sourceBizId": "finance-o4-0002",
        },
    )
    assert stale_payment.status_code == 409

    from app.db.session import get_sessionmaker
    from app.models import OrientationException
    db = get_sessionmaker()()
    db.add(OrientationException(
        tenant_id=TID, ori_student_id=ids["orientation"], exception_type="IDENTITY",
        description="证件信息仍需线下复核", risk_level="HIGH", status="OPEN",
    ))
    db.commit(); db.close()
    blocked = client.post(
        f"/api/v1/orientation/qualifications/{ids['orientation']}/recalculate",
        headers=auth_headers,
    )
    assert blocked.status_code == 200
    assert blocked.json()["data"]["verdict"] == "NOT_QUALIFIED"
    assert blocked.json()["data"]["checkinEligibility"]["eligible"] is False
    assert any(
        item["code"] == "OPEN_EXCEPTION_IDENTITY"
        for item in blocked.json()["data"]["blockers"]
    )


def test_o4_migration_is_serial_preflighted_and_downgrade_safe():
    source = (
        Path(__file__).parents[1] / "alembic" / "versions"
        / "20260901_orientation_qualification_o4.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision = "20260901_dorm_checkout_d4"' in source
    assert "O4 preflight failed before DDL" in source
    assert source.index("_preflight()") < source.index("op.add_column(")
    assert "O4 downgrade blocked: qualification decisions exist" in source
    assert "t_orientation_payment_account" in source
    assert "t_orientation_material_requirement" in source
    assert "t_orientation_qualification_decision" in source
