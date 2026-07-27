"""毕业设计中心 · 全角色验收缺陷回归（本次 E2E 发现并修复的门禁）。

覆盖：
1. 资格不合格/未认定学生不可确认选题
2. 成绩权重≠100% 拒绝保存
3. 阶段时间倒序拒绝保存
4. 未关闭风险阻止归档提交
5. 评阅 SoD 须同时核对题目指导教师（不依赖空白 advisor_name）
6. 中期整改中不可提交成果
7. 中期整改复核通过（RECTIFIED_PASS）可提交成果
8. 批量归档生成/核验同样受未关闭风险门禁约束
9. 创建批次时即校验阶段顺序与成绩权重
"""
from __future__ import annotations


def _upload_pdf(client, headers, name="thesis.pdf"):
    files = {"file": (name, b"%PDF-1.4 test", "application/pdf")}
    r = client.post("/api/v1/files/upload", headers=headers, files=files,
                    params={"bizType": "GRADUATION_MATERIAL"})
    assert r.json()["code"] == 0, r.json()
    return r.json()["data"]["fileId"]


from datetime import datetime

from sqlalchemy import select

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


def _seed_archive_ready(db, gid: int, *, with_open_risk: bool = False):
    from app.models import (GraduationDefenseScore, GraduationFinal, GraduationGrade,
                            GraduationMidterm, GraduationProposal, GraduationReview,
                            GraduationRiskCase, GraduationTaskBook)

    final = GraduationFinal(
        tenant_id=1000000000000000001, gd_student_id=int(gid), final_type="定稿",
        version="v1", submit_at=datetime.utcnow(), plagiarism_rate="8.0%",
        plagiarism_status="已检测", status="APPROVED", attachments_json=["test-file"],
    )
    db.add(final)
    db.flush()
    rows = [
        GraduationTaskBook(tenant_id=1000000000000000001, gd_student_id=int(gid), status="CONFIRMED"),
        GraduationProposal(tenant_id=1000000000000000001, gd_student_id=int(gid), version="v1", status="APPROVED"),
        GraduationMidterm(tenant_id=1000000000000000001, gd_student_id=int(gid), status="CHECKED_PASS"),
        GraduationReview(tenant_id=1000000000000000001, gd_student_id=int(gid), gd_final_id=final.id,
                         reviewer_name="李评阅", status="COMPLETED", score=88),
        GraduationDefenseScore(tenant_id=1000000000000000001, gd_student_id=int(gid),
                               judge_name="王评委", score=90, status="CONFIRMED"),
        GraduationGrade(tenant_id=1000000000000000001, gd_student_id=int(gid),
                        total_score=89, grade_level="良好", status="PUBLISHED"),
    ]
    if with_open_risk:
        rows.append(GraduationRiskCase(
            tenant_id=1000000000000000001, risk_code="GD-R01", risk_name="未选题",
            gd_student_id=int(gid), level="HIGH", status="OPEN",
            detected_at=datetime.utcnow(),
        ))
    db.add_all(rows)


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


def test_create_batch_rejects_invalid_stages_and_weights(client, auth_headers, db_mode):
    h = auth_headers
    bad_stages = client.post(GD_BATCH, headers=h, json={
        "batchName": "创建阶段非法批", "batchNo": "E2E-CREATE-S1", "gradeYear": "2026届",
        "stages": [
            {"code": "TOPIC", "name": "选题", "startDate": "2025-10-01", "endDate": "2025-10-31"},
            {"code": "PROPOSAL", "name": "开题", "startDate": "2025-09-01", "endDate": "2025-09-30"},
        ],
    }).json()
    assert bad_stages["code"] != 0
    bad_weights = client.post(GD_BATCH, headers=h, json={
        "batchName": "创建权重非法批", "batchNo": "E2E-CREATE-W1", "gradeYear": "2026届",
        "rules": {"score": {"advisorWeight": 0.5, "reviewerWeight": 0.3, "defenseWeight": 0.3}},
    }).json()
    assert bad_weights["code"] != 0
    assert "100%" in (bad_weights.get("message") or "")


def test_open_risk_blocks_archive_submit(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker

    h = auth_headers
    gid = _gd_student(client, h, "E2E-RISK-ARCH-01", "风险归档生")
    db = get_sessionmaker()()
    _seed_archive_ready(db, int(gid), with_open_risk=True)
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


def test_open_risk_skips_batch_archive_generate_and_file(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationArchiveRecord, GraduationStudent

    h = auth_headers
    bid = client.post(GD_BATCH, headers=h, json={
        "batchName": "E2E批量风险批", "batchNo": "E2E-RISK-BATCH-B", "gradeYear": "2026届", "plannedCount": 10,
    }).json()["data"]["id"]
    sid = client.post(STU, headers=h, json={"studentNo": "E2E-RISK-BATCH-01", "realName": "批量风险归档生"}).json()["data"]["id"]
    gid = client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": bid}).json()["data"]["id"]
    db = get_sessionmaker()()
    _seed_archive_ready(db, int(gid), with_open_risk=True)
    db.commit()
    db.close()

    gen = client.post(f"{GD_ARCHIVE}/batch-generate", headers=h, params={"batchId": bid}).json()
    assert gen["code"] == 0
    assert gen["data"]["skipped"] >= 1

    db = get_sessionmaker()()
    row = db.scalars(select(GraduationArchiveRecord).where(
        GraduationArchiveRecord.gd_student_id == int(gid),
        GraduationArchiveRecord.is_deleted.is_(False),
    )).first()
    assert row is not None
    assert row.status != "SUBMITTED"
    assert row.status != "FILED"
    # 强造 SUBMITTED，验证 batch-file 也会因未关闭风险跳过
    row.status = "SUBMITTED"
    row.missing_items = []
    db.commit()
    db.close()

    filed = client.post(f"{GD_ARCHIVE}/batch-file", headers=h, params={"batchId": bid}, json={}).json()
    assert filed["code"] == 0
    assert filed["data"]["skipped"] >= 1

    db = get_sessionmaker()()
    row = db.scalars(select(GraduationArchiveRecord).where(
        GraduationArchiveRecord.gd_student_id == int(gid),
        GraduationArchiveRecord.is_deleted.is_(False),
    )).first()
    assert row is not None
    assert row.status == "SUBMITTED"
    db.close()


def test_assign_review_sod_uses_topic_advisor_when_student_advisor_blank(client, auth_headers, db_mode):
    """SoD 不得仅依赖 student.advisor_name；题目指导教师也必须回避。"""
    h = auth_headers
    gid = _gd_student(client, h, "SOD-ADV-01", "SoD回避生")
    tid = client.post(GD_TOPIC, headers=h, json={
        "title": "SoD回避题-专名", "sourceType": "TEACHER", "advisorName": "张回避导师",
        "capacity": 1, "submitReview": True,
    }).json()["data"]["id"]
    client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    client.post(f"{GD_STU}/{gid}/eligibility", headers=h, json={
        "status": "QUALIFIED", "reason": "SoD测试资格合格",
    })
    client.post(f"{GD_STU}/{gid}/assign-topic", headers=h, json={"topicId": tid})
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent
    db = get_sessionmaker()()
    stu = db.get(GraduationStudent, int(gid))
    stu.advisor_name = None
    db.commit()
    db.close()
    conflict = client.post("/api/v1/graduation/gd-reviews/assign", headers=h, json={
        "gdStudentId": gid, "reviewerName": "张回避导师",
    }).json()
    assert conflict["code"] != 0
    assert "SoD" in (conflict.get("message") or "") or "指导教师" in (conflict.get("message") or "")
    ok = client.post("/api/v1/graduation/gd-reviews/assign", headers=h, json={
        "gdStudentId": gid, "reviewerName": "独立评阅人李",
    }).json()
    assert ok["code"] == 0


def test_final_blocked_while_midterm_rectifying(client, auth_headers, db_mode):
    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker
    from app.models import GraduationMidterm

    h = auth_headers
    name = "中期整改生"
    gid = _gd_student(client, h, "MT-FIN-01", name)
    db = get_sessionmaker()()
    db.add(GraduationMidterm(
        tenant_id=1000000000000000001, gd_student_id=int(gid),
        status="RECTIFYING", conclusion="RECTIFY",
        check_comment="测试覆盖不足", checked_at=datetime.utcnow(),
    ))
    db.commit()
    db.close()
    sh = {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "STUDENT",
        "tid": "demo", "tenantId": "1000000000000000001", "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP",
    })}
    blocked = client.post("/api/v1/mobile/graduation/final", headers=sh, json={"finalType": "初稿", "attachments": [_upload_pdf(client, sh)]}).json()
    assert blocked["code"] != 0
    assert ("中期" in (blocked.get("message") or "")) or ("阶段" in (blocked.get("message") or ""))


def test_final_allowed_after_midterm_rectified_pass(client, auth_headers, db_mode):
    """整改复核通过后 status=RECTIFIED_PASS（conclusion 应写为 PASS）须允许提交成果。"""
    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker
    from app.models import GraduationMidterm

    h = auth_headers
    name = "中期整改通过生"
    gid = _gd_student(client, h, "MT-FIN-PASS-01", name)
    db = get_sessionmaker()()
    from app.models import GraduationStudent
    stu = db.get(GraduationStudent, int(gid))
    stu.stage = "FINAL_CHECK"
    stu.topic_id = 1
    stu.topic_title = "整改通过题"
    db.add(GraduationMidterm(
        tenant_id=1000000000000000001, gd_student_id=int(gid),
        status="RECTIFIED_PASS", conclusion="PASS",
        check_comment="限期整改", rectify_content="已补材料",
        checked_at=datetime.utcnow(), reviewed_at=datetime.utcnow(),
    ))
    db.commit()
    db.close()
    sh = {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "STUDENT",
        "tid": "demo", "tenantId": "1000000000000000001", "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP",
    })}
    view = client.get("/api/v1/mobile/graduation/final", headers=sh).json()
    assert view["code"] == 0
    assert view["data"]["canSubmitDraft"] is True
    assert view["data"]["midtermPassed"] is True
    fid = _upload_pdf(client, sh)
    ok = client.post("/api/v1/mobile/graduation/final", headers=sh, json={
        "finalType": "初稿", "attachments": [fid],
    }).json()
    assert ok["code"] == 0, ok


def test_final_blocked_without_or_pending_midterm(client, auth_headers, db_mode):
    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker
    from app.models import GraduationMidterm

    h = auth_headers
    name = "无中期生"
    gid = _gd_student(client, h, "MT-FIN-NONE-01", name)
    sh = {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "STUDENT",
        "tid": "demo", "tenantId": "1000000000000000001", "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP",
    })}
    missing = client.post("/api/v1/mobile/graduation/final", headers=sh, json={"finalType": "初稿", "attachments": [_upload_pdf(client, sh)]}).json()
    assert missing["code"] != 0
    assert ("中期" in (missing.get("message") or "")) or ("阶段" in (missing.get("message") or ""))
    view = client.get("/api/v1/mobile/graduation/final", headers=sh).json()
    assert view["code"] == 0
    assert view["data"]["canSubmitDraft"] is False
    assert view["data"]["midtermPassed"] is False

    db = get_sessionmaker()()
    db.add(GraduationMidterm(
        tenant_id=1000000000000000001, gd_student_id=int(gid), status="PENDING",
    ))
    db.commit()
    db.close()
    pending = client.post("/api/v1/mobile/graduation/final", headers=sh, json={"finalType": "初稿", "attachments": [_upload_pdf(client, sh)]}).json()
    assert pending["code"] != 0
    assert ("中期" in (pending.get("message") or "")) or ("阶段" in (pending.get("message") or ""))


def test_review_rectification_sets_conclusion_pass(client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationMidterm, GraduationStudent

    h = auth_headers
    gid = _gd_student(client, h, "MT-CONCL-01", "整改结论生")
    db = get_sessionmaker()()
    db.add(GraduationMidterm(
        tenant_id=1000000000000000001, gd_student_id=int(gid),
        status="RECTIFY_SUBMITTED", conclusion="RECTIFY",
        rectify_content="已补齐实验数据", checked_at=datetime.utcnow(),
        rectify_submitted_at=datetime.utcnow(),
    ))
    db.commit()
    db.close()
    ok = client.post(f"/api/v1/graduation/gd-midterms/{gid}/rectify/review", headers=h, json={
        "action": "PASS", "comment": "整改材料齐全，予以通过",
    }).json()
    assert ok["code"] == 0, ok
    assert ok["data"]["status"] == "RECTIFIED_PASS"
    assert ok["data"]["conclusion"] == "PASS"
    assert ok["data"]["conclusionLabel"] == "通过"
    db = get_sessionmaker()()
    stu = db.get(GraduationStudent, int(gid))
    assert stu.midterm_conclusion == "通过"
    db.close()


def test_graduation_my_and_detail_use_live_midterm_and_latest_batch(client, auth_headers, db_mode):
    """摘要接口与提交门禁同一解析；学生详情中期读真实行。"""
    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker
    from app.models import GraduationMidterm, GraduationStudent

    h = auth_headers
    name = "摘要一致生"
    sno = "MT-MY-01"
    sid = client.post(STU, headers=h, json={"studentNo": sno, "realName": name}).json()["data"]["id"]
    old = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    db = get_sessionmaker()()
    old_row = db.get(GraduationStudent, int(old))
    old_row.topic_title = "旧批次题目"
    old_row.stage = "TOPIC_SELECTING"
    row = GraduationStudent(
        tenant_id=1000000000000000001, student_id=int(sid), student_no=sno, name=name,
        stage="FINAL_CHECK", topic_title="新批次题目",
    )
    db.add(row)
    db.flush()
    new = str(row.id)
    assert int(new) > int(old)
    db.add(GraduationMidterm(
        tenant_id=1000000000000000001, gd_student_id=int(new),
        status="CHECKED_PASS", conclusion="PASS",
        check_comment="进度正常", checked_at=datetime.utcnow(),
    ))
    db.commit()
    db.close()

    sh = {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "STUDENT",
        "tid": "demo", "tenantId": "1000000000000000001", "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP", "studentNo": sno,
    })}
    my = client.get("/api/v1/mobile/graduation/my", headers=sh).json()
    assert my["code"] == 0
    assert my["data"]["topicTitle"] == "新批次题目"
    assert my["data"]["stage"] == "FINAL_CHECK"

    detail = client.get(f"{GD_STU}/{new}", headers=h).json()
    assert detail["code"] == 0
    assert detail["data"]["midterm"]["conclusion"] == "通过"
    assert detail["data"]["midterm"]["status"] == "CHECKED_PASS"
    assert detail["data"]["midterm"]["statusLabel"] == "已通过"


def test_mobile_resolve_prefers_latest_non_archived_gd_student(client, auth_headers, db_mode):
    """多批次档案时，学生端须命中最近未归档档案，否则门禁会落在旧批次。"""
    from app.core.security import create_access_token
    from app.db.session import get_sessionmaker
    from app.models import GraduationMidterm, GraduationStudent

    h = auth_headers
    name = "多批次命中生"
    sno = "MT-MULTI-01"
    sid = client.post(STU, headers=h, json={"studentNo": sno, "realName": name}).json()["data"]["id"]
    old = client.post(GD_STU, headers=h, json={"studentId": sid}).json()["data"]["id"]
    db = get_sessionmaker()()
    # 业务接口对同生重复建档会 409；用第二行模拟历史多批次并存
    row = GraduationStudent(
        tenant_id=1000000000000000001, student_id=int(sid), student_no=sno, name=name,
        stage="GUIDING",
    )
    db.add(row)
    db.flush()
    new = str(row.id)
    assert int(new) > int(old)
    db.add(GraduationMidterm(
        tenant_id=1000000000000000001, gd_student_id=int(new),
        status="RECTIFYING", conclusion="RECTIFY",
        check_comment="新批次整改中", checked_at=datetime.utcnow(),
    ))
    db.commit()
    db.close()
    sh = {"Authorization": "Bearer " + create_access_token({
        "userId": f"u-{name}", "realName": name, "userType": "STUDENT",
        "tid": "demo", "tenantId": "1000000000000000001", "activeContextId": "ctx",
        "currentRoleCode": "STUDENT", "clientType": "MP", "studentNo": sno,
    })}
    blocked = client.post("/api/v1/mobile/graduation/final", headers=sh, json={"finalType": "初稿", "attachments": [_upload_pdf(client, sh)]}).json()
    assert blocked["code"] != 0
    assert ("中期" in (blocked.get("message") or "")) or ("阶段" in (blocked.get("message") or ""))
