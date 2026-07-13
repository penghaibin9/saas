"""Formal application: position allocation and self-arranged evidence are both closed loops."""
from __future__ import annotations

from app.core.security import create_access_token

TID = 1000000000000000001
MOB = "/api/v1/mobile"
APP = "/api/v1/internship/applications"
ENT = "/api/v1/internship/enterprises"
POS = "/api/v1/internship/positions"


def _student_header(no: str, name: str = "申请测试学生") -> dict:
    token = create_access_token({
        "userId": f"u-{no}", "realName": name, "userType": "STUDENT", "tid": "x",
        "tenantId": str(TID), "studentNo": no, "currentRoleCode": "STUDENT", "clientType": "MP",
    })
    return {"Authorization": f"Bearer {token}"}


def _record(db_mode, no: str, advisor: str = "申请审核老师") -> int:
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    try:
        stu = StudentProfile(tenant_id=TID, student_no=no, real_name="申请测试学生",
                             current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        db.add(stu); db.flush()
        rec = InternshipRecord(tenant_id=TID, student_id=stu.id, advisor_name=advisor,
                               status="PREPARING", eligibility_status="QUALIFIED",
                               destination_type="NONE", risk_level="NONE")
        db.add(rec); db.commit()
        return rec.id
    finally:
        db.close()


def _published_position(client, headers):
    company = client.post(ENT, headers=headers, json={
        "name": "申请闭环企业", "creditCode": "91310000APP0001X",
    }).json()["data"]["id"]
    assert client.post(f"{ENT}/{company}/review", headers=headers, json={"action": "APPROVE"}).json()["code"] == 0
    position = client.post(POS, headers=headers, json={
        "companyId": company, "title": "申请闭环岗位", "workLocation": "上海市浦东新区",
        "headcount": 1,
    }).json()["data"]["id"]
    assert client.post(f"{POS}/{position}/status", headers=headers, json={"action": "SUBMIT"}).json()["code"] == 0
    assert client.post(f"{POS}/{position}/status", headers=headers, json={"action": "PUBLISH"}).json()["code"] == 0
    return position


def test_position_application_review_uses_real_assignment(client, auth_headers, db_mode):
    rec_id = _record(db_mode, "APP-POS-001")
    position_id = _published_position(client, auth_headers)
    student = _student_header("APP-POS-001")
    draft = client.put(f"{MOB}/internship/applications", headers=student, json={
        "applicationType": "POSITION", "volunteerNo": 1, "positionId": position_id,
        "applicationNote": "希望申请该岗位",
    })
    assert draft.status_code == 200 and draft.json()["data"]["status"] == "DRAFT"
    app_id = draft.json()["data"]["id"]
    submitted = client.post(f"{MOB}/internship/applications/{app_id}/submit", headers=student)
    assert submitted.status_code == 200 and submitted.json()["data"]["status"] == "PENDING_REVIEW"
    review = client.post(f"{APP}/{app_id}/review", headers=auth_headers, json={"action": "APPROVE"})
    assert review.status_code == 200 and review.json()["data"]["status"] == "APPROVED"
    from app.db.session import get_sessionmaker
    from app.models import InternshipPosition, InternshipRecord
    db = get_sessionmaker()()
    try:
        rec = db.get(InternshipRecord, rec_id)
        pos = db.get(InternshipPosition, int(position_id))
        assert rec.position_id == int(position_id) and rec.destination_type == "ASSIGNED"
        assert pos.allocated_count == 1 and pos.status == "FULL"
    finally:
        db.close()


def test_self_arranged_application_requires_evidence_and_is_audited(client, auth_headers, db_mode):
    _record(db_mode, "APP-SELF-001")
    from app.db.session import get_sessionmaker
    from app.models import FileObject
    db = get_sessionmaker()()
    try:
        file = FileObject(tenant_id=TID, file_key="test/self-arranged.pdf", file_name="证明.pdf",
                          ext="pdf", size_bytes=12, status="STORED")
        db.add(file); db.commit(); file_id = str(file.id)
    finally:
        db.close()
    student = _student_header("APP-SELF-001")
    missing = client.put(f"{MOB}/internship/applications", headers=student, json={
        "applicationType": "SELF_ARRANGED", "companyName": "自主实习单位", "positionName": "技术员",
    })
    assert missing.status_code == 200
    app_id = missing.json()["data"]["id"]
    assert client.post(f"{MOB}/internship/applications/{app_id}/submit", headers=student).status_code == 400
    draft = client.put(f"{MOB}/internship/applications", headers=student, json={
        "id": app_id, "applicationType": "SELF_ARRANGED", "companyName": "自主实习单位",
        "positionName": "技术员", "workAddress": "上海市浦东新区实习路1号", "contactName": "企业联系人",
        "contactPhone": "13800138000", "evidenceFileId": file_id,
    })
    assert draft.status_code == 200
    assert client.post(f"{MOB}/internship/applications/{app_id}/submit", headers=student).json()["code"] == 0
    review = client.post(f"{APP}/{app_id}/review", headers=auth_headers, json={"action": "APPROVE"})
    assert review.status_code == 200 and review.json()["data"]["status"] == "APPROVED"
    detail = client.get(f"{APP}/{app_id}", headers=auth_headers).json()["data"]
    assert detail["evidenceFileId"] == file_id
    assert {x["action"] for x in detail["auditTrail"]} >= {"SAVE_DRAFT", "SUBMIT", "APPROVE"}
