"""毕设归档口径对齐：单个学生生成/提交与批量预览、备案使用同一份材料规则。

真实问题：单个学生页只核对 7 项旧业务状态，显示“材料齐全”也能提交；
到备案/批量预览时才被材料规则里的必交项（指导记录附件、学校自加的选题志愿确认单）拦下。
本文件在 MySQL 上验证：generate/submit/详情页与批量预览列出的缺件完全一致，提交被拦时说清缺哪几项。
"""
from __future__ import annotations

import uuid

from sqlalchemy import select

from conftest import make_org_class

GD_STU = "/api/v1/graduation/gd-students"
GD_BATCH = "/api/v1/graduation/batches"
GD_ARCHIVE = "/api/v1/graduation/gd-archives"
STU = "/api/v1/students"
MAIN = 1000000000000000001
CUSTOM_CODE = "TOPIC_WISH_CONFIRM"
CUSTOM_NAME = "选题志愿确认单"


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _batch(graduation_client, h) -> str:
    r = graduation_client.post(GD_BATCH, headers=h, json={
        "batchName": _uniq("归档口径"), "batchNo": _uniq("GD-AP"),
        "gradeYear": "2026届", "plannedCount": 10,
    }).json()
    assert r["code"] == 0, r
    return r["data"]["id"]


def _gd_student(graduation_client, h, batch_id) -> str:
    sno = _uniq("S")
    r = graduation_client.post(STU, headers=h, json={
        "studentNo": sno, "realName": f"口径{sno[-4:]}", "classId": make_org_class(),
    }).json()
    assert r["code"] == 0, r
    r = graduation_client.post(GD_STU, headers=h, json={"studentId": r["data"]["id"], "batchId": batch_id}).json()
    assert r["code"] == 0, r
    return r["data"]["id"]


def _rule(db, batch_id):
    from app.models.graduation_material import GraduationMaterialRule

    return db.scalars(select(GraduationMaterialRule).where(
        GraduationMaterialRule.tenant_id == MAIN,
        GraduationMaterialRule.batch_id == int(batch_id),
        GraduationMaterialRule.status == "ENABLED",
        GraduationMaterialRule.is_deleted.is_(False),
    )).one()


def _add_required_item(db, rule_id: int, code: str, name: str, sort_no: int = 99) -> None:
    from app.models.graduation_material import GraduationMaterialItem

    db.add(GraduationMaterialItem(
        tenant_id=MAIN, rule_id=int(rule_id), biz_stage="TOPIC", material_code=code,
        material_name=name, owner_role="STUDENT", required=True, allowed_ext_json=["pdf"],
        max_files=1, max_size_bytes=10 * 1024 * 1024, version_policy="IMMUTABLE_APPEND",
        review_required=True, archive_required=True, sensitivity_level="SENSITIVE",
        sort_no=sort_no, enabled=True,
    ))


def _school_rule(batch_id) -> None:
    """Mirror a real school rule: 指导记录附件必交 + 学校自加的必交材料。"""
    from app.db.session import get_sessionmaker
    from app.models.graduation_material import GraduationMaterialItem

    db = get_sessionmaker()()
    try:
        rule = _rule(db, batch_id)
        guidance = db.scalars(select(GraduationMaterialItem).where(
            GraduationMaterialItem.tenant_id == MAIN,
            GraduationMaterialItem.rule_id == int(rule.id),
            GraduationMaterialItem.material_code == "GUIDANCE_RECORD",
        )).one()
        guidance.required = True
        _add_required_item(db, int(rule.id), CUSTOM_CODE, CUSTOM_NAME)
        db.commit()
    finally:
        db.close()


def _batch_preview_missing(batch_id, gd_student_id) -> list[str]:
    """Row-level truth of the signed batch preview (same snapshot the file step verifies)."""
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import GraduationBatch
    from app.modules.graduation.services import graduation_archive_consistency as consistency

    set_tenant({"tenantId": str(MAIN)})
    set_current_user({
        "userId": "1", "tenantId": str(MAIN), "realName": "归档口径管理员",
        "currentRoleCode": "SCHOOL_ADMIN", "userType": "TEACHER", "activeContextId": "ctx",
        "dataScope": "ALL",
    })
    db = get_sessionmaker()()
    try:
        batch = db.get(GraduationBatch, int(batch_id))
        snapshot = consistency._snapshot(db, batch, "GENERATE")
        rows = [row for row in snapshot["rows"] if row["studentId"] == str(gd_student_id)]
        assert rows, snapshot
        return list(rows[0]["missing"])
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


def test_generate_lists_rule_items_exactly_like_batch_preview(graduation_client, auth_headers, db_mode):
    h = auth_headers
    batch_id = _batch(graduation_client, h)
    _school_rule(batch_id)
    gid = _gd_student(graduation_client, h, batch_id)

    gen = graduation_client.post(f"{GD_ARCHIVE}/{gid}/generate", headers=h, params={"batchId": batch_id}).json()
    assert gen["code"] == 0, gen
    missing = gen["data"]["missingItems"]
    assert "指导记录附件" in missing
    assert CUSTOM_NAME in missing
    labels = {row["label"] for row in gen["data"]["checklist"]}
    assert {"指导记录附件", CUSTOM_NAME} <= labels
    # 单个学生与批量预览同一口径：缺件清单逐项相同。
    assert sorted(missing) == sorted(_batch_preview_missing(batch_id, gid))


def test_submit_is_blocked_with_named_items_and_page_keeps_them(graduation_client, auth_headers, db_mode):
    h = auth_headers
    batch_id = _batch(graduation_client, h)
    _school_rule(batch_id)
    gid = _gd_student(graduation_client, h, batch_id)
    assert graduation_client.post(f"{GD_ARCHIVE}/{gid}/generate", headers=h,
                                  params={"batchId": batch_id}).json()["code"] == 0

    sub = graduation_client.post(f"{GD_ARCHIVE}/{gid}/submit", headers=h, params={"batchId": batch_id}).json()
    assert sub["code"] != 0, sub
    assert "不能提交归档" in sub["message"]
    assert "指导记录附件" in sub["message"]
    assert CUSTOM_NAME in sub["message"]

    detail = graduation_client.get(f"{GD_ARCHIVE}/{gid}", headers=h, params={"batchId": batch_id}).json()
    assert detail["code"] == 0, detail
    assert detail["data"]["status"] == "PENDING_SUBMIT"
    assert CUSTOM_NAME in detail["data"]["missingItems"]

    # 被拦截的提交也把最新缺件写回归档记录（列表页同样能看到），并留审计。
    from app.db.session import get_sessionmaker
    from app.models import GraduationArchiveRecord, GraduationAuditTrail

    db = get_sessionmaker()()
    try:
        archive = db.scalars(select(GraduationArchiveRecord).where(
            GraduationArchiveRecord.tenant_id == MAIN,
            GraduationArchiveRecord.gd_student_id == int(gid),
        )).one()
        assert archive.status == "PENDING_SUBMIT"
        assert CUSTOM_NAME in (archive.missing_items or [])
        trail = db.scalars(select(GraduationAuditTrail).where(
            GraduationAuditTrail.tenant_id == MAIN,
            GraduationAuditTrail.biz_id == str(archive.id),
            GraduationAuditTrail.action == "提交归档被拦截",
        )).all()
        assert trail
    finally:
        db.close()


def test_detail_rechecks_live_after_rule_gains_required_item(graduation_client, auth_headers, db_mode):
    h = auth_headers
    batch_id = _batch(graduation_client, h)
    gid = _gd_student(graduation_client, h, batch_id)
    gen = graduation_client.post(f"{GD_ARCHIVE}/{gid}/generate", headers=h, params={"batchId": batch_id}).json()
    assert gen["code"] == 0, gen
    assert "新增必交表" not in gen["data"]["missingItems"]

    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        _add_required_item(db, int(_rule(db, batch_id).id), "SCHOOL_EXTRA_FORM", "新增必交表")
        db.commit()
    finally:
        db.close()

    detail = graduation_client.get(f"{GD_ARCHIVE}/{gid}", headers=h, params={"batchId": batch_id}).json()
    assert detail["code"] == 0, detail
    assert "新增必交表" in detail["data"]["missingItems"]


def test_rule_check_flags_rule_items_even_when_legacy_items_all_present(db_mode):
    """复现原缺陷：7 项旧业务状态全部齐全，但材料规则必交项未交，必须判为缺件。"""
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import GraduationBatch, GraduationStudent
    from app.models.graduation_material import GraduationMaterialRule
    from app.modules.graduation.services.graduation_archive_v2_preview import student_rule_check

    set_tenant({"tenantId": str(MAIN)})
    set_current_user({"userId": "1", "tenantId": str(MAIN), "currentRoleCode": "SCHOOL_ADMIN",
                      "userType": "TEACHER", "activeContextId": "ctx"})
    db = get_sessionmaker()()
    try:
        batch = GraduationBatch(tenant_id=MAIN, batch_name=_uniq("口径单测"), batch_no=_uniq("GD-UT"),
                                grade_year="2026届", status="RUNNING")
        db.add(batch)
        db.flush()
        rule = GraduationMaterialRule(
            tenant_id=MAIN, batch_id=int(batch.id), rule_code="GD_MATERIAL_STANDARD",
            rule_name="口径单测规则", rule_version=1, status="ENABLED", enabled=True,
            default_owner_role="STUDENT", version_policy="IMMUTABLE_APPEND", archive_required=True,
            sensitivity_level="SENSITIVE", applicable_scope_json={}, required_items_json=[],
            allowed_ext_json=["pdf"], max_files=1, max_size_bytes=1024,
        )
        db.add(rule)
        db.flush()
        from app.models.graduation_material import GraduationMaterialItem

        db.add(GraduationMaterialItem(
            tenant_id=MAIN, rule_id=int(rule.id), biz_stage="TASKBOOK", material_code="TASKBOOK",
            material_name="任务书", owner_role="MENTOR", required=True, allowed_ext_json=["pdf"],
            max_files=1, max_size_bytes=1024, version_policy="IMMUTABLE_APPEND", review_required=True,
            archive_required=True, sensitivity_level="SENSITIVE", sort_no=1, enabled=True,
        ))
        db.add(GraduationMaterialItem(
            tenant_id=MAIN, rule_id=int(rule.id), biz_stage="GUIDANCE", material_code="GUIDANCE_RECORD",
            material_name="指导记录附件", owner_role="MENTOR", required=True, allowed_ext_json=["pdf"],
            max_files=1, max_size_bytes=1024, version_policy="IMMUTABLE_APPEND", review_required=False,
            archive_required=True, sensitivity_level="SENSITIVE", sort_no=2, enabled=True,
        ))
        _add_required_item(db, int(rule.id), CUSTOM_CODE, CUSTOM_NAME, sort_no=3)
        student = GraduationStudent(tenant_id=MAIN, batch_id=int(batch.id), student_no=_uniq("GDUT"),
                                    name="口径单测生", stage="COMPLETED", record_status="ACTIVE")
        db.add(student)
        db.commit()

        legacy = [{"item": key, "label": key, "present": True, "required": True}
                  for key in ("taskbook", "proposal", "midterm", "final", "review", "defenseScore", "grade")]
        checklist, missing = student_rule_check(db, student, legacy, [])
        assert "任务书" not in missing  # 系统快照项沿用业务状态
        assert missing == ["指导记录附件", CUSTOM_NAME]
        assert [row["label"] for row in checklist] == ["任务书", "指导记录附件", CUSTOM_NAME]
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


def test_batch_preview_explains_skips_per_student_in_plain_words(graduation_client, auth_headers, db_mode):
    """批量预览说清每个被跳过学生的原因（缺哪几项 / 几条风险没关），并可定位到学生。"""
    h = auth_headers
    batch_id = _batch(graduation_client, h)
    _school_rule(batch_id)
    missing_gid = _gd_student(graduation_client, h, batch_id)
    risk_gid = _gd_student(graduation_client, h, batch_id)

    from app.db.session import get_sessionmaker
    from app.models import GraduationRiskCase

    db = get_sessionmaker()()
    try:
        for code in ("GD-R06", "GD-R07"):
            db.add(GraduationRiskCase(
                tenant_id=MAIN, risk_code=code, risk_name="测试风险", gd_student_id=int(risk_gid),
                level="MEDIUM", status="OPEN",
            ))
        db.commit()
    finally:
        db.close()

    for path in ("batch-generate/preview", "batch-file/preview"):
        body = graduation_client.post(f"{GD_ARCHIVE}/{path}", headers=h, params={"batchId": batch_id}).json()
        assert body["code"] == 0, body
        data = body["data"]
        assert {"skippedStudents", "skippedStudentsTruncated", "missingSummary", "openRiskTotal"} <= set(data)
        # 名单条数与计数一致（未截断时）。
        assert len(data["skippedStudents"]) == data["skippedCount"]

    data = graduation_client.post(f"{GD_ARCHIVE}/batch-generate/preview", headers=h,
                                  params={"batchId": batch_id}).json()["data"]
    rows = {row["gdStudentId"]: row for row in data["skippedStudents"]}
    assert set(rows) == {str(missing_gid), str(risk_gid)}
    missing_row = rows[str(missing_gid)]
    assert missing_row["studentName"].startswith("口径") and missing_row["studentNo"]
    assert any(text.startswith("缺：") and CUSTOM_NAME in text for text in missing_row["reasons"])
    assert "还有 2 条风险没关闭" in rows[str(risk_gid)]["reasons"]
    assert data["openRiskTotal"] == 2
    summary = {item["name"]: item["count"] for item in data["missingSummary"]}
    assert summary[CUSTOM_NAME] == 2 and summary["指导记录附件"] == 2
    # 页面文字里不出现内部词。
    flat = " ".join(" ".join(row["reasons"]) for row in data["skippedStudents"])
    assert "missing_materials" not in flat and "open_risks" not in flat
