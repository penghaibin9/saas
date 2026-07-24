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


def _record(db_mode, no: str, advisor: str = "申请审核老师", batch_id=None) -> int:
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    try:
        stu = StudentProfile(tenant_id=TID, student_no=no, real_name="申请测试学生",
                             current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        db.add(stu); db.flush()
        rec = InternshipRecord(tenant_id=TID, student_id=stu.id, advisor_name=advisor,
                               status="PREPARING", eligibility_status="QUALIFIED",
                               destination_type="NONE", risk_level="NONE", batch_id=batch_id)
        db.add(rec); db.commit()
        return rec.id
    finally:
        db.close()


_RIGHTS_FACTS = {
    "workContent": "参与前端页面开发与联调", "dailyHours": 8, "weeklyHours": 40,
    "nightShift": False, "overtimeAllowed": False, "restDaysPerWeek": 2,
    "remunerationType": "MONTHLY", "accommodationProvided": True,
    "mealProvided": True, "hazardousFlag": False,
    "remunerationAmount": 2000, "remunerationCycle": "MONTHLY",
}


def _mk_batch(client, headers):
    from uuid import uuid4
    b = client.post("/api/v1/internship/batches", headers=headers, json={
        "batchName": f"申请测试批次-{uuid4().hex[:6]}", "batchNo": f"APPB-{uuid4().hex[:8]}",
        "startDate": "2026-03-01", "endDate": "2026-08-31", "plannedCount": 10}).json()
    bid = b["data"]["id"]
    assert client.post(f"/api/v1/internship/batches/{bid}/activate", headers=headers,
                       json={"expectedVersion": 0}).json()["code"] == 0
    return bid


def _published_position(client, headers, batch_id=None):
    if batch_id is None:
        batch_id = _mk_batch(client, headers)
    company = client.post(ENT, headers=headers, json={
        "name": "申请闭环企业", "creditCode": "91310000APP0001X",
    }).json()["data"]["id"]
    assert client.post(f"{ENT}/{company}/review", headers=headers, json={"action": "APPROVE"}).json()["code"] == 0
    position = client.post(POS, headers=headers, json={
        "companyId": company, "title": "申请闭环岗位", "workLocation": "上海市浦东新区",
        "headcount": 1, "batchId": str(batch_id), **_RIGHTS_FACTS,
    }).json()["data"]["id"]
    assert client.post(f"{POS}/{position}/status", headers=headers, json={"action": "SUBMIT"}).json()["code"] == 0
    assert client.post(f"{POS}/{position}/status", headers=headers, json={"action": "PUBLISH"}).json()["code"] == 0
    return position


def test_position_application_review_uses_real_assignment(client, auth_headers, db_mode):
    batch_id = _mk_batch(client, auth_headers)
    rec_id = _record(db_mode, "APP-POS-001", batch_id=batch_id)
    position_id = _published_position(client, auth_headers, batch_id=batch_id)
    student = _student_header("APP-POS-001")
    draft = client.put(f"{MOB}/internship/applications", headers=student, json={
        "applicationType": "POSITION", "volunteerNo": 1, "positionId": position_id,
        "applicationNote": "希望申请该岗位",
    })
    assert draft.status_code == 200 and draft.json()["data"]["status"] == "DRAFT"
    app_id = draft.json()["data"]["id"]
    submitted = client.post(f"{MOB}/internship/applications/{app_id}/submit", headers=student)
    assert submitted.status_code == 200 and submitted.json()["data"]["status"] == "PENDING_REVIEW"
    ver = int(submitted.json()["data"].get("version") or 0)
    # POSITION 类型审核通过会真实落岗（写实习学生记录），须单独回传该记录的 expectedVersion
    record_ver = int(submitted.json()["data"].get("recordVersion") or 0)
    review = client.post(f"{APP}/{app_id}/review", headers=auth_headers,
                         json={"action": "APPROVE", "expectedVersion": ver,
                               "recordExpectedVersion": record_ver})
    assert review.status_code == 200 and review.json()["data"]["status"] == "APPROVED", review.json()
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
    student = _student_header("APP-SELF-001")
    missing = client.put(f"{MOB}/internship/applications", headers=student, json={
        "applicationType": "SELF_ARRANGED", "companyName": "自主实习单位", "positionName": "技术员",
    })
    assert missing.status_code == 200
    app_id = missing.json()["data"]["id"]
    assert client.post(f"{MOB}/internship/applications/{app_id}/submit", headers=student).status_code == 400
    from app.db.session import get_sessionmaker
    from app.models import FileObject
    db = get_sessionmaker()()
    try:
        # 对象级授权：学生附件必须可被本人 meta 校验（biz_id=学号）
        file = FileObject(
            tenant_id=TID, file_key="test/self-arranged.pdf", file_name="证明.pdf",
            ext="pdf", size_bytes=12, status="AVAILABLE", visibility="BIZ_SCOPED",
            biz_type="INTERNSHIP_APPLICATION", biz_id="APP-SELF-001",
        )
        db.add(file); db.commit(); file_id = str(file.id)
    finally:
        db.close()
    draft = client.put(f"{MOB}/internship/applications", headers=student, json={
        "id": app_id, "applicationType": "SELF_ARRANGED", "companyName": "自主实习单位",
        "positionName": "技术员", "workAddress": "上海市浦东新区实习路1号", "contactName": "企业联系人",
        "contactPhone": "13800138000", "evidenceFileId": file_id,
    })
    assert draft.status_code == 200, draft.json()
    submitted = client.post(f"{MOB}/internship/applications/{app_id}/submit", headers=student).json()
    assert submitted["code"] == 0, submitted
    ver = int(submitted["data"].get("version") or 0)
    # SELF_ARRANGED 类型通过审核时会同时写实习学生记录（去向/企业/岗位名），
    # 须单独回传该记录的 expectedVersion（乐观锁），与申请自身的版本号是两回事
    record_ver = int(submitted["data"].get("recordVersion") or 0)
    review = client.post(f"{APP}/{app_id}/review", headers=auth_headers,
                         json={"action": "APPROVE", "expectedVersion": ver,
                               "recordExpectedVersion": record_ver})
    assert review.status_code == 200 and review.json()["data"]["status"] == "APPROVED", (submitted, review.json())
    detail = client.get(f"{APP}/{app_id}", headers=auth_headers).json()["data"]
    assert detail["evidenceFileId"] == file_id
    assert {x["action"] for x in detail["auditTrail"]} >= {"SAVE_DRAFT", "SUBMIT", "APPROVE"}


def test_approve_rolls_back_when_position_full(client, auth_headers, db_mode):
    """落岗失败不得留下「已通过但未落实」：申请应回到待审并记 APPROVE_ROLLBACK。"""
    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord, StudentProfile

    company = client.post(ENT, headers=auth_headers, json={
        "name": "满员回滚企业", "creditCode": "91310000APPFULL1X",
    }).json()["data"]["id"]
    assert client.post(f"{ENT}/{company}/review", headers=auth_headers, json={"action": "APPROVE"}).json()["code"] == 0
    batch_id = _mk_batch(client, auth_headers)
    position = client.post(POS, headers=auth_headers, json={
        "companyId": company, "title": "满员回滚岗位", "workLocation": "上海市浦东新区",
        "headcount": 1, "batchId": str(batch_id), **_RIGHTS_FACTS,
    }).json()["data"]["id"]
    assert client.post(f"{POS}/{position}/status", headers=auth_headers, json={"action": "SUBMIT"}).json()["code"] == 0
    assert client.post(f"{POS}/{position}/status", headers=auth_headers, json={"action": "PUBLISH"}).json()["code"] == 0

    # 先提交申请（此时仍有名额），再被人占满，审核落岗才应失败并回滚
    _record(db_mode, "APP-FULL-002", batch_id=batch_id)
    student = _student_header("APP-FULL-002")
    draft = client.put(f"{MOB}/internship/applications", headers=student, json={
        "applicationType": "POSITION", "volunteerNo": 1, "positionId": position,
        "applicationNote": "希望申请该岗位",
    }).json()
    assert draft["code"] == 0, draft
    app_id = draft["data"]["id"]
    submitted = client.post(f"{MOB}/internship/applications/{app_id}/submit", headers=student).json()
    assert submitted["code"] == 0, submitted
    ver = int(submitted["data"].get("version") or 0)
    record_ver = int(submitted["data"].get("recordVersion") or 0)

    rec1 = _record(db_mode, "APP-FULL-001", batch_id=batch_id)
    assign = client.post(
        f"/api/v1/internship/intern-students/{rec1}/assign",
        headers=auth_headers, json={"positionId": position, "expectedVersion": 0},
    ).json()
    assert assign["code"] == 0, assign

    review = client.post(f"{APP}/{app_id}/review", headers=auth_headers,
                         json={"action": "APPROVE", "expectedVersion": ver,
                               "recordExpectedVersion": record_ver})
    body = review.json()
    assert body["code"] != 0, body
    detail = client.get(f"{APP}/{app_id}", headers=auth_headers).json()["data"]
    assert detail["status"] == "PENDING_REVIEW"
    assert "APPROVE_ROLLBACK" in {x["action"] for x in detail["auditTrail"]}

    db = get_sessionmaker()()
    try:
        stu = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == TID, StudentProfile.student_no == "APP-FULL-002")).one()
        rec = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == TID, InternshipRecord.student_id == stu.id)).one()
        assert rec.position_id is None
        assert (rec.destination_type or "NONE") in ("NONE", None, "")
    finally:
        db.close()
