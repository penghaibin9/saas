"""实习成绩：权重快照、权威来源、ASSESSING 门禁、发布合规与版本锁。"""
from __future__ import annotations

import io
from datetime import date

TID = 1000000000000000001
INT = "/api/v1/internship"


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


def _student(student_no, tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": "学生", "userType": "STUDENT",
        "tid": "x", "tenantId": str(tid), "studentNo": student_no,
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    """两名学生均具备进入 ASSESS 的正式基础事实；评价仍通过真实 API 生成。"""
    from uuid import uuid4
    from app.db.session import get_sessionmaker
    from app.models import (
        EmpCompany, InternshipAgreement, InternshipBatch, InternshipInsurance,
        InternshipPosition, InternshipRecord, StudentProfile,
    )
    db = get_sessionmaker()()
    ids = {}
    try:
        batch = InternshipBatch(
            tenant_id=TID, batch_name="成绩测试批次",
            batch_no=f"SCORE-{uuid4().hex[:8]}", status="RUNNING", planned_count=2,
            end_date=date.today(),
            rules_config={"compliance": {"studentConsent": {
                "requireGuardianConsentForMinor": False,
            }}},
        )
        db.add(batch); db.flush(); ids["batch"] = batch.id
        company = EmpCompany(
            tenant_id=TID, name="成绩测试企业",
            credit_code=f"91310000SC{uuid4().hex[:6].upper()}", coop_status="ACTIVE",
        )
        db.add(company); db.flush()
        position = InternshipPosition(
            tenant_id=TID, company_id=company.id, company_name=company.name,
            title="实习生", batch_id=batch.id, status="PUBLISHED", headcount=5,
        )
        db.add(position); db.flush()
        for number, name, advisor, key in [
            ("SC-A", "甲", "刘强", "a"), ("SC-B", "乙", "王芳", "b")
        ]:
            student = StudentProfile(
                tenant_id=TID, student_no=number, real_name=name,
                current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(student); db.flush()
            record = InternshipRecord(
                tenant_id=TID, student_id=student.id, advisor_name=advisor,
                enterprise_name=company.name, position_name=position.title,
                enterprise_id=company.id, position_id=position.id,
                eligibility_status="QUALIFIED", status="ASSESSING",
                risk_level="NONE", batch_id=batch.id)
            db.add(record); db.flush(); ids[f"rec_{key}"] = record.id
            ids[f"stu_{key}"] = student.id
            db.add(InternshipInsurance(
                tenant_id=TID, internship_id=record.id,
                student_id=student.id, status="VERIFIED"))
            db.add(InternshipAgreement(
                tenant_id=TID, internship_id=record.id,
                student_id=student.id, status="EFFECTIVE"))
        db.commit(); return ids
    finally:
        db.close()


def _config(client, **overrides):
    body = {
        "checkinWeight": 20, "weeklyWeight": 20, "monthlyWeight": 10,
        "enterpriseWeight": 30, "schoolWeight": 20, "passLine": 60,
        **overrides,
    }
    return client.post(f"{INT}/scores/config", json=body, headers=_admin(client))


def _upload_enterprise_evidence(client, headers) -> str:
    uploaded = client.post(
        "/api/v1/files",
        headers=headers,
        files={"file": (
            "enterprise-eval.txt",
            io.BytesIO(b"authoritative-enterprise-evaluation-evidence"),
            "text/plain",
        )},
        data={"bizType": "INTERNSHIP_ENTERPRISE_EVAL"},
    )
    assert uploaded.status_code == 200, uploaded.text
    data = uploaded.json()["data"]
    assert data["temporary"] is True and data["bindingCreated"] is False
    return data["fileId"]


def _approve_enterprise_eval(client, record_id, mentor_name="刘强", component_score=60):
    mentor_headers = _mentor(mentor_name)
    evidence_file_id = _upload_enterprise_evidence(client, mentor_headers)
    created = client.post(
        f"{INT}/enterprise-evals",
        json={
            "internshipId": str(record_id), "mentorName": "企业导师",
            "attendanceScore": component_score, "skillScore": component_score,
            "attitudeScore": component_score, "collaborationScore": component_score,
            "safetyScore": component_score, "sourceFileId": evidence_file_id,
        },
        headers=mentor_headers,
    )
    assert created.status_code == 200, created.json()
    data = created.json()["data"]
    reviewed = client.post(
        f"{INT}/enterprise-evals/{data['id']}/review-versioned",
        json={"action": "APPROVE", "expectedVersion": data["version"]},
        headers=_admin(client),
    )
    assert reviewed.status_code == 200, reviewed.json()
    return data["id"]


def _compute(client, ids, key="a", mentor="刘强", scores=None):
    values = scores or {
        "checkinScore": 90, "weeklyScore": 80,
        "monthlyScore": 70, "schoolScore": 100,
    }
    return client.post(
        f"{INT}/scores/compute",
        json={"internshipId": str(ids[f"rec_{key}"]), **values},
        headers=_mentor(mentor),
    )


def test_config_weight_sum_and_snapshot(client, db_mode):
    ids = _seed(db_mode)
    bad = _config(client, schoolWeight=30)
    assert bad.status_code == 400
    first = _config(client).json()["data"]
    assert first["configId"]

    current = client.get(f"{INT}/scores/config", headers=_admin(client)).json()["data"]
    assert current["enterpriseWeight"] == 30
    assert current["passLine"] == 60
    assert current["configId"] == first["configId"]

    denied = client.post(
        f"{INT}/scores/config",
        json={"checkinWeight": 20, "weeklyWeight": 20, "monthlyWeight": 10,
              "enterpriseWeight": 30, "schoolWeight": 20},
        headers=_mentor("刘强"))
    assert denied.status_code == 403

    _approve_enterprise_eval(client, ids["rec_a"], component_score=80)
    computed = _compute(client, ids, scores={
        "checkinScore": 80, "weeklyScore": 80, "monthlyScore": 80, "schoolScore": 80})
    assert computed.status_code == 200, computed.json()
    detail = client.get(
        f"{INT}/scores/{computed.json()['data']['id']}", headers=_mentor("刘强")).json()["data"]
    assert detail["scoreConfigId"] == first["configId"]
    assert detail["scoreConfigVersion"] >= 1

    second = _config(client, checkinWeight=10, weeklyWeight=10,
                     enterpriseWeight=40, schoolWeight=30).json()["data"]
    assert second["configId"] != first["configId"]


def test_compute_and_school_publish_with_versions(client, db_mode):
    ids = _seed(db_mode)
    _config(client)
    _approve_enterprise_eval(client, ids["rec_a"], component_score=60)
    computed = _compute(client, ids)
    assert computed.status_code == 200, computed.json()
    score = computed.json()["data"]
    assert score["total"] == 79.0 and score["incomplete"] is False and score["isPass"] is True

    mentor_publish = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]}, headers=_mentor("刘强"))
    assert mentor_publish.status_code == 403

    published = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]}, headers=_admin(client))
    assert published.status_code == 200, published.json()
    published_data = published.json()["data"]
    assert published_data["status"] == "PUBLISHED"

    detail = client.get(f"{INT}/scores/{score['id']}", headers=_mentor("刘强")).json()["data"]
    assert {"COMPUTE", "PUBLISH"} <= {item["action"] for item in detail["auditTrail"]}
    stale = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]}, headers=_admin(client))
    assert stale.status_code == 409


def test_enterprise_score_is_authoritative_and_manual_override_rejected(client, db_mode):
    ids = _seed(db_mode)
    _config(client)
    _approve_enterprise_eval(client, ids["rec_a"], component_score=84)

    manual = client.post(
        f"{INT}/scores/compute",
        json={"internshipId": str(ids["rec_a"]), "checkinScore": 100,
              "weeklyScore": 100, "monthlyScore": 100,
              "enterpriseScore": 1, "schoolScore": 100},
        headers=_mentor("刘强"))
    assert manual.status_code == 400

    computed = _compute(client, ids, scores={
        "checkinScore": 100, "weeklyScore": 100,
        "monthlyScore": 100, "schoolScore": 100})
    assert computed.status_code == 200, computed.json()
    detail = client.get(
        f"{INT}/scores/{computed.json()['data']['id']}", headers=_mentor("刘强")).json()["data"]
    assert detail["enterpriseScore"] == 84
    assert detail["enterpriseSource"]["type"] == "APPROVED_ENTERPRISE_EVAL"


def test_incomplete_cannot_publish(client, db_mode):
    ids = _seed(db_mode)
    _config(client)
    computed = _compute(client, ids, scores={
        "checkinScore": 90, "weeklyScore": 80, "schoolScore": 100})
    assert computed.status_code == 200, computed.json()
    score = computed.json()["data"]
    assert score["incomplete"] is True
    denied = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]}, headers=_admin(client))
    assert denied.status_code == 409


def test_scope_student_forbidden_withdraw_and_export(client, db_mode):
    ids = _seed(db_mode)
    _config(client)
    _approve_enterprise_eval(client, ids["rec_a"], mentor_name="刘强", component_score=80)
    _approve_enterprise_eval(client, ids["rec_b"], mentor_name="王芳", component_score=80)
    score_a = _compute(client, ids, key="a", mentor="刘强", scores={
        "checkinScore": 80, "weeklyScore": 80, "monthlyScore": 80, "schoolScore": 80}).json()["data"]
    score_b = _compute(client, ids, key="b", mentor="王芳", scores={
        "checkinScore": 80, "weeklyScore": 80, "monthlyScore": 80, "schoolScore": 80}).json()["data"]

    assert client.get(
        f"{INT}/scores/{score_b['id']}", headers=_mentor("刘强")).status_code == 403
    params = {"batchId": ids["batch"]}
    assert client.get(f"{INT}/scores", params=params,
                      headers=_admin(client)).json()["data"]["total"] == 2
    assert client.get(f"{INT}/scores", params=params,
                      headers=_mentor("刘强")).json()["data"]["total"] == 1
    assert client.get(f"{INT}/scores", params=params,
                      headers=_student("SC-A")).status_code == 403
    assert client.post(
        f"{INT}/scores/compute",
        json={"internshipId": str(ids["rec_a"]), "checkinScore": 80,
              "weeklyScore": 80, "monthlyScore": 80, "schoolScore": 80},
        headers=_student("SC-A")).status_code == 403

    published = client.post(
        f"{INT}/scores/{score_a['id']}/publish",
        json={"expectedVersion": score_a["version"]}, headers=_admin(client)).json()["data"]
    too_short = client.post(
        f"{INT}/scores/{score_a['id']}/withdraw",
        json={"reason": "x", "expectedVersion": published["version"]}, headers=_admin(client))
    assert too_short.status_code == 400
    withdrawn = client.post(
        f"{INT}/scores/{score_a['id']}/withdraw",
        json={"reason": "成绩录入有误需要重新核算", "expectedVersion": published["version"]},
        headers=_admin(client))
    assert withdrawn.status_code == 200
    assert withdrawn.json()["data"]["status"] == "WITHDRAWN"

    exported = client.post(
        f"{INT}/scores/export", params=params, headers=_admin(client))
    assert exported.status_code == 200
    data = exported.json()["data"]
    assert data["filename"].endswith(".xlsx") and data["rowCount"] == 2


def test_wrong_stage_cannot_compute(client, db_mode):
    ids = _seed(db_mode)
    _approve_enterprise_eval(client, ids["rec_a"], component_score=80)
    from app.db.session import get_sessionmaker
    from app.models import InternshipRecord
    db = get_sessionmaker()()
    try:
        db.get(InternshipRecord, ids["rec_a"]).status = "ONBOARD"
        db.commit()
    finally:
        db.close()
    denied = _compute(client, ids)
    assert denied.status_code == 409
    assert "ASSESSING" in denied.json()["message"]


def test_publish_reruns_authoritative_assess_compliance(client, db_mode):
    ids = _seed(db_mode)
    _approve_enterprise_eval(client, ids["rec_a"], component_score=80)
    computed = _compute(client, ids, scores={
        "checkinScore": 80, "weeklyScore": 80,
        "monthlyScore": 80, "schoolScore": 80,
    })
    assert computed.status_code == 200, computed.json()
    score = computed.json()["data"]
    from app.db.session import get_sessionmaker
    from app.models import InternshipInsurance
    db = get_sessionmaker()()
    try:
        insurance = db.query(InternshipInsurance).filter_by(
            tenant_id=TID, internship_id=ids["rec_a"]).one()
        insurance.status = "PENDING"
        db.commit()
    finally:
        db.close()
    denied = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]}, headers=_admin(client))
    assert denied.status_code == 409
    assert denied.json()["details"]["blockers"]


def test_independent_score_archive_is_disabled(client, db_mode):
    ids = _seed(db_mode)
    _approve_enterprise_eval(client, ids["rec_a"], component_score=80)
    computed = _compute(client, ids, scores={
        "checkinScore": 80, "weeklyScore": 80,
        "monthlyScore": 80, "schoolScore": 80,
    }).json()["data"]
    published = client.post(
        f"{INT}/scores/{computed['id']}/publish",
        json={"expectedVersion": computed["version"]}, headers=_admin(client))
    assert published.status_code == 200, published.json()
    denied = client.post(
        f"{INT}/scores/{computed['id']}/archive",
        json={"expectedVersion": published.json()["data"]["version"]},
        headers=_admin(client))
    assert denied.status_code == 409
    assert "总档案归档" in denied.json()["message"]
