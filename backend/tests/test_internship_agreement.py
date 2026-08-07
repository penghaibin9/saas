"""三方协议：批次、三方职责、版本锁、学生新版入口、附件与审计。"""
from __future__ import annotations

import io

TID = 1000000000000000001
INT = "/api/v1/internship"
MOBILE = "/api/v1/mobile/internship/context/agreements"


def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _mentor(name, tid=TID):
    from app.core.security import create_access_token
    user_id = {"刘强": "9001", "王芳": "9002"}.get(name, "9099")
    return {"Authorization": "Bearer " + create_access_token({
        "userId": user_id, "realName": name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(tid), "activeContextId": "ctx",
        "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _student(student_no, batch_id, tid=TID):
    from app.core.security import create_access_token
    return {
        "Authorization": "Bearer " + create_access_token({
            "userId": f"u-{student_no}", "realName": "学生", "userType": "STUDENT",
            "tid": "x", "tenantId": str(tid), "studentNo": student_no,
            "currentRoleCode": "STUDENT", "clientType": "MP"}),
        "X-Internship-Batch-Id": str(batch_id),
    }


def _seed(db_mode):
    from uuid import uuid4
    from app.db.session import get_sessionmaker
    from app.models import InternshipBatch, InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    ids = {}
    try:
        batch = InternshipBatch(
            tenant_id=TID, batch_name="协议测试批次",
            batch_no=f"AG-{uuid4().hex[:8]}", status="RUNNING", planned_count=2)
        db.add(batch); db.flush(); ids["batch"] = batch.id
        for number, name, advisor, key in [
            ("AG-A", "甲", "刘强", "a"), ("AG-B", "乙", "王芳", "b")
        ]:
            student = StudentProfile(
                tenant_id=TID, student_no=number, real_name=name,
                current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(student); db.flush()
            record = InternshipRecord(
                tenant_id=TID, student_id=student.id, advisor_name=advisor,
                enterprise_name="测试企业", position_name="实习生",
                status="ONBOARD", risk_level="NONE", batch_id=batch.id)
            db.add(record); db.flush(); ids[f"rec_{key}"] = record.id
        db.commit()
        return ids
    finally:
        db.close()


def _file(client, headers):
    uploaded = client.post(
        "/api/v1/files",
        headers=headers,
        files={"file": (
            "agreement.txt",
            io.BytesIO(b"signed-three-party-agreement-evidence"),
            "text/plain",
        )},
        data={"bizType": "INTERNSHIP_AGREEMENT"},
    )
    assert uploaded.status_code == 200, uploaded.text
    data = uploaded.json()["data"]
    assert data["temporary"] is True and data["bindingCreated"] is False
    return data["fileId"]


def _generate_and_issue(client, record_id, mentor):
    generated = client.post(
        f"{INT}/agreements", json={"internshipId": str(record_id)}, headers=mentor)
    assert generated.status_code == 200
    data = generated.json()["data"]
    issued = client.post(
        f"{INT}/agreements/{data['id']}/issue",
        json={"expectedVersion": data["version"]}, headers=mentor)
    assert issued.status_code == 200
    return data["id"], issued.json()["data"]["version"]


def test_full_three_party_flow(client, db_mode):
    ids = _seed(db_mode)
    mentor = _mentor("刘强")
    file_id = _file(client, mentor)
    agreement_id, version = _generate_and_issue(client, ids["rec_a"], mentor)

    duplicate = client.post(
        f"{INT}/agreements", json={"internshipId": str(ids['rec_a'])}, headers=mentor)
    assert duplicate.status_code == 409

    student_confirm = client.post(
        f"{MOBILE}/{agreement_id}/confirm",
        json={
            "action": "CONFIRM",
            "expectedVersion": version,
            "batchId": ids["batch"],
            "internshipId": ids["rec_a"],
        },
        headers=_student("AG-A", ids["batch"]))
    assert student_confirm.status_code == 200
    version = student_confirm.json()["data"]["version"]

    missing_file = client.post(
        f"{INT}/agreements/{agreement_id}/enterprise-confirm",
        json={"confirmBy": "企业HR", "expectedVersion": version}, headers=mentor)
    assert missing_file.status_code == 400

    enterprise_confirm = client.post(
        f"{INT}/agreements/{agreement_id}/enterprise-confirm",
        json={"confirmBy": "企业HR", "fileId": file_id, "expectedVersion": version},
        headers=mentor)
    assert enterprise_confirm.status_code == 200, enterprise_confirm.json()
    version = enterprise_confirm.json()["data"]["version"]

    school_confirm = client.post(
        f"{INT}/agreements/{agreement_id}/school-confirm",
        json={"expectedVersion": version}, headers=_admin(client))
    assert school_confirm.status_code == 200
    version = school_confirm.json()["data"]["version"]

    archived = client.post(
        f"{INT}/agreements/{agreement_id}/archive",
        json={"expectedVersion": version}, headers=mentor)
    assert archived.status_code == 200

    detail = client.get(f"{INT}/agreements/{agreement_id}", headers=mentor).json()["data"]
    assert detail["attachment"]["fileName"] == "agreement.txt"
    actions = {item["action"] for item in detail["auditTrail"]}
    assert {"GENERATE", "ISSUE", "STUDENT_CONFIRM", "ENTERPRISE_CONFIRM",
            "SCHOOL_CONFIRM", "ARCHIVE"} <= actions


def test_student_reject_and_legacy_route_is_disabled(client, db_mode):
    ids = _seed(db_mode)
    mentor = _mentor("刘强")
    agreement_id, version = _generate_and_issue(client, ids["rec_a"], mentor)
    student_headers = _student("AG-A", ids["batch"])

    legacy = client.post(
        f"/api/v1/mobile/internship/agreements/{agreement_id}/confirm",
        json={"action": "REJECT", "reason": "岗位与专业不符，暂不确认",
              "expectedVersion": version}, headers=student_headers)
    assert legacy.status_code == 400

    result = client.post(
        f"{MOBILE}/{agreement_id}/confirm",
        json={"action": "REJECT", "reason": "岗位与专业不符，暂不确认",
              "expectedVersion": version, "batchId": ids["batch"],
              "internshipId": ids["rec_a"]}, headers=student_headers)
    assert result.status_code == 200
    assert result.json()["data"]["status"] == "REJECTED"


def test_owner_scope_and_school_confirm_boundary(client, db_mode):
    ids = _seed(db_mode)
    mentor_b = _mentor("王芳")
    created = client.post(
        f"{INT}/agreements",
        json={"internshipId": str(ids["rec_b"])},
        headers=mentor_b)
    assert created.status_code == 200
    agreement = created.json()["data"]
    agreement_id = agreement["id"]

    assert client.post(
        f"{INT}/agreements/{agreement_id}/issue",
        json={"expectedVersion": agreement["version"]},
        headers=_mentor("刘强")).status_code == 403

    issued = client.post(
        f"{INT}/agreements/{agreement_id}/issue",
        json={"expectedVersion": agreement["version"]},
        headers=mentor_b)
    assert issued.status_code == 200
    version = issued.json()["data"]["version"]

    assert client.post(
        f"{INT}/agreements/{agreement_id}/reject",
        json={"reason": "信息有误需要修改", "expectedVersion": version},
        headers=_mentor("刘强")).status_code == 403

    client.post(f"{INT}/agreements", json={"internshipId": str(ids["rec_a"])},
                headers=_mentor("刘强"))
    params = {"batchId": ids["batch"]}
    assert client.get(f"{INT}/agreements", params=params,
                      headers=_admin(client)).json()["data"]["total"] == 2
    assert client.get(f"{INT}/agreements", params=params,
                      headers=_mentor("刘强")).json()["data"]["total"] == 1


def test_staff_reject_pending_requires_version(client, db_mode):
    ids = _seed(db_mode)
    mentor = _mentor("刘强")
    agreement_id, version = _generate_and_issue(client, ids["rec_a"], mentor)
    assert client.post(
        f"{INT}/agreements/{agreement_id}/reject",
        json={"reason": "no", "expectedVersion": version}, headers=mentor).status_code == 400
    result = client.post(
        f"{INT}/agreements/{agreement_id}/reject",
        json={"reason": "信息有误需重新生成", "expectedVersion": version}, headers=mentor)
    assert result.status_code == 200
    assert result.json()["data"]["status"] == "REJECTED"


def test_student_forbidden_on_pc_and_export_is_batch_scoped(client, db_mode):
    ids = _seed(db_mode)
    student_headers = _student("AG-A", ids["batch"])
    assert client.get(f"{INT}/agreements", params={"batchId": ids["batch"]},
                      headers=student_headers).status_code == 403
    assert client.post(
        f"{INT}/agreements",
        json={"internshipId": str(ids["rec_a"])},
        headers=student_headers).status_code == 403
    client.post(f"{INT}/agreements", json={"internshipId": str(ids["rec_a"])},
                headers=_mentor("刘强"))
    exported = client.post(
        f"{INT}/agreements/export", params={"batchId": ids["batch"]}, headers=_admin(client))
    assert exported.status_code == 200
    data = exported.json()["data"]
    assert data["filename"].endswith(".xlsx") and data["rowCount"] == 1
