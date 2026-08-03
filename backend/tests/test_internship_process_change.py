"""岗位实习 · 过程报告（月报/总结）+ 实习变更 + 学生企业/岗位评价。"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001
INT = "/api/v1/internship"
MOB = "/api/v1/mobile"


def _admin(client):
    d = client.post("/api/v1/auth/mock-login",
                    json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {d['accessToken']}"}


def _student(sno="PC-STU-01"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-stu-pc", "realName": "过程报告学生", "userType": "STUDENT", "tid": "x",
        "tenantId": str(TID), "studentNo": sno, "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _mentor(name="刘强"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(TID), "activeContextId": "ctx",
        "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import EmpCompany, InternshipBatch, InternshipPosition, InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    try:
        batch = InternshipBatch(
            tenant_id=TID, batch_name="过程变更批次", batch_no=f"PC-{datetime.utcnow().strftime('%H%M%S%f')}",
            status="RUNNING", planned_count=10,
            rules_config={"compliance": {"workRights": {"requireEnterpriseAccess": False}}})
        db.add(batch)
        db.flush()
        old_company = EmpCompany(
            tenant_id=TID, name="原企业", status="ACTIVE", coop_status="ACTIVE",
            qualification_status="PASSED", blacklist=False)
        target_company = EmpCompany(
            tenant_id=TID, name="新企业A", status="ACTIVE", coop_status="ACTIVE",
            qualification_status="PASSED", blacklist=False)
        db.add_all([old_company, target_company])
        db.flush()
        old_position = InternshipPosition(
            tenant_id=TID, company_id=old_company.id, company_name=old_company.name,
            batch_id=batch.id, title="原岗位", work_location="原工作地点",
            headcount=3, allocated_count=1, status="PUBLISHED")
        target_position = InternshipPosition(
            tenant_id=TID, company_id=target_company.id, company_name=target_company.name,
            batch_id=batch.id, title="新岗位B", work_location="新工作地点",
            work_address="新企业A生产实训区", work_content="从事专业对口的生产实训与质量记录",
            daily_hours=8, weekly_hours=40, night_shift=False, overtime_allowed=False,
            rest_days_per_week=2, remuneration_type="UNPAID",
            accommodation_provided=False, meal_provided=False, hazardous_flag=False,
            headcount=3, allocated_count=0, status="PUBLISHED")
        db.add_all([old_position, target_position])
        db.flush()
        s = StudentProfile(tenant_id=TID, student_no="PC-STU-01", real_name="过程学生",
                           current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
        db.add(s)
        db.flush()
        r = InternshipRecord(
            tenant_id=TID, student_id=s.id, batch_id=batch.id, advisor_name="刘强",
            enterprise_id=old_company.id, position_id=old_position.id,
            enterprise_name=old_company.name, position_name=old_position.title,
            destination_type="ASSIGNED", status="ONBOARD", risk_level="NONE")
        db.add(r)
        db.flush()
        db.commit()
        return {
            "rec_id": r.id, "stu_id": s.id, "batch_id": batch.id,
            "old_position_id": old_position.id,
            "target_company_id": target_company.id,
            "target_position_id": target_position.id,
        }
    finally:
        db.close()


def test_process_report_submit_and_review(client, db_mode):
    ids = _seed(db_mode)
    content = "今" * 35
    sub = client.post(f"{MOB}/internship/process-report",
                      json={"reportType": "DAILY", "periodKey": "2026-07-10", "content": content},
                      headers=_student())
    assert sub.status_code == 200 and sub.json()["code"] == 0
    rid = sub.json()["data"]["id"]
    lst = client.get(f"{INT}/process-reports",
                     params={"reportType": "DAILY", "batchId": str(ids["batch_id"])},
                     headers=_mentor("刘强"))
    assert lst.status_code == 200 and lst.json()["data"]["total"] >= 1
    detail = client.get(f"{INT}/process-reports/{rid}", headers=_mentor("刘强"))
    assert detail.status_code == 200
    assert detail.json()["data"]["id"] == rid
    assert detail.json()["data"]["content"] == content
    ver = int(detail.json()["data"].get("version") or 0)
    rev = client.post(f"{INT}/process-reports/{rid}/review",
                      json={"action": "APPROVE", "comment": "良好", "expectedVersion": ver},
                      headers=_mentor("刘强"))
    assert rev.status_code == 200 and rev.json()["data"]["status"] == "APPROVED"


def test_change_request_apply_and_review(client, db_mode):
    ids = _seed(db_mode)
    apply = client.post(
        f"{MOB}/internship/change-request",
        json={
            "changeType": "CHANGE_ENTERPRISE", "reason": "企业搬迁需换单位",
            "targetEnterpriseId": ids["target_company_id"],
            "targetPositionId": ids["target_position_id"],
            "targetEnterpriseName": "新企业A", "targetPositionName": "新岗位B",
        },
        headers=_student())
    assert apply.status_code == 200 and apply.json()["code"] == 0
    cid = apply.json()["data"]["id"]
    ver = int(apply.json()["data"].get("version") or 0)
    lst = client.get(f"{INT}/change-requests",
                     params={"status": "PENDING", "batchId": str(ids["batch_id"])},
                     headers=_mentor("刘强"))
    assert lst.status_code == 200
    assert any(x["id"] == cid for x in lst.json()["data"]["items"])
    assert client.get(f"{INT}/change-requests", headers=_mentor("刘强")).json()["code"] != 0
    rev = client.post(f"{INT}/change-requests/{cid}/review",
                      json={"action": "APPROVE", "comment": "同意变更", "expectedVersion": ver},
                      headers=_mentor("刘强"))
    assert rev.status_code == 200 and rev.json()["data"]["status"] == "APPROVED", rev.json()

    from app.db.session import get_sessionmaker
    from app.models import InternshipPosition, InternshipRecord
    db = get_sessionmaker()()
    try:
        record = db.get(InternshipRecord, ids["rec_id"])
        old_position = db.get(InternshipPosition, ids["old_position_id"])
        target_position = db.get(InternshipPosition, ids["target_position_id"])
        assert record.position_id == ids["target_position_id"]
        assert record.enterprise_id == ids["target_company_id"]
        assert record.enterprise_name == "新企业A" and record.position_name == "新岗位B"
        assert old_position.allocated_count == 0
        assert target_position.allocated_count == 1
    finally:
        db.close()


def test_change_position_requires_target_position_id(client, db_mode):
    """换岗缺 targetPositionId 不可申请，防止审过不落岗假通过。"""
    _seed(db_mode)
    bad = client.post(f"{MOB}/internship/change-request",
                      json={"changeType": "CHANGE_POSITION", "reason": "想换一个更对口的岗位"},
                      headers=_student())
    assert bad.status_code == 400 or bad.json().get("code") not in (0, None)
    assert "岗位" in (bad.json().get("message") or "")


def test_self_eval_enterprise_rating(client, db_mode):
    _seed(db_mode)
    body = {
        "selfSummary": "实习总结内容" * 20,
        "enterpriseRating": 4,
        "positionRating": 5,
        "enterpriseFeedback": "企业氛围好",
        "positionFeedback": "岗位匹配专业"
    }
    sub = client.post(f"{MOB}/internship/self-eval", json=body, headers=_student())
    assert sub.status_code == 200 and sub.json()["code"] == 0
    got = client.get(f"{MOB}/internship/self-eval", headers=_student())
    assert got.json()["data"]["enterpriseRating"] == 4
    assert got.json()["data"]["positionRating"] == 5

def test_stale_change_request_can_still_be_rejected(client, db_mode):
    ids = _seed(db_mode)
    response = client.post(
        f"{MOB}/internship/change-request",
        json={
            "changeType": "CHANGE_ENTERPRISE",
            "reason": "企业经营调整需变更单位",
            "targetEnterpriseId": ids["target_company_id"],
            "targetPositionId": ids["target_position_id"],
            "targetEnterpriseName": "新企业A",
            "targetPositionName": "新岗位B",
        },
        headers=_student(),
    )
    assert response.status_code == 200 and response.json()["code"] == 0
    change = response.json()["data"]

    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord
    db = get_sessionmaker()()
    try:
        record = db.get(InternshipRecord, ids["rec_id"])
        record.version = int(record.version or 0) + 1
        db.commit()
    finally:
        db.close()

    rejected = client.post(
        f"{INT}/change-requests/{change['id']}/review",
        json={
            "action": "REJECT",
            "comment": "主记录已变化，请重新提交申请",
            "expectedVersion": int(change.get("version") or 0),
        },
        headers=_mentor("刘强"),
    )
    assert rejected.status_code == 200, rejected.json()
    assert rejected.json()["data"]["status"] == "REJECTED"
