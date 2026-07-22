"""毕业设计中心 · 全角色验收缺陷回归（本次 E2E 发现并修复的门禁）。

覆盖：
1. 资格不合格/未认定学生不可确认选题
2. 成绩权重≠100% 拒绝保存
3. 阶段时间倒序拒绝保存
4. 未关闭风险阻止归档提交
"""
from __future__ import annotations

from datetime import datetime

GD_BATCH = "/api/v1/graduation/batches"
GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
GD_ARCHIVE = "/api/v1/graduation/gd-archives"
GD_RISK = "/api/v1/graduation/gd-risks"
STU = "/api/v1/students"


def _gd_student(client, h, no, name):
    sid = client.post(STU, headers=h, json={"studentNo": no, "realName": name}).json()["data"]["id"]
    return client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]


def _approved_topic(client, h, title, capacity=1):
    r = client.post(GD_TOPIC, headers=h, json={
        "title": title, "sourceType": "TEACHER", "advisorName": "E2E导师",
        "capacity": capacity, "submitReview": True,
    }).json()
    tid = r["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    return tid


def test_unqualified_student_cannot_be_assigned_topic(client, auth_headers, db_mode):
    h = auth_headers
    gid = _gd_student(client, h, "E2E-ELIG-01", "资格拦截生")
    tid = _approved_topic(client, h, "资格拦截题")
    # PENDING 可由学院管理员分配（运营补录）；UNQUALIFIED 必须拦截
    client.post(f"{GD_STU}/{gid}/eligibility", headers=h, json={
        "status": "UNQUALIFIED", "reason": "学分未达毕业设计准入要求",
    })
    blocked = client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    assert blocked.json()["code"] != 0
    client.post(f"{GD_STU}/{gid}/eligibility", headers=h, json={
        "status": "QUALIFIED", "reason": "补修完成，予以认定",
    })
    ok = client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    assert ok.json()["code"] == 0
    assert ok.json()["data"]["topicId"] == tid


def test_batch_rules_reject_non_100_percent_weights(client, auth_headers, db_mode):
    h = auth_headers
    bid = client.post(GD_BATCH, headers=h, json={
        "batchName": "E2E权重校验批", "batchNo": "E2E-W-1", "gradeYear": "2026届", "plannedCount": 10,
    }).json()["data"]["id"]
    bad = client.post(f"{GD_BATCH}/{bid}/rules", headers=h, json={
        "rules": {"score": {"advisorWeight": 0.5, "reviewerWeight": 0.3, "defenseWeight": 0.3}},
    }).json()
    assert bad["code"] != 0
    assert "100%" in (bad.get("message") or "")
    ok = client.post(f"{GD_BATCH}/{bid}/rules", headers=h, json={
        "rules": {"score": {"advisorWeight": 0.4, "reviewerWeight": 0.3, "defenseWeight": 0.3},
                  "plagiarism": {"thresholdPercent": 25}},
    }).json()
    assert ok["code"] == 0
    assert ok["data"]["rules"]["plagiarism"]["thresholdPercent"] == 25


def test_batch_stages_reject_reversed_dates(client, auth_headers, db_mode):
    h = auth_headers
    bid = client.post(GD_BATCH, headers=h, json={
        "batchName": "E2E阶段校验批", "batchNo": "E2E-S-1", "gradeYear": "2026届", "plannedCount": 10,
    }).json()["data"]["id"]
    bad = client.post(f"{GD_BATCH}/{bid}/stages", headers=h, json={"stages": [
        {"code": "TOPIC", "name": "选题", "startDate": "2025-10-01", "endDate": "2025-10-31"},
        {"code": "PROPOSAL", "name": "开题", "startDate": "2025-09-01", "endDate": "2025-09-30"},
    ]}).json()
    assert bad["code"] != 0
    ok = client.post(f"{GD_BATCH}/{bid}/stages", headers=h, json={"stages": [
        {"code": "TOPIC", "name": "选题", "startDate": "2025-09-01", "endDate": "2025-09-30"},
        {"code": "PROPOSAL", "name": "开题", "startDate": "2025-10-01", "endDate": "2025-10-31"},
    ]}).json()
    assert ok["code"] == 0


def test_open_risk_blocks_archive_submit(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import (GraduationDefenseScore, GraduationFinal, GraduationGrade,
                            GraduationMidterm, GraduationProposal, GraduationReview,
                            GraduationRiskCase, GraduationTaskBook)

    h = auth_headers
    gid = _gd_student(client, h, "E2E-RISK-ARCH-01", "风险归档生")
    db = get_sessionmaker()()
    final = GraduationFinal(
        tenant_id=1000000000000000001, gd_student_id=int(gid), final_type="定稿",
        version="v1", submit_at=datetime.utcnow(), plagiarism_rate="8.0%",
        plagiarism_status="已检测", status="APPROVED", attachments_json=["test-file"],
    )
    db.add(final)
    db.flush()
    db.add_all([
        GraduationTaskBook(tenant_id=1000000000000000001, gd_student_id=int(gid), status="CONFIRMED"),
        GraduationProposal(tenant_id=1000000000000000001, gd_student_id=int(gid), version="v1", status="APPROVED"),
        GraduationMidterm(tenant_id=1000000000000000001, gd_student_id=int(gid), status="CHECKED_PASS"),
        GraduationReview(tenant_id=1000000000000000001, gd_student_id=int(gid), gd_final_id=final.id,
                         reviewer_name="李评阅", status="COMPLETED", score=88),
        GraduationDefenseScore(tenant_id=1000000000000000001, gd_student_id=int(gid),
                               judge_name="王评委", score=90, status="CONFIRMED"),
        GraduationGrade(tenant_id=1000000000000000001, gd_student_id=int(gid),
                        total_score=89, grade_level="良好", status="PUBLISHED"),
        GraduationRiskCase(tenant_id=1000000000000000001, risk_code="GD-R01", risk_name="未选题",
                           gd_student_id=int(gid), level="HIGH", status="OPEN",
                           detected_at=datetime.utcnow()),
    ])
    db.commit()
    db.close()

    gen = client.post(f"{GD_ARCHIVE}/{gid}/generate", headers=h).json()["data"]
    assert gen["missingItems"] == []
    blocked = client.post(f"{GD_ARCHIVE}/{gid}/submit", headers=h).json()
    assert blocked["code"] != 0
    assert "未关闭风险" in (blocked.get("message") or "")

    # close risk then submit OK
    risks = client.get(GD_RISK, headers=h, params={"gdStudentId": gid}).json()["data"]["items"]
    rid = risks[0]["id"]
    client.post(f"{GD_RISK}/{rid}/accept", headers=h, json={})
    client.post(f"{GD_RISK}/{rid}/close", headers=h, json={"reason": "E2E风险已处理关闭"})
    ok = client.post(f"{GD_ARCHIVE}/{gid}/submit", headers=h).json()
    assert ok["code"] == 0
    assert ok["data"]["status"] == "SUBMITTED"
