"""U11：合规工作台首屏拆分（summary 计数 + 按 Tab 懒加载分组）等价性回归。

旧接口 get_workbench() 一次性把 8 组完整列表都拉出来，6 项统计数字是遍历这些
已加载列表现算的。拆分只允许换取数方式，不许改口径——本文件把「口径没变」
变成可执行断言：

1. 新 summary 的 counts（纯 SQL COUNT）必须与按旧口径（Python 遍历已加载列表）
   独立复算出的结果逐项相等；
2. 按 Tab 懒加载的每个分组，内容必须与旧一次性接口里同一分组完全一致；
3. SCOPED 教师与校级角色的可见范围（含仅校级可见的批次级事故/证据包）必须两条
   路径都收敛一致，不能因为拆分漏掉范围。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

TID = 1000000000000000002
# 授权只认 advisor_user_id（见 internship_advisor_identity_guard），姓名只作展示快照。
LIU_UID = "501"
WANG_UID = "502"


def _ctx(role="SCHOOL_ADMIN", real_name="实习处", user_id="1", **extra):
    """包 8 第一组（internship_advisor_identity_guard）已把 SCOPED 导师授权硬化成
    只认 InternshipRecord.advisor_user_id == token.userId，advisor_name 只作展示快照、
    不再参与授权判断。SCOPED 用例必须传与种子记录一致的 user_id，不能只对姓名。"""
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TID)})
    payload = {"userId": user_id, "tenantId": str(TID), "realName": real_name,
               "userType": "ADMIN" if role != "INTERN_MENTOR" else "TEACHER",
               "currentRoleCode": role, "activeContextId": "ctx"}
    payload.update(extra)
    set_current_user(payload)
    return payload


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


def _seed(db):
    """一个批次 + 4 名学生（导师 刘强 x2 / 王芳 x2），覆盖 6 个分组的多种状态，
    并特意混入「批次级事故」与「批次级证据包」（internship_id/target_id 不落在
    任何一个学生名下，只有校级角色能看见）。"""
    from app.models import (
        InternshipBatch, InternshipComplianceExemption, InternshipConsent,
        InternshipEmergencyPlan, InternshipEvidencePackage, InternshipIncident,
        InternshipRecord, InternshipSafetyCompletion, InternshipSafetyCourse,
        InternshipSpecialFiling, StudentProfile,
    )

    batch = InternshipBatch(tenant_id=TID, batch_name="U11拆分测试批次",
                            batch_no=f"U11-{uuid.uuid4().hex[:8]}", status="RUNNING")
    db.add(batch)
    db.flush()

    advisors = [("刘强", LIU_UID), ("刘强", LIU_UID), ("王芳", WANG_UID), ("王芳", WANG_UID)]
    records = []
    for i, (adv, adv_uid) in enumerate(advisors):
        stu = StudentProfile(tenant_id=TID, student_no=f"U11S{uuid.uuid4().hex[:8]}",
                             real_name=f"合规学生{i}", grade="2024",
                             student_status="NORMAL", status="ACTIVE")
        db.add(stu)
        db.flush()
        rec = InternshipRecord(tenant_id=TID, student_id=stu.id, batch_id=batch.id,
                               status="ONBOARD", advisor_name=adv, advisor_user_id=int(adv_uid))
        db.add(rec)
        db.flush()
        records.append(rec)
    db.flush()

    now = datetime.utcnow()

    # 知情确认：2 条 PENDING（刘强1 + 王芳1）、1 条 VALID（刘强）
    db.add(InternshipConsent(tenant_id=TID, internship_id=records[0].id, batch_id=batch.id,
                             student_id=records[0].student_id, consent_type="STUDENT",
                             status="PENDING"))
    db.add(InternshipConsent(tenant_id=TID, internship_id=records[1].id, batch_id=batch.id,
                             student_id=records[1].student_id, consent_type="STUDENT",
                             status="VALID"))
    db.add(InternshipConsent(tenant_id=TID, internship_id=records[2].id, batch_id=batch.id,
                             student_id=records[2].student_id, consent_type="STUDENT",
                             status="PENDING"))

    # 安全教育：1 门课程 + 完成记录（PENDING_REVIEW/PASSED/NOT_STARTED 各一）
    course = InternshipSafetyCourse(tenant_id=TID, batch_id=batch.id, title="岗前安全教育",
                                    course_version="v1", status="ACTIVE")
    db.add(course)
    db.flush()
    db.add(InternshipSafetyCompletion(tenant_id=TID, internship_id=records[0].id, batch_id=batch.id,
                                      student_id=records[0].student_id, course_id=course.id,
                                      course_version="v1", status="PENDING_REVIEW"))
    db.add(InternshipSafetyCompletion(tenant_id=TID, internship_id=records[1].id, batch_id=batch.id,
                                      student_id=records[1].student_id, course_id=course.id,
                                      course_version="v1", status="PASSED"))
    db.add(InternshipSafetyCompletion(tenant_id=TID, internship_id=records[2].id, batch_id=batch.id,
                                      student_id=records[2].student_id, course_id=course.id,
                                      course_version="v1", status="NOT_STARTED"))

    # 特殊备案：1 条 DRAFT（待处理）+ 1 条 APPROVED（刘强、王芳各一）
    db.add(InternshipSpecialFiling(tenant_id=TID, internship_id=records[0].id, batch_id=batch.id,
                                   student_id=records[0].student_id, filing_type="HIGH_RISK",
                                   status="DRAFT"))
    db.add(InternshipSpecialFiling(tenant_id=TID, internship_id=records[2].id, batch_id=batch.id,
                                   student_id=records[2].student_id, filing_type="OTHER",
                                   status="APPROVED"))

    # 事故：学生级 REPORTED（刘强）、学生级 CLOSED（不计入 open）、批次级 REPORTED（仅校级可见）
    db.add(InternshipIncident(tenant_id=TID, batch_id=batch.id, internship_id=records[0].id,
                              student_id=records[0].student_id, incident_no=f"INC-{uuid.uuid4().hex[:8]}",
                              incident_type="INJURY", severity="MEDIUM", status="REPORTED"))
    db.add(InternshipIncident(tenant_id=TID, batch_id=batch.id, internship_id=records[1].id,
                              student_id=records[1].student_id, incident_no=f"INC-{uuid.uuid4().hex[:8]}",
                              incident_type="INJURY", severity="LOW", status="CLOSED"))
    db.add(InternshipIncident(tenant_id=TID, batch_id=batch.id, internship_id=None,
                              student_id=None, incident_no=f"INC-{uuid.uuid4().hex[:8]}",
                              incident_type="ENTERPRISE", severity="HIGH", status="REPORTED"))

    # 应急预案：仅校级 / COLLEGE_ADMIN 可见
    db.add(InternshipEmergencyPlan(tenant_id=TID, batch_id=batch.id, plan_name="批次应急预案",
                                   status="DRAFT"))

    # 豁免：1 条 PENDING_REVIEW（刘强）+ 1 条 APPROVED（王芳）
    db.add(InternshipComplianceExemption(tenant_id=TID, internship_id=records[0].id, batch_id=batch.id,
                                         check_code="insurance", reason="测试豁免原因占位",
                                         status="PENDING_REVIEW"))
    db.add(InternshipComplianceExemption(tenant_id=TID, internship_id=records[2].id, batch_id=batch.id,
                                         check_code="agreement", reason="测试豁免原因占位2",
                                         status="APPROVED"))

    # 证据包：学生级 READY（刘强）+ 批次级 READY（仅校级可见）
    db.add(InternshipEvidencePackage(tenant_id=TID, batch_id=batch.id, package_type="STUDENT",
                                     target_id=records[0].id, package_version=1, status="READY",
                                     generated_at=now))
    db.add(InternshipEvidencePackage(tenant_id=TID, batch_id=batch.id, package_type="BATCH",
                                     target_id=batch.id, package_version=1, status="READY",
                                     generated_at=now))

    db.flush()
    return batch.id, [r.id for r in records]


def _legacy_counts(batch_id, user):
    """旧口径：完整调用 get_workbench()，用 Python 对已加载列表做与原实现完全相同的
    过滤/计数逻辑——独立于新 _counts() 的 SQL 实现，作为等价性基准。"""
    from app.modules.internship.services import internship_compliance_workbench_service as ws

    full = ws.get_workbench(batch_id, user)
    return {
        "consentPending": sum(1 for row in full["consents"] if row["status"] == "PENDING"),
        "safetyPending": sum(1 for row in full["safetyCompletions"]
                             if row["status"] in ("PENDING_REVIEW", "IN_PROGRESS", "NOT_STARTED")),
        "filingPending": sum(1 for row in full["filings"]
                             if row["status"] in ("DRAFT", "PENDING_COLLEGE", "PENDING_SCHOOL")),
        "incidentOpen": sum(1 for row in full["incidents"] if row["status"] != "CLOSED"),
        "exemptionPending": sum(1 for row in full["exemptions"] if row["status"] == "PENDING_REVIEW"),
        "packageReady": sum(1 for row in full["evidencePackages"]
                            if row["status"] in ("READY", "READY_WITH_MISSING")),
    }, full


@pytest.fixture()
def seeded(db_mode):
    db = _session()
    batch_id, record_ids = _seed(db)
    db.commit()
    db.close()
    return batch_id, record_ids


def test_summary_counts_match_legacy_python_filter_school_admin(seeded, db_mode):
    batch_id, _ = seeded
    user = _ctx("SCHOOL_ADMIN")
    from app.modules.internship.services import internship_compliance_workbench_service as ws

    legacy_counts, full = _legacy_counts(str(batch_id), user)
    summary = ws.get_workbench_summary(str(batch_id), user)

    assert summary["counts"] == legacy_counts, (
        f"校级角色：新 SQL COUNT 与旧 Python 遍历口径不一致\n"
        f"new={summary['counts']}\nlegacy={legacy_counts}")
    # 种子事实核验（防止两边都错但恰好相等）
    assert legacy_counts == {
        "consentPending": 2, "safetyPending": 2, "filingPending": 1,
        "incidentOpen": 2, "exemptionPending": 1, "packageReady": 2,
    }, f"种子事实与预期不符：{legacy_counts}"
    assert summary["batch"]["studentCount"] == 4 == full["batch"]["studentCount"]


def test_summary_counts_match_legacy_python_filter_scoped_mentor(seeded, db_mode):
    """SCOPED 导师「刘强」：只看得到自己名下 2 名学生，且看不到批次级事故/证据包。"""
    batch_id, _ = seeded
    user = _ctx("INTERN_MENTOR", real_name="刘强", user_id=LIU_UID)
    from app.modules.internship.services import internship_compliance_workbench_service as ws

    legacy_counts, full = _legacy_counts(str(batch_id), user)
    summary = ws.get_workbench_summary(str(batch_id), user)

    assert summary["counts"] == legacy_counts, (
        f"SCOPED 导师：新 SQL COUNT 与旧 Python 遍历口径不一致\n"
        f"new={summary['counts']}\nlegacy={legacy_counts}")
    # 刘强只带 2 个学生：1 条 PENDING 知情确认、1 条 PENDING_REVIEW 安全教育、
    # 1 条 DRAFT 备案、1 条学生级开放事故（批次级事故对 SCOPED 不可见）、
    # 1 条 PENDING_REVIEW 豁免、1 条学生级证据包（批次级证据包不可见）。
    assert legacy_counts == {
        "consentPending": 1, "safetyPending": 1, "filingPending": 1,
        "incidentOpen": 1, "exemptionPending": 1, "packageReady": 1,
    }, f"SCOPED 种子事实与预期不符（范围收敛可能漏了）：{legacy_counts}"
    assert summary["batch"]["studentCount"] == 2 == full["batch"]["studentCount"]


@pytest.mark.parametrize("group,keys", [
    ("consents", ["consents"]),
    ("safety", ["safetyCourses", "safetyCompletions"]),
    ("filings", ["filings"]),
    ("incidents", ["incidents", "emergencyPlans"]),
    ("exemptions", ["exemptions"]),
    ("evidence", ["evidencePackages"]),
])
def test_group_lazyload_matches_full_workbench_school_admin(seeded, db_mode, group, keys):
    batch_id, _ = seeded
    user = _ctx("SCHOOL_ADMIN")
    from app.modules.internship.services import internship_compliance_workbench_service as ws

    full = ws.get_workbench(str(batch_id), user)
    part = ws.get_workbench_group(str(batch_id), group, user)

    assert set(part.keys()) == set(keys)
    for key in keys:
        assert part[key] == full[key], f"分组 {group}.{key} 懒加载结果与全量接口不一致"


def test_group_lazyload_matches_full_workbench_scoped_mentor(seeded, db_mode):
    batch_id, _ = seeded
    user = _ctx("INTERN_MENTOR", real_name="王芳", user_id=WANG_UID)
    from app.modules.internship.services import internship_compliance_workbench_service as ws

    full = ws.get_workbench(str(batch_id), user)
    for group, keys in [
        ("consents", ["consents"]), ("safety", ["safetyCourses", "safetyCompletions"]),
        ("filings", ["filings"]), ("incidents", ["incidents", "emergencyPlans"]),
        ("exemptions", ["exemptions"]), ("evidence", ["evidencePackages"]),
    ]:
        part = ws.get_workbench_group(str(batch_id), group, user)
        for key in keys:
            assert part[key] == full[key], f"王芳视角分组 {group}.{key} 懒加载与全量不一致"

    # 王芳只应看到自己名下的学生，看不到刘强的知情确认/豁免
    names = {row["studentName"] for row in full["consents"]}
    assert names and all("合规学生2" in n or "合规学生3" in n for n in names), (
        f"SCOPED 范围疑似泄漏了其他导师的学生：{names}")
    # 批次级事故/证据包对 SCOPED 教师不可见
    assert all(row["internshipId"] for row in full["incidents"]), "SCOPED 视角不应看到批次级事故"
    assert full["emergencyPlans"] == [], "非校级/学院角色不应看到应急预案"


@pytest.mark.parametrize("role,real_name,user_id", [
    ("SCHOOL_ADMIN", "实习处", "1"),
    ("INTERN_MENTOR", "刘强", LIU_UID),
    ("INTERN_MENTOR", "王芳", WANG_UID),
    ("COLLEGE_ADMIN", "学院办", "9"),
])
def test_bulk_scope_path_selects_same_records_as_per_row_path(seeded, db_mode,
                                                              role, real_name, user_id):
    """`_allowed_records` 改用批量预加载后，可见记录集合必须与逐行判定完全一致。

    这是数据范围函数，判错就是越权/漏看。基准不是"新代码跟自己比"，而是在测试里
    按改造前的写法（逐行 db.get(StudentProfile) + 逐行 _rec_in_scope）独立重算一遍。
    """
    batch_id, _ = seeded
    user = _ctx(role, real_name=real_name, user_id=user_id)
    from sqlalchemy import select

    from app.models import InternshipRecord, StudentProfile
    from app.modules.internship.services import internship_service as domain_service
    from app.modules.internship.services import internship_compliance_workbench_service as ws
    from app.services.db_service import _tid

    db = _session()
    try:
        # 改造前的判定路径（逐行取学生 + 逐行 _rec_in_scope）
        batch, new_records, new_students = ws._allowed_records(db, str(batch_id), user)
        rows = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
        ).order_by(InternshipRecord.id.desc())).all()
        scope = domain_service._current_scope(user)
        legacy_ids = []
        for record in rows:
            student = db.get(StudentProfile, record.student_id)
            if student and domain_service._rec_in_scope(scope, db, record, student):
                legacy_ids.append(record.id)
    finally:
        db.close()

    new_ids = sorted(r.id for r in new_records)
    assert new_ids == sorted(legacy_ids), (
        f"{role}/{real_name} 视角下批量判定与逐行判定选出的记录不一致：\n"
        f"批量={new_ids}\n逐行={sorted(legacy_ids)}\n"
        "数据范围口径变了——要么有人看不到本该看到的，要么看到了不该看到的。")
    # 学生映射也必须齐全，否则明细行会退化成 '-' 占位
    assert set(new_students) == {r.student_id for r in new_records}


def test_unknown_group_rejected(seeded, db_mode):
    batch_id, _ = seeded
    user = _ctx("SCHOOL_ADMIN")
    from app.core.exceptions import AppException
    from app.modules.internship.services import internship_compliance_workbench_service as ws

    with pytest.raises(AppException):
        ws.get_workbench_group(str(batch_id), "not-a-real-group", user)


def test_college_admin_sees_emergency_plan(seeded, db_mode):
    """应急预案可见性是「校级 或 COLLEGE_ADMIN」，事故/证据包可见性是「仅校级」——
    两条规则不是同一个开关，拆分后不能被合并成一个判断。COLLEGE_ADMIN 按学院收敛，
    种子学生未挂学院，这里只验证应急预案分支本身，不掺和学院匹配。"""
    batch_id, _ = seeded
    user = _ctx("COLLEGE_ADMIN", real_name="学院办")
    from app.modules.internship.services import internship_compliance_workbench_service as ws

    part_incidents = ws.get_workbench_group(str(batch_id), "incidents", user)
    assert part_incidents["emergencyPlans"], "COLLEGE_ADMIN 应能看到应急预案"
