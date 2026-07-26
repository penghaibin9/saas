"""实习成绩：权重快照、企业评价权威来源、导师核算、学校发布与版本锁。"""
from __future__ import annotations

TID = 1000000000000000001
INT = "/api/v1/internship"


def _admin(client):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _mentor(name, tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "TEACHER",
        "tid": "x", "tenantId": str(tid), "activeContextId": "ctx",
        "currentRoleCode": "INTERN_MENTOR", "clientType": "PC"})}


def _student(student_no, tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}", "realName": "学生", "userType": "STUDENT",
        "tid": "x", "tenantId": str(tid), "studentNo": student_no,
        "currentRoleCode": "STUDENT", "clientType": "MP"})}


def _seed(db_mode):
    from uuid import uuid4
    from app.db.session import get_sessionmaker
    from app.models import FileObject, InternshipBatch, InternshipRecord, StudentProfile
    db = get_sessionmaker()()
    ids = {}
    try:
        batch = InternshipBatch(
            tenant_id=TID, batch_name="成绩测试批次",
            batch_no=f"SCORE-{uuid4().hex[:8]}", status="RUNNING", planned_count=2)
        db.add(batch); db.flush(); ids["batch"] = batch.id
        evidence = FileObject(
            tenant_id=TID, file_key=f"score/{uuid4().hex}.pdf", file_name="企业评价扫描件.pdf",
            ext="pdf", size_bytes=1024, biz_type="INTERNSHIP", biz_id="ENT_EVAL_TEST",
            visibility="BIZ_SCOPED", status="STORED")
        db.add(evidence); db.flush(); ids["file"] = str(evidence.id)
        for number, name, advisor, key in [
            ("SC-A", "甲", "刘强", "a"), ("SC-B", "乙", "王芳", "b")
        ]:
            student = StudentProfile(
                tenant_id=TID, student_no=number, real_name=name,
                current_stage="INTERNSHIP", student_status="NORMAL", status="ACTIVE")
            db.add(student); db.flush()
            record = InternshipRecord(
                tenant_id=TID, student_id=student.id, advisor_name=advisor,
                enterprise_name="测试企业", position_name="实习生", status="ONBOARD",
                risk_level="NONE", batch_id=batch.id)
            db.add(record); db.flush(); ids[f"rec_{key}"] = record.id
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


def _approve_enterprise_eval(client, record_id, evidence_file_id, mentor_name="刘强",
                             component_score=60):
    created = client.post(
        f"{INT}/enterprise-evals",
        json={
            "internshipId": str(record_id), "mentorName": "企业导师",
            "attendanceScore": component_score, "skillScore": component_score,
            "attitudeScore": component_score, "collaborationScore": component_score,
            "safetyScore": component_score, "sourceFileId": evidence_file_id,
        },
        headers=_mentor(mentor_name),
    )
    assert created.status_code == 200
    data = created.json()["data"]
    reviewed = client.post(
        f"{INT}/enterprise-evals/{data['id']}/review-versioned",
        json={"action": "APPROVE", "expectedVersion": data["version"]},
        headers=_admin(client),
    )
    assert reviewed.status_code == 200
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
    denied = client.post(
        f"{INT}/scores/config",
        json={"checkinWeight": 20, "weeklyWeight": 20, "monthlyWeight": 10,
              "enterpriseWeight": 30, "schoolWeight": 20},
        headers=_mentor("刘强"))
    assert denied.status_code == 403

    _approve_enterprise_eval(client, ids["rec_a"], ids["file"], component_score=80)
    computed = _compute(client, ids, scores={
        "checkinScore": 80, "weeklyScore": 80, "monthlyScore": 80, "schoolScore": 80})
    assert computed.status_code == 200
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
    _approve_enterprise_eval(client, ids["rec_a"], ids["file"], component_score=60)
    computed = _compute(client, ids)
    assert computed.status_code == 200
    score = computed.json()["data"]
    assert score["total"] == 79.0 and score["incomplete"] is False and score["isPass"] is True

    mentor_publish = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]}, headers=_mentor("刘强"))
    assert mentor_publish.status_code == 403

    published = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]}, headers=_admin(client))
    assert published.status_code == 200
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
    _approve_enterprise_eval(client, ids["rec_a"], ids["file"], component_score=84)

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
    assert computed.status_code == 200
    detail = client.get(
        f"{INT}/scores/{computed.json()['data']['id']}", headers=_mentor("刘强")).json()["data"]
    assert detail["enterpriseScore"] == 84
    assert detail["enterpriseSource"]["type"] == "APPROVED_ENTERPRISE_EVAL"


def test_incomplete_cannot_publish(client, db_mode):
    ids = _seed(db_mode)
    _config(client)
    computed = _compute(client, ids, scores={
        "checkinScore": 90, "weeklyScore": 80, "schoolScore": 100})
    assert computed.status_code == 200
    score = computed.json()["data"]
    assert score["incomplete"] is True
    denied = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]}, headers=_admin(client))
    assert denied.status_code == 409


def test_scope_student_forbidden_withdraw_and_export(client, db_mode):
    ids = _seed(db_mode)
    _config(client)
    _approve_enterprise_eval(client, ids["rec_a"], ids["file"], mentor_name="刘强", component_score=80)
    _approve_enterprise_eval(client, ids["rec_b"], ids["file"], mentor_name="王芳", component_score=80)
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
