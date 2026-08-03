"""SYS-17 主数据责任与数据质量（真库）。

对应必测 SYS17-T01～T04：
P0 问题有 owner 与 SLA / 合并预览列出所有引用 / 修复后重新扫描验证 / 例外有期限和审批。
"""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.core.context import set_tenant
from app.core.exceptions import AppException
from app.services import master_data_governance_service as md

MAIN_TENANT_ID = 1000000000000000001
ADMIN = {"userId": "db-1", "currentRoleCode": "SCHOOL_ADMIN"}


def _session():
    from app.db.session import get_sessionmaker

    return get_sessionmaker()()


@pytest.fixture()
def tenant_ctx(db_mode):
    from app.models import Tenant

    with _session() as db:
        if db.get(Tenant, MAIN_TENANT_ID) is None:
            db.add(Tenant(id=MAIN_TENANT_ID, tenant_code="demo",
                          school_name="主数据测试学校", status="ACTIVE"))
            db.commit()
    set_tenant({"tenantId": str(MAIN_TENANT_ID)})
    md.bootstrap_defaults(tenant_id=MAIN_TENANT_ID)
    try:
        yield MAIN_TENANT_ID
    finally:
        set_tenant(None)


def _make_user(login_name: str) -> int:
    from app.core.security import hash_password
    from app.models import User

    with _session() as db:
        row = User(tenant_id=MAIN_TENANT_ID, login_name=login_name, real_name="数据责任人",
                   password_hash=hash_password("Init123456"), user_type="TEACHER",
                   status="ACTIVE")
        db.add(row)
        db.commit()
        return int(row.id)


def _make_org(*, college_code: str | None = None) -> tuple[int, int, int]:
    from app.models.org import College, Major, SchoolClass

    with _session() as db:
        col = College(tenant_id=MAIN_TENANT_ID, college_name=f"学院-{uuid4().hex[:6]}",
                      code=college_code, status="ACTIVE")
        db.add(col)
        db.flush()
        maj = Major(tenant_id=MAIN_TENANT_ID, college_id=col.id,
                    major_name=f"专业-{uuid4().hex[:6]}", status="ACTIVE")
        db.add(maj)
        db.flush()
        cls = SchoolClass(tenant_id=MAIN_TENANT_ID, major_id=maj.id,
                          class_name=f"班级-{uuid4().hex[:6]}", grade="2026",
                          status="ACTIVE", class_status="NORMAL")
        db.add(cls)
        db.commit()
        return int(col.id), int(maj.id), int(cls.id)


def _make_student(*, class_id: int | None, name: str = "测试学生") -> int:
    from app.models import StudentProfile

    with _session() as db:
        row = StudentProfile(tenant_id=MAIN_TENANT_ID, student_no=f"S{uuid4().hex[:10]}",
                             real_name=name, class_id=class_id, current_stage="IN_SCHOOL",
                             student_status="NORMAL", status="ACTIVE")
        db.add(row)
        db.commit()
        return int(row.id)


def _issues(rule_code: str) -> list[dict]:
    rows = md.list_issues(tenant_id=MAIN_TENANT_ID)["list"]
    return [r for r in rows if r["ruleCode"] == rule_code]


# ── SYS17-T01：P0 必须有责任人和 SLA ────────────────────────────────────────
def test_t01_p0_rule_requires_owner_and_sla(tenant_ctx):
    _make_org(college_code="DUP001")
    _make_org(college_code="DUP001")  # 制造真实的编码重复

    # 还没指定责任人 → P0 规则不许运行
    with pytest.raises(AppException) as caught:
        md.scan(rule_code="ORG_DUPLICATE_CODE", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert "尚未指定责任人" in caught.value.message

    owner_id = _make_user("md_owner_org")
    md.set_domain_owner(md.DOMAIN_ORG, owner_user_id=owner_id, reason="指定组织主数据责任人",
                        tenant_id=MAIN_TENANT_ID, user=ADMIN)

    result = md.scan(rule_code="ORG_DUPLICATE_CODE", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert result["opened"] >= 1

    rows = _issues("ORG_DUPLICATE_CODE")
    assert rows, "重复编码必须扫出问题"
    for row in rows:
        assert row["severity"] == md.SEVERITY_P0
        assert row["ownerUserId"] == str(owner_id), "P0 问题必须自动带上责任人"
        assert row["dueAt"], "P0 问题必须有 SLA 到期时间"

    summary = md.list_issues(tenant_id=MAIN_TENANT_ID)["summary"]
    assert summary["p0WithoutOwner"] == 0


def test_t01b_p0_rule_without_sla_is_rejected(tenant_ctx):
    from app.models.master_data_governance import DataQualityRule
    from sqlalchemy import select

    owner_id = _make_user("md_owner_org2")
    md.set_domain_owner(md.DOMAIN_ORG, owner_user_id=owner_id, reason="指定组织主数据责任人",
                        tenant_id=MAIN_TENANT_ID, user=ADMIN)
    with _session() as db:
        rule = db.scalars(select(DataQualityRule).where(
            DataQualityRule.tenant_id == MAIN_TENANT_ID,
            DataQualityRule.rule_code == "ORG_DUPLICATE_CODE")).first()
        rule.sla_hours = None
        db.commit()

    with pytest.raises(AppException) as caught:
        md.scan(rule_code="ORG_DUPLICATE_CODE", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert "SLA" in caught.value.message


def test_t01c_domain_list_exposes_missing_owners(tenant_ctx):
    listed = md.list_domains(tenant_id=MAIN_TENANT_ID)
    assert set(listed["domainsWithoutOwner"]) >= {md.DOMAIN_ORG, md.DOMAIN_STUDENT}
    owner_id = _make_user("md_owner_student")
    md.set_domain_owner(md.DOMAIN_STUDENT, owner_user_id=owner_id, reason="指定学生主档责任人",
                        tenant_id=MAIN_TENANT_ID, user=ADMIN)
    after = md.list_domains(tenant_id=MAIN_TENANT_ID)
    assert md.DOMAIN_STUDENT not in after["domainsWithoutOwner"]
    student_domain = next(d for d in after["list"] if d["domainCode"] == md.DOMAIN_STUDENT)
    assert student_domain["ownerUserId"] == str(owner_id)
    assert student_domain["authoritativeTable"] == "t_student_profile"


# ── SYS17-T02：合并预览列出所有引用 ─────────────────────────────────────────
def test_t02_merge_preview_lists_every_reference(tenant_ctx):
    from datetime import datetime as dt

    from app.models import StudentAccountLink, StudentContact

    _col, _maj, class_id = _make_org()
    keep = _make_student(class_id=class_id, name="张三")
    dup = _make_student(class_id=class_id, name="张三")
    user_id = _make_user("md_dup_account")
    with _session() as db:
        db.add(StudentContact(tenant_id=MAIN_TENANT_ID, student_id=dup, contact_type="PHONE",
                              contact_value_encrypted="13800000000", is_primary=True,
                              verified_status="VERIFIED"))
        db.add(StudentAccountLink(tenant_id=MAIN_TENANT_ID, student_id=dup, user_id=user_id,
                                  link_status="ACTIVE", source="MANUAL",
                                  bound_at=dt.now().replace(microsecond=0)))
        db.commit()

    preview = md.merge_preview(md.DOMAIN_STUDENT, primary_object_id=str(keep),
                               merged_object_id=str(dup), reason="疑似重复建档合并",
                               tenant_id=MAIN_TENANT_ID, user=ADMIN)

    tables = {r["table"]: r["count"] for r in preview["references"]}
    assert tables.get("t_student_account_link") == 1
    assert tables.get("t_student_contact") == 1
    # 没有引用的表也必须出现在清单里（0 也是结论，不能省略）
    assert "t_gd_student" in tables and "t_internship_record" in tables
    assert preview["totalReferences"] == 2
    assert preview["autoMergeAllowed"] is False, "系统管理不得自动执行高风险合并"
    assert preview["previewHash"]

    events = md.list_merge_events(tenant_id=MAIN_TENANT_ID)
    assert events["total"] == 1
    assert events["list"][0]["status"] == md.MERGE_PREVIEW


def test_t02b_merge_preview_validates_input(tenant_ctx):
    with pytest.raises(AppException):
        md.merge_preview(md.DOMAIN_STUDENT, primary_object_id="1", merged_object_id="1",
                         reason="保留方与被并方相同", tenant_id=MAIN_TENANT_ID)
    with pytest.raises(AppException):
        md.merge_preview("NOT_A_DOMAIN", primary_object_id="1", merged_object_id="2",
                         reason="不支持的域", tenant_id=MAIN_TENANT_ID)
    with pytest.raises(AppException):
        md.merge_preview(md.DOMAIN_STUDENT, primary_object_id="1", merged_object_id="2",
                         reason="短", tenant_id=MAIN_TENANT_ID)


# ── SYS17-T03：修复后必须复扫验证 ───────────────────────────────────────────
def test_t03_resolve_then_verify_by_rescan(tenant_ctx):
    from app.models import StudentProfile

    owner_id = _make_user("md_owner_student2")
    md.set_domain_owner(md.DOMAIN_STUDENT, owner_user_id=owner_id, reason="指定学生主档责任人",
                        tenant_id=MAIN_TENANT_ID, user=ADMIN)
    _col, _maj, class_id = _make_org()
    orphan = _make_student(class_id=None)

    md.scan(rule_code="STUDENT_MISSING_CLASS", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    # db_mode 夹具本身就种了一个未挂班的学生，这里只认自己造的那条
    mine = [r for r in _issues("STUDENT_MISSING_CLASS") if r["objectId"] == str(orphan)]
    assert len(mine) == 1
    issue_id = int(mine[0]["issueId"])

    # 只是"声明修好了"，还没真改数据 → 复扫必须打回
    md.resolve_issue(issue_id, note="已联系辅导员补挂班级", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert md.get_issue(issue_id, tenant_id=MAIN_TENANT_ID)["status"] == md.ISSUE_RESOLVED
    after_fake = md.verify_issue(issue_id, tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert after_fake["status"] == md.ISSUE_OPEN
    assert after_fake["verifyResult"] == "STILL_PRESENT"

    # 真改数据后再复扫 → 才算核销
    with _session() as db:
        db.get(StudentProfile, orphan).class_id = class_id
        db.commit()
    after_real = md.verify_issue(issue_id, tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert after_real["status"] == md.ISSUE_VERIFIED
    assert after_real["verifyResult"] == "GONE"


def test_t03b_rescan_reopens_resolved_but_unfixed_issue(tenant_ctx):
    owner_id = _make_user("md_owner_student3")
    md.set_domain_owner(md.DOMAIN_STUDENT, owner_user_id=owner_id, reason="指定学生主档责任人",
                        tenant_id=MAIN_TENANT_ID, user=ADMIN)
    _make_student(class_id=None)
    md.scan(rule_code="STUDENT_MISSING_CLASS", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    issue_id = int(_issues("STUDENT_MISSING_CLASS")[0]["issueId"])
    md.resolve_issue(issue_id, note="声称已处理", tenant_id=MAIN_TENANT_ID, user=ADMIN)

    md.scan(rule_code="STUDENT_MISSING_CLASS", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    row = md.get_issue(issue_id, tenant_id=MAIN_TENANT_ID)
    assert row["status"] == md.ISSUE_OPEN
    assert row["verifyResult"] == "STILL_PRESENT"


def test_t03c_scan_is_idempotent_and_clears_fixed_issues(tenant_ctx):
    from app.models import StudentProfile

    owner_id = _make_user("md_owner_student4")
    md.set_domain_owner(md.DOMAIN_STUDENT, owner_user_id=owner_id, reason="指定学生主档责任人",
                        tenant_id=MAIN_TENANT_ID, user=ADMIN)
    _col, _maj, class_id = _make_org()
    orphan = _make_student(class_id=None)

    first = md.scan(rule_code="STUDENT_MISSING_CLASS", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert first["opened"] >= 1
    opened_first = first["opened"]
    second = md.scan(rule_code="STUDENT_MISSING_CLASS", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert second["opened"] == 0, "重复扫描不得堆重复问题"
    assert second["updated"] == opened_first, "同一批问题应逐条更新而不是新增"

    with _session() as db:
        db.get(StudentProfile, orphan).class_id = class_id
        db.commit()
    third = md.scan(rule_code="STUDENT_MISSING_CLASS", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert third["cleared"] == 1, "只应核销真正被修好的那一条"
    mine = [r for r in _issues("STUDENT_MISSING_CLASS") if r["objectId"] == str(orphan)]
    assert mine and mine[0]["status"] == md.ISSUE_VERIFIED


# ── SYS17-T04：例外必须有期限和审批 ─────────────────────────────────────────
def test_t04_exception_requires_deadline_and_approver(tenant_ctx):
    owner_id = _make_user("md_owner_student5")
    approver_id = _make_user("md_approver")
    md.set_domain_owner(md.DOMAIN_STUDENT, owner_user_id=owner_id, reason="指定学生主档责任人",
                        tenant_id=MAIN_TENANT_ID, user=ADMIN)
    _col, _maj, class_id = _make_org()
    _make_student(class_id=class_id, name="李四")
    _make_student(class_id=class_id, name="李四")
    md.scan(rule_code="STUDENT_DUPLICATE_NAME_IN_CLASS", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    issue_id = int(_issues("STUDENT_DUPLICATE_NAME_IN_CLASS")[0]["issueId"])

    with pytest.raises(AppException):  # 没有期限
        md.except_issue(issue_id, reason="确认是两个同名学生", until="",
                        approved_by=approver_id, tenant_id=MAIN_TENANT_ID)
    with pytest.raises(AppException):  # 期限在过去
        md.except_issue(issue_id, reason="确认是两个同名学生",
                        until=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
                        approved_by=approver_id, tenant_id=MAIN_TENANT_ID)
    with pytest.raises(AppException):  # 没有审批人
        md.except_issue(issue_id, reason="确认是两个同名学生",
                        until=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                        approved_by=0, tenant_id=MAIN_TENANT_ID)

    ok = md.except_issue(issue_id, reason="核实确为两名同名学生，非重复建档",
                         until=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                         approved_by=approver_id, tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert ok["status"] == md.ISSUE_EXCEPTED
    assert ok["exceptionUntil"] and ok["exceptionReason"]


def test_t04b_p0_cannot_be_excepted(tenant_ctx):
    owner_id = _make_user("md_owner_org3")
    md.set_domain_owner(md.DOMAIN_ORG, owner_user_id=owner_id, reason="指定组织主数据责任人",
                        tenant_id=MAIN_TENANT_ID, user=ADMIN)
    _make_org(college_code="DUP777")
    _make_org(college_code="DUP777")
    md.scan(rule_code="ORG_DUPLICATE_CODE", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    issue_id = int(_issues("ORG_DUPLICATE_CODE")[0]["issueId"])

    with pytest.raises(AppException) as caught:
        md.except_issue(issue_id, reason="暂时不处理编码重复",
                        until=(datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d"),
                        approved_by=owner_id, tenant_id=MAIN_TENANT_ID)
    assert "P0" in caught.value.message


def test_t04c_expired_exception_reopens_on_next_scan(tenant_ctx):
    from sqlalchemy import select

    from app.models.master_data_governance import DataQualityIssue

    owner_id = _make_user("md_owner_student6")
    md.set_domain_owner(md.DOMAIN_STUDENT, owner_user_id=owner_id, reason="指定学生主档责任人",
                        tenant_id=MAIN_TENANT_ID, user=ADMIN)
    _col, _maj, class_id = _make_org()
    _make_student(class_id=class_id, name="王五")
    _make_student(class_id=class_id, name="王五")
    md.scan(rule_code="STUDENT_DUPLICATE_NAME_IN_CLASS", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    issue_id = int(_issues("STUDENT_DUPLICATE_NAME_IN_CLASS")[0]["issueId"])
    md.except_issue(issue_id, reason="本学期先不处理，下学期核对",
                    until=(datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
                    approved_by=owner_id, tenant_id=MAIN_TENANT_ID, user=ADMIN)

    with _session() as db:  # 把例外推到过期
        row = db.scalars(select(DataQualityIssue).where(
            DataQualityIssue.id == issue_id)).first()
        row.exception_until = datetime.now().replace(microsecond=0) - timedelta(minutes=1)
        db.commit()

    md.scan(rule_code="STUDENT_DUPLICATE_NAME_IN_CLASS", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert md.get_issue(issue_id, tenant_id=MAIN_TENANT_ID)["status"] == md.ISSUE_OPEN


# ── 治理表不复制主数据 + 跨租户 ─────────────────────────────────────────────
def test_governance_tables_do_not_copy_master_data(tenant_ctx):
    from app.models.master_data_governance import DataQualityIssue

    columns = {c.name for c in DataQualityIssue.__table__.columns}
    # 只允许记对象引用与证据，不许出现主数据本体字段
    for forbidden in ("real_name", "student_no", "id_card_encrypted", "phone_encrypted"):
        assert forbidden not in columns, f"治理表不得复制主数据字段：{forbidden}"
    assert {"object_type", "object_id", "evidence_json"} <= columns


def test_scan_is_tenant_isolated(tenant_ctx):
    from app.models import Tenant

    other = 8907
    with _session() as db:
        if db.get(Tenant, other) is None:
            db.add(Tenant(id=other, tenant_code="md-other", school_name="他校", status="ACTIVE"))
            db.commit()
    owner_id = _make_user("md_owner_student7")
    md.set_domain_owner(md.DOMAIN_STUDENT, owner_user_id=owner_id, reason="指定学生主档责任人",
                        tenant_id=MAIN_TENANT_ID, user=ADMIN)
    _make_student(class_id=None)
    md.scan(rule_code="STUDENT_MISSING_CLASS", tenant_id=MAIN_TENANT_ID, user=ADMIN)

    md.bootstrap_defaults(tenant_id=other)
    assert md.list_issues(tenant_id=other)["total"] == 0
    assert md.list_issues(tenant_id=MAIN_TENANT_ID)["total"] >= 1


def test_unknown_rule_and_version_conflict(tenant_ctx):
    owner_id = _make_user("md_owner_student8")
    md.set_domain_owner(md.DOMAIN_STUDENT, owner_user_id=owner_id, reason="指定学生主档责任人",
                        tenant_id=MAIN_TENANT_ID, user=ADMIN)
    with pytest.raises(AppException):
        md.scan(rule_code="NOT_A_RULE", tenant_id=MAIN_TENANT_ID, user=ADMIN)

    _make_student(class_id=None)
    md.scan(rule_code="STUDENT_MISSING_CLASS", tenant_id=MAIN_TENANT_ID, user=ADMIN)
    row = _issues("STUDENT_MISSING_CLASS")[0]
    stale = int(row["version"])
    md.assign_issue(int(row["issueId"]), owner_user_id=owner_id, reason="先指派一次抬版本",
                    tenant_id=MAIN_TENANT_ID, user=ADMIN)
    with pytest.raises(AppException) as caught:
        md.resolve_issue(int(row["issueId"]), note="拿旧版本提交处理结果",
                         expected_version=stale, tenant_id=MAIN_TENANT_ID, user=ADMIN)
    assert caught.value.code == "DATA_CONFLICT"


# ── 接口层 ───────────────────────────────────────────────────────────────────
def test_http_endpoints(client, auth_headers, tenant_ctx):
    owner_id = _make_user("md_http_owner")
    client.post("/api/v1/system/master-data/bootstrap", headers=auth_headers)

    owned = client.put(f"/api/v1/system/master-data/domains/{md.DOMAIN_STUDENT}/owner",
                       headers=auth_headers,
                       json={"ownerUserId": str(owner_id), "reason": "接口层指定责任人"}).json()
    assert owned["code"] == 0

    _make_student(class_id=None)
    scanned = client.post("/api/v1/system/master-data/scan", headers=auth_headers,
                          json={"ruleCode": "STUDENT_MISSING_CLASS"}).json()
    assert scanned["code"] == 0 and scanned["data"]["opened"] >= 1

    issues = client.get("/api/v1/system/master-data/issues", headers=auth_headers).json()
    assert issues["code"] == 0 and issues["data"]["total"] >= 1
    issue_id = issues["data"]["list"][0]["issueId"]

    verified = client.post(f"/api/v1/system/master-data/issues/{issue_id}/verify",
                           headers=auth_headers).json()
    assert verified["code"] == 0
    assert verified["data"]["verifyResult"] in ("GONE", "STILL_PRESENT")

    domains = client.get("/api/v1/system/master-data/domains", headers=auth_headers).json()
    assert domains["code"] == 0 and domains["data"]["total"] >= 3
    rules = client.get("/api/v1/system/master-data/rules", headers=auth_headers).json()
    assert rules["code"] == 0 and rules["data"]["total"] >= 5
    assert all(r["executorAvailable"] for r in rules["data"]["list"]), "登记的扫描器必须真实存在"
