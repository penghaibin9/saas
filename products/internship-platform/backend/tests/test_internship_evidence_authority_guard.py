"""包 8：豁免证据冻结与自动失效反向测试。"""
from __future__ import annotations

import io
from datetime import datetime, timedelta

TID = 1000000000000000001
BASE = "/api/v1/internship/compliance"


def _admin(client):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_record(db_mode):
    from uuid import uuid4
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, StudentProfile

    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="豁免证据测试批次",
            batch_no=f"EXEMPT-{uuid4().hex[:8]}",
            status="RUNNING",
            planned_count=1,
            rules_config={
                "compliance": {
                    "insurance": {"required": True, "severity": "BLOCK", "label": "实习保险"},
                    "studentConsent": {"required": False},
                    "safetyEducation": {"required": False},
                    "agreement": {"required": False},
                    "specialFiling": {"required": False},
                    "workRights": {"required": False},
                    "emergency": {"required": False},
                },
            },
        )
        student = StudentProfile(
            tenant_id=TID,
            student_no=f"EX-{uuid4().hex[:6]}",
            real_name="豁免证据学生",
            current_stage="INTERNSHIP",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add_all([batch, student])
        db.flush()
        record = InternshipRecord(
            tenant_id=TID,
            student_id=student.id,
            batch_id=batch.id,
            advisor_user_id=None,
            advisor_name=None,
            eligibility_status="QUALIFIED",
            status="PREPARING",
            destination_type="NONE",
            risk_level="NONE",
        )
        db.add(record)
        db.commit()
        return record.id
    finally:
        db.close()


def _upload(client, headers):
    response = client.post(
        "/api/v1/files",
        headers=headers,
        files={
            "file": (
                "insurance-exemption.txt",
                io.BytesIO(b"formal-insurance-exemption-evidence"),
                "text/plain",
            )
        },
        data={"bizType": "INTERNSHIP_COMPLIANCE_EXEMPTION"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["temporary"] is True
    return data["fileId"]


def test_exemption_freezes_file_binding_and_invalidates_on_hash_change(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipComplianceExemption
    from app.models.file import FileBinding, FileObject

    record_id = _seed_record(db_mode)
    headers = _admin(client)
    file_id = _upload(client, headers)
    requested = client.post(
        f"{BASE}/exemptions",
        headers=headers,
        json={
            "internshipId": str(record_id),
            "checkCode": "insurance",
            "reason": "学校核验特殊保险替代材料",
            "validUntil": (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z",
            "evidenceFileIds": [file_id],
        },
    )
    assert requested.status_code == 200, requested.json()
    exemption = requested.json()["data"]

    reviewed = client.post(
        f"{BASE}/exemptions/{exemption['id']}/review",
        headers=headers,
        json={"action": "APPROVE", "expectedVersion": exemption["version"]},
    )
    assert reviewed.status_code == 200, reviewed.json()
    assert reviewed.json()["data"]["status"] == "APPROVED"

    db = get_sessionmaker()()
    try:
        row = db.get(InternshipComplianceExemption, int(exemption["id"]))
        snapshots = row.evidence_file_ids
        assert snapshots and snapshots[0]["fileId"] == file_id
        assert str(snapshots[0]["bindingId"]).isdigit()
        assert len(snapshots[0]["fileSha256"]) == 64
        binding = db.get(FileBinding, int(snapshots[0]["bindingId"]))
        assert binding.status == "ACTIVE"
        assert binding.biz_type == "INTERNSHIP_COMPLIANCE_EXEMPTION"
        assert binding.biz_id == exemption["id"]
    finally:
        db.close()

    valid = client.get(
        f"{BASE}/evaluate/{record_id}",
        headers=headers,
        params={"operation": "ONBOARD"},
    )
    assert valid.status_code == 200, valid.json()
    insurance = next(
        item for item in valid.json()["data"]["items"]
        if item["code"] == "insurance"
    )
    assert insurance["status"] == "EXEMPTED"

    db = get_sessionmaker()()
    try:
        file_obj = db.get(FileObject, int(file_id))
        file_obj.sha256 = "0" * 64
        file_obj.version = int(file_obj.version or 0) + 1
        db.commit()
    finally:
        db.close()

    invalidated = client.get(
        f"{BASE}/evaluate/{record_id}",
        headers=headers,
        params={"operation": "ONBOARD"},
    )
    assert invalidated.status_code == 200, invalidated.json()
    insurance = next(
        item for item in invalidated.json()["data"]["items"]
        if item["code"] == "insurance"
    )
    assert insurance["status"] != "EXEMPTED"

    db = get_sessionmaker()()
    try:
        row = db.get(InternshipComplianceExemption, int(exemption["id"]))
        assert row.status == "INVALIDATED"
        assert int(row.version or 0) >= 2
    finally:
        db.close()


def test_legacy_id_only_exemption_cannot_be_approved(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import InternshipComplianceExemption

    record_id = _seed_record(db_mode)
    headers = _admin(client)
    db = get_sessionmaker()()
    try:
        row = InternshipComplianceExemption(
            tenant_id=TID,
            internship_id=record_id,
            check_code="insurance",
            reason="历史仅保存文件编号的豁免",
            evidence_file_ids=["123456"],
            valid_from=datetime.utcnow(),
            valid_until=datetime.utcnow() + timedelta(days=30),
            status="PENDING_REVIEW",
            requested_by_name="历史管理员",
        )
        db.add(row)
        db.commit()
        exemption_id = row.id
        version = int(row.version or 0)
    finally:
        db.close()

    reviewed = client.post(
        f"{BASE}/exemptions/{exemption_id}/review",
        headers=headers,
        json={"action": "APPROVE", "expectedVersion": version},
    )
    assert reviewed.status_code == 200, reviewed.json()
    assert reviewed.json()["data"]["status"] == "INVALIDATED"
    assert "快照" in reviewed.json()["data"]["invalidationReason"]
