"""实习成绩：事实建议分、人工调整证据、权重快照、发布与归档冻结。"""
from __future__ import annotations

import io
from datetime import date, datetime

TID = 1000000000000000001
INT = "/api/v1/internship"


def _admin(client):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _school_admin(user_id="alternate-school-admin", name="复核管理员", tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": user_id,
        "realName": name,
        "userType": "TEACHER",
        "tid": "x",
        "tenantId": str(tid),
        "activeContextId": "ctx",
        "currentRoleCode": "SCHOOL_ADMIN",
        "clientType": "PC",
    })}


def _mentor(name, tid=TID):
    from app.core.security import create_access_token
    user_id = {"刘强": "9001", "王芳": "9002"}.get(name, "9099")
    return {"Authorization": "Bearer " + create_access_token({
        "userId": user_id,
        "realName": name,
        "userType": "TEACHER",
        "tid": "x",
        "tenantId": str(tid),
        "activeContextId": "ctx",
        "currentRoleCode": "INTERN_MENTOR",
        "clientType": "PC",
    })}


def _student(student_no, tid=TID):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{student_no}",
        "realName": "学生",
        "userType": "STUDENT",
        "tid": "x",
        "tenantId": str(tid),
        "studentNo": student_no,
        "currentRoleCode": "STUDENT",
        "clientType": "MP",
    })}


def _seed(db_mode):
    """两名学生均具备正式 ASSESS 过程事实；企业评价仍通过真实 API 生成。"""
    from uuid import uuid4

    from app.db.session import get_sessionmaker
    from app.models import (
        EmpCompany,
        InternshipAgreement,
        InternshipBatch,
        InternshipCheckin,
        InternshipGuidance,
        InternshipInsurance,
        InternshipPosition,
        InternshipProcessReport,
        InternshipRecord,
        InternshipStudentEval,
        InternshipVisit,
        StudentProfile,
        WeeklyReport,
    )

    db = get_sessionmaker()()
    ids = {}
    try:
        today = date.today()
        batch = InternshipBatch(
            tenant_id=TID,
            batch_name="成绩测试批次",
            batch_no=f"SCORE-{uuid4().hex[:8]}",
            status="RUNNING",
            planned_count=2,
            start_date=today,
            end_date=today,
            rules_config={
                "checkin": {"expectedDays": 1},
                "weeklyReport": {"expectedCount": 1},
                "monthlyReport": {"expectedCount": 1},
                "guidance": {"expectedCount": 1},
                "visit": {"expectedCount": 1},
                "compliance": {
                    "studentConsent": {
                        "requireGuardianConsentForMinor": False,
                    },
                },
            },
        )
        db.add(batch)
        db.flush()
        ids["batch"] = batch.id
        company = EmpCompany(
            tenant_id=TID,
            name="成绩测试企业",
            credit_code=f"91310000SC{uuid4().hex[:6].upper()}",
            coop_status="ACTIVE",
        )
        db.add(company)
        db.flush()
        position = InternshipPosition(
            tenant_id=TID,
            company_id=company.id,
            company_name=company.name,
            title="实习生",
            batch_id=batch.id,
            status="PUBLISHED",
            headcount=5,
        )
        db.add(position)
        db.flush()

        for number, name, advisor, key in [
            ("SC-A", "甲", "刘强", "a"),
            ("SC-B", "乙", "王芳", "b"),
        ]:
            student = StudentProfile(
                tenant_id=TID,
                student_no=number,
                real_name=name,
                current_stage="INTERNSHIP",
                student_status="NORMAL",
                status="ACTIVE",
            )
            db.add(student)
            db.flush()
            record = InternshipRecord(
                tenant_id=TID,
                student_id=student.id,
                advisor_name=advisor,
                enterprise_name=company.name,
                position_name=position.title,
                enterprise_id=company.id,
                position_id=position.id,
                eligibility_status="QUALIFIED",
                status="ASSESSING",
                risk_level="NONE",
                batch_id=batch.id,
                intern_start_date=today,
                intern_end_date=today,
            )
            db.add(record)
            db.flush()
            ids[f"rec_{key}"] = record.id
            ids[f"rec_ver_{key}"] = int(record.version or 0)
            ids[f"stu_{key}"] = student.id
            db.add_all([
                InternshipInsurance(
                    tenant_id=TID,
                    internship_id=record.id,
                    student_id=student.id,
                    status="VERIFIED",
                ),
                InternshipAgreement(
                    tenant_id=TID,
                    internship_id=record.id,
                    student_id=student.id,
                    status="EFFECTIVE",
                ),
                InternshipCheckin(
                    tenant_id=TID,
                    internship_id=record.id,
                    checkin_date=today.isoformat(),
                    checkin_at=datetime.utcnow(),
                    result="NORMAL",
                ),
                WeeklyReport(
                    tenant_id=TID,
                    internship_id=record.id,
                    week_number=1,
                    word_count=800,
                    report_version=1,
                    submitted_at=datetime.utcnow(),
                    status="APPROVED",
                ),
                InternshipProcessReport(
                    tenant_id=TID,
                    internship_id=record.id,
                    report_type="MONTHLY",
                    period_key=today.strftime("%Y-%m"),
                    content="完整月报",
                    word_count=800,
                    submitted_at=datetime.utcnow(),
                    status="APPROVED",
                ),
                InternshipGuidance(
                    tenant_id=TID,
                    internship_id=record.id,
                    student_id=student.id,
                    advisor_name=advisor,
                    method="ONSITE",
                    content="完整指导记录",
                    status="NORMAL",
                ),
                InternshipVisit(
                    tenant_id=TID,
                    internship_id=record.id,
                    student_id=student.id,
                    advisor_name=advisor,
                    enterprise_name=company.name,
                    visit_at=datetime.utcnow(),
                    method="ONSITE",
                    rectify_status="NONE",
                ),
                InternshipStudentEval(
                    tenant_id=TID,
                    internship_id=record.id,
                    student_id=student.id,
                    self_summary="完整自评",
                    submit_status="SUBMITTED",
                ),
            ])
        db.commit()
        return ids
    finally:
        db.close()


def _config(client, **overrides):
    body = {
        "checkinWeight": 20,
        "weeklyWeight": 20,
        "monthlyWeight": 10,
        "enterpriseWeight": 30,
        "schoolWeight": 20,
        "passLine": 60,
        **overrides,
    }
    return client.post(f"{INT}/scores/config", json=body, headers=_admin(client))


def _upload(client, headers, name, content, biz_type):
    uploaded = client.post(
        "/api/v1/files",
        headers=headers,
        files={"file": (name, io.BytesIO(content), "text/plain")},
        data={"bizType": biz_type},
    )
    assert uploaded.status_code == 200, uploaded.text
    data = uploaded.json()["data"]
    assert data["temporary"] is True and data["bindingCreated"] is False
    return data["fileId"]


def _upload_enterprise_evidence(client, headers) -> str:
    return _upload(
        client,
        headers,
        "enterprise-eval.txt",
        b"authoritative-enterprise-evaluation-evidence",
        "INTERNSHIP_ENTERPRISE_EVAL",
    )


def _upload_adjustment_evidence(client, headers) -> str:
    return _upload(
        client,
        headers,
        "score-adjustment.txt",
        b"formal-score-adjustment-evidence",
        "INTERNSHIP_SCORE_ADJUSTMENT",
    )


def _approve_enterprise_eval(
    client, record_id, mentor_name="刘强", component_score=60,
):
    mentor_headers = _mentor(mentor_name)
    evidence_file_id = _upload_enterprise_evidence(client, mentor_headers)
    created = client.post(
        f"{INT}/enterprise-evals",
        json={
            "internshipId": str(record_id),
            "mentorName": "企业导师",
            "attendanceScore": component_score,
            "skillScore": component_score,
            "attitudeScore": component_score,
            "collaborationScore": component_score,
            "safetyScore": component_score,
            "sourceFileId": evidence_file_id,
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


def _compute(
    client, ids, key="a", mentor="刘强", body=None, headers=None,
):
    payload = {"internshipId": str(ids[f"rec_{key}"])}
    payload.update(body or {})
    return client.post(
        f"{INT}/scores/compute",
        json=payload,
        headers=headers or _mentor(mentor),
    )


def test_config_weight_sum_and_snapshot(client, db_mode):
    ids = _seed(db_mode)
    bad = _config(client, schoolWeight=30)
    assert bad.status_code == 400
    first = _config(client).json()["data"]
    assert first["configId"]

    current = client.get(
        f"{INT}/scores/config", headers=_admin(client),
    ).json()["data"]
    assert current["enterpriseWeight"] == 30
    assert current["passLine"] == 60
    assert current["configId"] == first["configId"]

    denied = client.post(
        f"{INT}/scores/config",
        json={
            "checkinWeight": 20,
            "weeklyWeight": 20,
            "monthlyWeight": 10,
            "enterpriseWeight": 30,
            "schoolWeight": 20,
        },
        headers=_mentor("刘强"),
    )
    assert denied.status_code == 403

    _approve_enterprise_eval(client, ids["rec_a"], component_score=80)
    computed = _compute(client, ids)
    assert computed.status_code == 200, computed.json()
    detail = client.get(
        f"{INT}/scores/{computed.json()['data']['id']}",
        headers=_mentor("刘强"),
    ).json()["data"]
    assert detail["scoreConfigId"] == first["configId"]
    assert detail["scoreConfigVersion"] >= 1
    assert len(detail["sourceHash"]) == 64
    assert detail["suggestedScores"] == {
        "checkin": 100,
        "weekly": 100,
        "monthly": 100,
        "enterprise": 80,
        "school": 100,
    }
    assert detail["sourceManifest"]["facts"]["weekly"]["rows"]

    second = _config(
        client,
        checkinWeight=10,
        weeklyWeight=10,
        enterpriseWeight=40,
        schoolWeight=30,
    ).json()["data"]
    assert second["configId"] != first["configId"]


def test_compute_and_school_publish_with_versions(client, db_mode):
    ids = _seed(db_mode)
    _config(client)
    _approve_enterprise_eval(client, ids["rec_a"], component_score=60)
    computed = _compute(client, ids)
    assert computed.status_code == 200, computed.json()
    score = computed.json()["data"]
    assert score["total"] == 88.0
    assert score["incomplete"] is False
    assert score["isPass"] is True
    assert score["adjustmentReviewStatus"] == "NOT_REQUIRED"

    mentor_publish = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]},
        headers=_mentor("刘强"),
    )
    assert mentor_publish.status_code == 403

    published = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]},
        headers=_admin(client),
    )
    assert published.status_code == 200, published.json()
    published_data = published.json()["data"]
    assert published_data["status"] == "PUBLISHED"
    assert published_data["sourceHash"] == score["sourceHash"]

    detail = client.get(
        f"{INT}/scores/{score['id']}", headers=_mentor("刘强"),
    ).json()["data"]
    assert {"COMPUTE_FACT_SNAPSHOT", "COMPUTE", "PUBLISH"} <= {
        item["action"] for item in detail["auditTrail"]
    }
    stale = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]},
        headers=_admin(client),
    )
    assert stale.status_code == 409


def test_enterprise_score_is_authoritative_and_manual_override_rejected(
    client, db_mode,
):
    ids = _seed(db_mode)
    _config(client)
    _approve_enterprise_eval(client, ids["rec_a"], component_score=84)

    manual = _compute(client, ids, body={
        "checkinScore": 100,
        "weeklyScore": 100,
        "monthlyScore": 100,
        "enterpriseScore": 1,
        "schoolScore": 100,
    })
    assert manual.status_code == 400
    assert "不得直接提交" in manual.json()["message"]

    computed = _compute(client, ids)
    assert computed.status_code == 200, computed.json()
    detail = client.get(
        f"{INT}/scores/{computed.json()['data']['id']}",
        headers=_mentor("刘强"),
    ).json()["data"]
    assert detail["enterpriseScore"] == 84
    assert detail["suggestedScores"]["enterprise"] == 84
    assert detail["enterpriseSource"]["type"] == "APPROVED_ENTERPRISE_EVAL"


def test_incomplete_cannot_publish(client, db_mode):
    ids = _seed(db_mode)
    _config(client)
    computed = _compute(client, ids)
    assert computed.status_code == 200, computed.json()
    score = computed.json()["data"]
    assert score["incomplete"] is True
    assert "企业评价" in score["incompleteReason"]
    denied = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]},
        headers=_admin(client),
    )
    assert denied.status_code == 409


def test_scope_student_forbidden_withdraw_and_export(client, db_mode):
    ids = _seed(db_mode)
    _config(client)
    _approve_enterprise_eval(
        client, ids["rec_a"], mentor_name="刘强", component_score=80,
    )
    _approve_enterprise_eval(
        client, ids["rec_b"], mentor_name="王芳", component_score=80,
    )
    score_a = _compute(client, ids, key="a", mentor="刘强").json()["data"]
    score_b = _compute(client, ids, key="b", mentor="王芳").json()["data"]

    assert client.get(
        f"{INT}/scores/{score_b['id']}", headers=_mentor("刘强"),
    ).status_code == 403
    params = {"batchId": ids["batch"]}
    assert client.get(
        f"{INT}/scores", params=params, headers=_admin(client),
    ).json()["data"]["total"] == 2
    assert client.get(
        f"{INT}/scores", params=params, headers=_mentor("刘强"),
    ).json()["data"]["total"] == 1
    assert client.get(
        f"{INT}/scores", params=params, headers=_student("SC-A"),
    ).status_code == 403
    assert client.post(
        f"{INT}/scores/compute",
        json={"internshipId": str(ids["rec_a"])},
        headers=_student("SC-A"),
    ).status_code == 403

    published = client.post(
        f"{INT}/scores/{score_a['id']}/publish",
        json={"expectedVersion": score_a["version"]},
        headers=_admin(client),
    ).json()["data"]
    too_short = client.post(
        f"{INT}/scores/{score_a['id']}/withdraw",
        json={"reason": "x", "expectedVersion": published["version"]},
        headers=_admin(client),
    )
    assert too_short.status_code == 400
    withdrawn = client.post(
        f"{INT}/scores/{score_a['id']}/withdraw",
        json={
            "reason": "成绩录入有误需要重新核算",
            "expectedVersion": published["version"],
        },
        headers=_admin(client),
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["data"]["status"] == "WITHDRAWN"

    exported = client.post(
        f"{INT}/scores/export", params=params, headers=_admin(client),
    )
    assert exported.status_code == 200
    data = exported.json()["data"]
    assert data["filename"].endswith(".xlsx")
    assert data["rowCount"] == 2


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
    computed = _compute(client, ids)
    assert computed.status_code == 200, computed.json()
    score = computed.json()["data"]

    from app.db.session import get_sessionmaker
    from app.models import InternshipInsurance

    db = get_sessionmaker()()
    try:
        insurance = db.query(InternshipInsurance).filter_by(
            tenant_id=TID,
            internship_id=ids["rec_a"],
        ).one()
        insurance.status = "PENDING"
        db.commit()
    finally:
        db.close()
    denied = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]},
        headers=_admin(client),
    )
    assert denied.status_code == 409
    assert denied.json()["details"]["blockers"]


def test_independent_score_archive_is_disabled(client, db_mode):
    ids = _seed(db_mode)
    _approve_enterprise_eval(client, ids["rec_a"], component_score=80)
    computed = _compute(client, ids).json()["data"]
    published = client.post(
        f"{INT}/scores/{computed['id']}/publish",
        json={"expectedVersion": computed["version"]},
        headers=_admin(client),
    )
    assert published.status_code == 200, published.json()
    denied = client.post(
        f"{INT}/scores/{computed['id']}/archive",
        json={"expectedVersion": published.json()["data"]["version"]},
        headers=_admin(client),
    )
    assert denied.status_code == 409
    assert "总档案归档" in denied.json()["message"]


def test_manual_adjustment_requires_evidence_and_independent_reviewer(
    client, db_mode,
):
    ids = _seed(db_mode)
    _approve_enterprise_eval(client, ids["rec_a"], component_score=80)
    adjuster = _admin(client)

    missing = _compute(
        client,
        ids,
        headers=adjuster,
        body={
            "manualAdjustments": {"weekly": -10},
            "adjustmentReason": "周报质量复核后人工扣分",
        },
    )
    assert missing.status_code == 400
    assert "依据文件" in missing.json()["message"]

    evidence = _upload_adjustment_evidence(client, adjuster)
    computed = _compute(
        client,
        ids,
        headers=adjuster,
        body={
            "manualAdjustments": {"weekly": -10},
            "adjustmentReason": "周报质量复核后人工扣分",
            "adjustmentEvidenceFileIds": [evidence],
        },
    )
    assert computed.status_code == 200, computed.json()
    score = computed.json()["data"]
    assert score["suggestedScores"]["weekly"] == 100
    assert score["manualAdjustments"]["weekly"] == -10
    assert score["total"] == 92.0
    assert score["adjustmentReviewStatus"] == "PENDING"

    same_user = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]},
        headers=adjuster,
    )
    assert same_user.status_code == 409
    assert "不同用户复核" in same_user.json()["message"]

    reviewed = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]},
        headers=_school_admin(),
    )
    assert reviewed.status_code == 200, reviewed.json()
    assert reviewed.json()["data"]["adjustmentReviewStatus"] == "APPROVED"

    detail = client.get(
        f"{INT}/scores/{score['id']}", headers=_admin(client),
    ).json()["data"]
    assert detail["adjustmentReviewStatus"] == "APPROVED"
    assert detail["adjustedByUserId"] != detail["reviewedByUserId"]
    evidence_rows = detail["sourceManifest"]["manualAdjustmentEvidence"]
    assert evidence_rows[0]["fileId"] == evidence
    assert evidence_rows[0]["bindingStatus"] == "ACTIVE"


def test_source_change_requires_recompute_before_publish(client, db_mode):
    ids = _seed(db_mode)
    _approve_enterprise_eval(client, ids["rec_a"], component_score=80)
    computed = _compute(client, ids)
    assert computed.status_code == 200, computed.json()
    score = computed.json()["data"]

    from app.db.session import get_sessionmaker
    from app.models import WeeklyReport

    db = get_sessionmaker()()
    try:
        db.add(WeeklyReport(
            tenant_id=TID,
            internship_id=ids["rec_a"],
            week_number=2,
            word_count=900,
            report_version=1,
            submitted_at=datetime.utcnow(),
            status="APPROVED",
        ))
        db.commit()
    finally:
        db.close()

    stale = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]},
        headers=_admin(client),
    )
    assert stale.status_code == 409
    assert "来源事实已变化" in stale.json()["message"]

    recomputed = _compute(
        client,
        ids,
        body={"expectedVersion": score["version"]},
    )
    assert recomputed.status_code == 200, recomputed.json()
    refreshed = recomputed.json()["data"]
    assert refreshed["factSourceHash"] != score["factSourceHash"]
    published = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": refreshed["version"]},
        headers=_admin(client),
    )
    assert published.status_code == 200, published.json()


def test_total_archive_freezes_fact_snapshot_and_source_hash(client, db_mode):
    ids = _seed(db_mode)
    _approve_enterprise_eval(client, ids["rec_a"], component_score=80)
    computed = _compute(client, ids)
    assert computed.status_code == 200, computed.json()
    score = computed.json()["data"]
    published = client.post(
        f"{INT}/scores/{score['id']}/publish",
        json={"expectedVersion": score["version"]},
        headers=_admin(client),
    )
    assert published.status_code == 200, published.json()

    archived = client.post(
        f"{INT}/archive/{ids['rec_a']}/archive",
        json={"expectedVersion": ids["rec_ver_a"]},
        headers=_admin(client),
    )
    assert archived.status_code == 200, archived.json()

    from app.db.session import get_sessionmaker
    from app.models import InternshipArchive

    db = get_sessionmaker()()
    try:
        row = db.query(InternshipArchive).filter_by(
            tenant_id=TID,
            internship_id=ids["rec_a"],
        ).one()
        freeze = row.material_snapshot["finalScoreFreeze"]
        assert freeze["sourceSnapshotStatus"] == "FROZEN"
        assert freeze["sourceHash"] == score["sourceHash"]
        assert freeze["suggestedScores"]["checkin"] == 100
        assert freeze["sourceManifest"]["facts"]["enterprise"]["evaluationId"]
        assert row.material_snapshot["finalScoreFreezeHash"] == archived.json()["data"][
            "finalScoreFreezeHash"
        ]
    finally:
        db.close()
