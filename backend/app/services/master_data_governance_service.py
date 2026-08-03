"""SYS-17：主数据责任与数据质量。

三条硬规矩
──────────
1. **治理表只存问题和证据**，主数据永远留在业务权威表里。合并预览列引用、问题记
   object_id，但绝不把学生/组织抄一份进 t_data_* 。
2. **P0 必须有责任人和 SLA**：没有责任人的域不许启用 P0 规则；P0 规则必须填 SLA
   小时数。否则"最高优先级问题"会变成没人认领、没有期限的摆设。
3. **修复要靠复扫证明**，不是靠处理人自己说改好了：``verify_issue`` 重新执行该规则，
   问题还在就打回 OPEN 并记 STILL_PRESENT。

扫描器都是真查业务表，其中两个直接复用既有实现，不重写一遍：
组织编码重复用 ``org_master_service.find_duplicate_org_codes``，
班级缺辅导员用 SYS-05 的 ``business_relation_registry.inspect_relation``。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy import func, select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.master_data_governance import (ISSUE_ASSIGNED, ISSUE_EXCEPTED,
                                               ISSUE_OPEN, ISSUE_RESOLVED,
                                               ISSUE_VERIFIED, MERGE_PREVIEW,
                                               SEVERITY_LEVELS, SEVERITY_P0,
                                               DataDomain, DataOwner,
                                               DataQualityIssue,
                                               DataQualityRule,
                                               MasterMergeEvent)

DOMAIN_STUDENT = "STUDENT"
DOMAIN_ORG = "ORG"
DOMAIN_ACCOUNT = "ACCOUNT"

DEFAULT_DOMAINS = (
    {"domainCode": DOMAIN_STUDENT, "domainName": "学生主档", "ownerModule": "studentAffairs",
     "authoritativeTable": "t_student_profile",
     "description": "学籍主体，全平台唯一学生身份；系统管理不代业务部门确认学生事实。"},
    {"domainCode": DOMAIN_ORG, "domainName": "组织主数据", "ownerModule": "systemAdmin",
     "authoritativeTable": "t_college / t_major / t_school_class",
     "description": "学院、专业、班级；四大业务中心共用。"},
    {"domainCode": DOMAIN_ACCOUNT, "domainName": "账号与身份绑定", "ownerModule": "systemAdmin",
     "authoritativeTable": "t_user / t_student_account_link",
     "description": "登录账号与学籍主体的稳定绑定。"},
)

DEFAULT_RULES = (
    {"ruleCode": "ORG_DUPLICATE_CODE", "domainCode": DOMAIN_ORG, "ruleName": "组织编码重复",
     "ruleType": "DUPLICATE", "severity": SEVERITY_P0, "executorKey": "org_duplicate_code",
     "slaHours": 48},
    {"ruleCode": "CLASS_MISSING_COUNSELOR", "domainCode": DOMAIN_ORG, "ruleName": "班级缺辅导员",
     "ruleType": "MISSING", "severity": "P1", "executorKey": "class_missing_counselor",
     "slaHours": 168},
    {"ruleCode": "STUDENT_MISSING_CLASS", "domainCode": DOMAIN_STUDENT, "ruleName": "学生未挂班级",
     "ruleType": "MISSING", "severity": "P1", "executorKey": "student_missing_class",
     "slaHours": 168},
    {"ruleCode": "STUDENT_DUPLICATE_NAME_IN_CLASS", "domainCode": DOMAIN_STUDENT,
     "ruleName": "同班同名疑似重复建档", "ruleType": "DUPLICATE", "severity": "P2",
     "executorKey": "student_duplicate_name_in_class", "slaHours": None},
    {"ruleCode": "ACCOUNT_BROKEN_BINDING", "domainCode": DOMAIN_ACCOUNT,
     "ruleName": "账号绑定指向不存在的学籍", "ruleType": "BROKEN_LINK", "severity": SEVERITY_P0,
     "executorKey": "account_broken_binding", "slaHours": 24},
)


def _tid(tenant_id: int | None = None) -> int:
    return int(tenant_id if tenant_id is not None else (current_tenant_id() or 0))


def _now() -> datetime:
    # MySQL DATETIME 无微秒位，统一截断到秒，避免"刚写入的记录看起来比现在晚"
    return datetime.now().replace(microsecond=0)


def _actor(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or "").replace("db-", "")
    return int(raw) if raw.isdigit() else None


def _digest(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


# ── 扫描器：全部真查业务权威表 ───────────────────────────────────────────────
def _scan_org_duplicate_code(db, tenant_id: int) -> list[dict]:
    from app.services.org_master_service import find_duplicate_org_codes

    report = find_duplicate_org_codes(tenant_id)
    out: list[dict] = []
    for kind in ("college", "major", "class"):
        for row in report.get(kind) or []:
            out.append({
                "issueKey": f"ORG_DUPLICATE_CODE:{kind}:{row['code']}",
                "objectType": kind.upper(), "objectId": str(row["code"]),
                "summary": f"{kind} 编码 {row['code']} 重复 {row['count']} 次",
                "evidence": {"kind": kind, "code": row["code"], "count": row["count"]},
            })
    return out


def _scan_class_missing_counselor(db, tenant_id: int) -> list[dict]:
    from app.services import business_relation_registry as registry

    report = registry.inspect_relation("COUNSELOR_CLASS", tenant_id=tenant_id)
    out: list[dict] = []
    for issue in report.get("issues") or []:
        if issue["code"] != registry.ISSUE_MISSING_SUBJECT:
            continue
        for sample in issue.get("samples") or []:
            out.append({
                "issueKey": f"CLASS_MISSING_COUNSELOR:{sample['id']}",
                "objectType": "CLASS", "objectId": str(sample["id"]),
                "summary": f"班级 {sample['id']} 没有辅导员，辅导员数据范围解析不出任何人",
                "evidence": {"relationType": "COUNSELOR_CLASS", "classId": sample["id"]},
            })
    return out


def _scan_student_missing_class(db, tenant_id: int) -> list[dict]:
    from app.models import StudentProfile

    rows = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
        StudentProfile.class_id.is_(None)).limit(500)).all()
    return [{
        "issueKey": f"STUDENT_MISSING_CLASS:{r.id}",
        "objectType": "STUDENT", "objectId": str(r.id),
        "summary": f"学生 {r.student_no or r.id} 未挂班级，班级范围与辅导员均无法覆盖",
        "evidence": {"studentId": str(r.id), "studentNo": r.student_no},
    } for r in rows]


def _scan_student_duplicate_name_in_class(db, tenant_id: int) -> list[dict]:
    from app.models import StudentProfile

    rows = db.execute(
        select(StudentProfile.class_id, StudentProfile.real_name, func.count())
        .where(StudentProfile.tenant_id == tenant_id,
               StudentProfile.is_deleted.is_(False),
               StudentProfile.class_id.is_not(None))
        .group_by(StudentProfile.class_id, StudentProfile.real_name)
        .having(func.count() > 1)).all()
    return [{
        "issueKey": f"STUDENT_DUPLICATE_NAME_IN_CLASS:{r[0]}:{r[1]}",
        "objectType": "CLASS", "objectId": str(r[0]),
        "summary": f"班级 {r[0]} 内有 {int(r[2])} 名同名学生「{r[1]}」，请人工核对是否重复建档",
        "evidence": {"classId": str(r[0]), "realName": r[1], "count": int(r[2])},
    } for r in rows]


def _scan_account_broken_binding(db, tenant_id: int) -> list[dict]:
    from app.models import StudentAccountLink, StudentProfile

    links = db.scalars(select(StudentAccountLink).where(
        StudentAccountLink.tenant_id == tenant_id,
        StudentAccountLink.link_status == "ACTIVE",
        StudentAccountLink.is_deleted.is_(False)).limit(1000)).all()
    if not links:
        return []
    alive = {int(r) for r in db.scalars(select(StudentProfile.id).where(
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False))).all()}
    return [{
        "issueKey": f"ACCOUNT_BROKEN_BINDING:{link.id}",
        "objectType": "ACCOUNT", "objectId": str(link.user_id),
        "summary": f"账号 {link.user_id} 的绑定指向不存在的学籍 {link.student_id}",
        "evidence": {"linkId": str(link.id), "userId": str(link.user_id),
                     "studentId": str(link.student_id)},
    } for link in links if int(link.student_id) not in alive]


EXECUTORS: dict[str, Callable] = {
    "org_duplicate_code": _scan_org_duplicate_code,
    "class_missing_counselor": _scan_class_missing_counselor,
    "student_missing_class": _scan_student_missing_class,
    "student_duplicate_name_in_class": _scan_student_duplicate_name_in_class,
    "account_broken_binding": _scan_account_broken_binding,
}


# ── 目录与责任人 ─────────────────────────────────────────────────────────────
def bootstrap_defaults(*, tenant_id: int | None = None) -> dict:
    """把内置数据域与规则装进本校。已存在的只跳过，不覆盖学校自己的调整。"""
    tid = _tid(tenant_id)
    now = _now()
    db = get_sessionmaker()()
    try:
        created = {"domains": 0, "rules": 0}
        existing_domains = {d.domain_code for d in db.scalars(select(DataDomain).where(
            DataDomain.tenant_id == tid, DataDomain.is_deleted.is_(False)))}
        for item in DEFAULT_DOMAINS:
            if item["domainCode"] in existing_domains:
                continue
            db.add(DataDomain(tenant_id=tid, domain_code=item["domainCode"],
                              domain_name=item["domainName"], owner_module=item["ownerModule"],
                              authoritative_table=item["authoritativeTable"],
                              description=item["description"], status="ACTIVE"))
            created["domains"] += 1
        existing_rules = {r.rule_code for r in db.scalars(select(DataQualityRule).where(
            DataQualityRule.tenant_id == tid, DataQualityRule.is_deleted.is_(False)))}
        for item in DEFAULT_RULES:
            if item["ruleCode"] in existing_rules:
                continue
            db.add(DataQualityRule(
                tenant_id=tid, domain_code=item["domainCode"], rule_code=item["ruleCode"],
                rule_name=item["ruleName"], rule_type=item["ruleType"],
                severity=item["severity"], executor_key=item["executorKey"],
                sla_hours=item["slaHours"], status="ACTIVE"))
            created["rules"] += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return created


def _primary_owner(db, tenant_id: int, domain_code: str, *, now: datetime) -> DataOwner | None:
    rows = db.scalars(select(DataOwner).where(
        DataOwner.tenant_id == tenant_id, DataOwner.domain_code == domain_code,
        DataOwner.status == "ACTIVE", DataOwner.is_deleted.is_(False),
        DataOwner.effective_at <= now)).all()
    live = [r for r in rows if r.expires_at is None or r.expires_at > now]
    if not live:
        return None
    return next((r for r in live if r.is_primary), live[0])


def set_domain_owner(domain_code: str, *, owner_user_id: int, reason: str,
                     owner_role_code: str | None = None, is_primary: bool = True,
                     expires_at: str | None = None, tenant_id: int | None = None,
                     user: dict | None = None) -> dict:
    if len(str(reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "指定责任人的原因不少于 5 个字")
    tid = _tid(tenant_id)
    now = _now()
    parsed_expires = _parse_dt(expires_at, "expiresAt")
    db = get_sessionmaker()()
    try:
        domain = db.scalars(select(DataDomain).where(
            DataDomain.tenant_id == tid, DataDomain.domain_code == domain_code,
            DataDomain.is_deleted.is_(False))).first()
        if domain is None:
            raise AppException("DATA_NOT_FOUND", f"数据域不存在：{domain_code}")
        row = db.scalars(select(DataOwner).where(
            DataOwner.tenant_id == tid, DataOwner.domain_code == domain_code,
            DataOwner.owner_user_id == int(owner_user_id),
            DataOwner.is_deleted.is_(False))).first()
        if row is None:
            row = DataOwner(tenant_id=tid, domain_code=domain_code,
                            owner_user_id=int(owner_user_id), owner_role_code=owner_role_code,
                            is_primary=bool(is_primary), effective_at=now,
                            expires_at=parsed_expires, status="ACTIVE",
                            created_by=_actor(user), updated_by=_actor(user))
            db.add(row)
        else:
            row.owner_role_code = owner_role_code
            row.is_primary = bool(is_primary)
            row.expires_at = parsed_expires
            row.status = "ACTIVE"
            row.updated_by = _actor(user)
            row.version = int(row.version or 0) + 1
        if is_primary:
            for other in db.scalars(select(DataOwner).where(
                    DataOwner.tenant_id == tid, DataOwner.domain_code == domain_code,
                    DataOwner.owner_user_id != int(owner_user_id),
                    DataOwner.is_deleted.is_(False))).all():
                other.is_primary = False
        db.commit()
    except AppException:
        db.rollback()
        raise
    finally:
        db.close()

    from app.services import audit_log

    audit_log.record("MASTER_DATA_OWNER_SET", f"data-domain:{domain_code}",
                     detail={"reason": reason, "ownerUserId": str(owner_user_id),
                             "moduleCode": "systemAdmin"})
    return list_domains(tenant_id=tid)


def _parse_dt(value: Any, field: str) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).replace(microsecond=0)
        except ValueError:
            continue
    raise AppException("VALIDATION_ERROR", f"{field} 格式应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS")


def list_domains(*, tenant_id: int | None = None) -> dict:
    tid = _tid(tenant_id)
    now = _now()
    db = get_sessionmaker()()
    try:
        domains = db.scalars(select(DataDomain).where(
            DataDomain.tenant_id == tid, DataDomain.is_deleted.is_(False)
        ).order_by(DataDomain.domain_code)).all()
        rules = db.scalars(select(DataQualityRule).where(
            DataQualityRule.tenant_id == tid, DataQualityRule.is_deleted.is_(False))).all()
        issues = db.scalars(select(DataQualityIssue).where(
            DataQualityIssue.tenant_id == tid, DataQualityIssue.is_deleted.is_(False))).all()
        out = []
        for domain in domains:
            owner = _primary_owner(db, tid, domain.domain_code, now=now)
            domain_issues = [i for i in issues if i.domain_code == domain.domain_code]
            open_issues = [i for i in domain_issues
                           if i.status in (ISSUE_OPEN, ISSUE_ASSIGNED, ISSUE_RESOLVED)]
            overdue = [i for i in open_issues if i.due_at is not None and i.due_at < now]
            domain_rules = [r for r in rules if r.domain_code == domain.domain_code]
            out.append({
                "domainCode": domain.domain_code, "domainName": domain.domain_name,
                "ownerModule": domain.owner_module,
                "authoritativeTable": domain.authoritative_table,
                "description": domain.description or "",
                "ownerUserId": str(owner.owner_user_id) if owner else "",
                "hasOwner": owner is not None,
                "ruleCount": len(domain_rules),
                "p0RuleCount": sum(1 for r in domain_rules if r.severity == SEVERITY_P0),
                "openIssues": len(open_issues),
                "overdueIssues": len(overdue),
                "qualityScore": _quality_score(domain_issues, now),
            })
        return {"list": out, "total": len(out),
                "domainsWithoutOwner": [d["domainCode"] for d in out if not d["hasOwner"]]}
    finally:
        db.close()


def _quality_score(issues: list, now: datetime) -> int:
    """扣分制：P0 扣 20、P1 扣 8、P2 扣 3，逾期再翻倍。没有问题就是 100。"""
    weights = {SEVERITY_P0: 20, "P1": 8, "P2": 3}
    score = 100
    for issue in issues:
        if issue.status in (ISSUE_VERIFIED, ISSUE_EXCEPTED):
            continue
        penalty = weights.get(issue.severity, 3)
        if issue.due_at is not None and issue.due_at < now:
            penalty *= 2
        score -= penalty
    return max(0, score)


def list_rules(*, tenant_id: int | None = None, domain_code: str = "") -> dict:
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        stmt = select(DataQualityRule).where(
            DataQualityRule.tenant_id == tid, DataQualityRule.is_deleted.is_(False))
        if domain_code:
            stmt = stmt.where(DataQualityRule.domain_code == domain_code)
        rows = db.scalars(stmt.order_by(DataQualityRule.rule_code)).all()
        now = _now()
        return {"list": [{
            "ruleCode": r.rule_code, "ruleName": r.rule_name, "domainCode": r.domain_code,
            "ruleType": r.rule_type, "severity": r.severity, "executorKey": r.executor_key,
            "slaHours": r.sla_hours, "status": r.status,
            "executorAvailable": r.executor_key in EXECUTORS,
            "ownerReady": _primary_owner(db, tid, r.domain_code, now=now) is not None,
        } for r in rows], "total": len(rows)}
    finally:
        db.close()


def _assert_p0_ready(db, tenant_id: int, rule: DataQualityRule, *, now: datetime) -> None:
    """P0 的两条硬要求：域有责任人、规则有 SLA。缺一条就不许它进入运行。"""
    if rule.severity != SEVERITY_P0:
        return
    if not rule.sla_hours:
        raise AppException("VALIDATION_ERROR",
                           f"P0 规则必须设置 SLA 小时数：{rule.rule_code}")
    if _primary_owner(db, tenant_id, rule.domain_code, now=now) is None:
        raise AppException("VALIDATION_ERROR",
                           f"数据域 {rule.domain_code} 尚未指定责任人，不能运行 P0 规则"
                           f"（{rule.rule_code}）")


# ── 扫描 ─────────────────────────────────────────────────────────────────────
def scan(*, tenant_id: int | None = None, rule_code: str = "",
         user: dict | None = None) -> dict:
    """执行质量规则。同一问题重复扫描只更新 last_seen；扫不到的已修复问题自动核销。"""
    tid = _tid(tenant_id)
    now = _now()
    batch_no = f"SCAN-{now:%Y%m%d%H%M%S}"
    db = get_sessionmaker()()
    try:
        stmt = select(DataQualityRule).where(
            DataQualityRule.tenant_id == tid, DataQualityRule.status == "ACTIVE",
            DataQualityRule.is_deleted.is_(False))
        if rule_code:
            stmt = stmt.where(DataQualityRule.rule_code == rule_code)
        rules = db.scalars(stmt).all()
        if rule_code and not rules:
            raise AppException("DATA_NOT_FOUND", f"质量规则不存在或未启用：{rule_code}")

        existing = {i.issue_key: i for i in db.scalars(select(DataQualityIssue).where(
            DataQualityIssue.tenant_id == tid, DataQualityIssue.is_deleted.is_(False)))}
        opened, updated, cleared, skipped = 0, 0, 0, []
        seen_keys: set[str] = set()

        for rule in rules:
            executor = EXECUTORS.get(rule.executor_key)
            if executor is None:
                skipped.append({"ruleCode": rule.rule_code,
                                "reason": f"扫描器不存在：{rule.executor_key}"})
                continue
            _assert_p0_ready(db, tid, rule, now=now)
            owner = _primary_owner(db, tid, rule.domain_code, now=now)
            findings = executor(db, tid)
            for finding in findings:
                key = finding["issueKey"]
                seen_keys.add(key)
                due = now + timedelta(hours=int(rule.sla_hours)) if rule.sla_hours else None
                row = existing.get(key)
                if row is None:
                    db.add(DataQualityIssue(
                        tenant_id=tid, domain_code=rule.domain_code, rule_code=rule.rule_code,
                        issue_key=key, severity=rule.severity, status=ISSUE_OPEN,
                        object_type=finding.get("objectType"), object_id=finding.get("objectId"),
                        summary=finding["summary"], evidence_json=finding.get("evidence") or {},
                        owner_user_id=owner.owner_user_id if owner else None,
                        due_at=due, first_seen_at=now, last_seen_at=now,
                        scan_batch_no=batch_no, created_by=_actor(user), updated_by=_actor(user)))
                    opened += 1
                else:
                    row.last_seen_at = now
                    row.summary = finding["summary"]
                    row.evidence_json = finding.get("evidence") or {}
                    row.scan_batch_no = batch_no
                    row.severity = rule.severity
                    if row.owner_user_id is None and owner is not None:
                        row.owner_user_id = owner.owner_user_id
                    if row.due_at is None and due is not None:
                        row.due_at = due
                    # 例外到期未处理 → 打回 OPEN；已判 RESOLVED 但问题还在 → 也打回
                    if row.status == ISSUE_EXCEPTED and row.exception_until is not None \
                            and row.exception_until <= now:
                        row.status = ISSUE_OPEN
                        row.exception_until = None
                    elif row.status == ISSUE_RESOLVED:
                        row.status = ISSUE_OPEN
                        row.verify_result = "STILL_PRESENT"
                    row.version = int(row.version or 0) + 1
                    updated += 1

        # 本轮规则范围内、这次没扫到的问题＝已消除
        scoped_rules = {r.rule_code for r in rules}
        for key, row in existing.items():
            if row.rule_code not in scoped_rules or key in seen_keys:
                continue
            if row.status in (ISSUE_VERIFIED,):
                continue
            row.status = ISSUE_VERIFIED
            row.verified_at = now
            row.verify_result = "GONE"
            row.version = int(row.version or 0) + 1
            cleared += 1
        db.commit()
    except AppException:
        db.rollback()
        raise
    finally:
        db.close()

    from app.services import audit_log

    audit_log.record("MASTER_DATA_SCAN", f"scan:{batch_no}",
                     detail={"opened": opened, "updated": updated, "cleared": cleared,
                             "skipped": skipped, "moduleCode": "systemAdmin"})
    return {"batchNo": batch_no, "opened": opened, "updated": updated,
            "cleared": cleared, "skippedRules": skipped}


# ── 问题闭环 ─────────────────────────────────────────────────────────────────
def _load_issue(db, tenant_id: int, issue_id: int) -> DataQualityIssue:
    row = db.scalars(select(DataQualityIssue).where(
        DataQualityIssue.id == int(issue_id), DataQualityIssue.tenant_id == tenant_id,
        DataQualityIssue.is_deleted.is_(False))).first()
    if row is None:
        raise AppException("DATA_NOT_FOUND", "数据质量问题不存在")
    return row


def _issue_dto(row, *, now: datetime) -> dict:
    return {
        "issueId": str(row.id), "issueKey": row.issue_key,
        "domainCode": row.domain_code, "ruleCode": row.rule_code,
        "severity": row.severity, "status": row.status,
        "objectType": row.object_type or "", "objectId": row.object_id or "",
        "summary": row.summary, "evidence": row.evidence_json or {},
        "ownerUserId": str(row.owner_user_id or ""),
        "dueAt": str(row.due_at or "")[:19],
        "overdue": bool(row.due_at is not None and row.due_at < now
                        and row.status in (ISSUE_OPEN, ISSUE_ASSIGNED, ISSUE_RESOLVED)),
        "firstSeenAt": str(row.first_seen_at or "")[:19],
        "lastSeenAt": str(row.last_seen_at or "")[:19],
        "resolveNote": row.resolve_note or "",
        "verifyResult": row.verify_result or "",
        "exceptionUntil": str(row.exception_until or "")[:19],
        "exceptionReason": row.exception_reason or "",
        "version": int(row.version or 0),
    }


def list_issues(*, tenant_id: int | None = None, domain_code: str = "", status: str = "",
                severity: str = "", page: int = 1, page_size: int = 50) -> dict:
    tid = _tid(tenant_id)
    now = _now()
    db = get_sessionmaker()()
    try:
        stmt = select(DataQualityIssue).where(
            DataQualityIssue.tenant_id == tid, DataQualityIssue.is_deleted.is_(False))
        if domain_code:
            stmt = stmt.where(DataQualityIssue.domain_code == domain_code)
        if status:
            stmt = stmt.where(DataQualityIssue.status == status)
        if severity:
            stmt = stmt.where(DataQualityIssue.severity == severity)
        rows = db.scalars(stmt.order_by(DataQualityIssue.severity,
                                        DataQualityIssue.id.desc())).all()
        items = [_issue_dto(r, now=now) for r in rows]
    finally:
        db.close()
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 50)))
    start = (page - 1) * page_size
    return {
        "list": items[start:start + page_size], "total": len(items),
        "page": page, "pageSize": page_size,
        "summary": {
            "p0Open": sum(1 for i in items
                          if i["severity"] == SEVERITY_P0 and i["status"] in (ISSUE_OPEN, ISSUE_ASSIGNED)),
            "overdue": sum(1 for i in items if i["overdue"]),
            "p0WithoutOwner": sum(1 for i in items
                                  if i["severity"] == SEVERITY_P0 and not i["ownerUserId"]),
            "excepted": sum(1 for i in items if i["status"] == ISSUE_EXCEPTED),
        },
    }


def assign_issue(issue_id: int, *, owner_user_id: int, reason: str,
                 expected_version: int | None = None, tenant_id: int | None = None,
                 user: dict | None = None) -> dict:
    if len(str(reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "指派原因不少于 5 个字")
    tid = _tid(tenant_id)
    now = _now()
    db = get_sessionmaker()()
    try:
        row = _load_issue(db, tid, issue_id)
        _check_version(row, expected_version)
        if row.status in (ISSUE_VERIFIED,):
            raise AppException("VALIDATION_ERROR", "问题已核销，无需指派")
        row.owner_user_id = int(owner_user_id)
        row.status = ISSUE_ASSIGNED
        row.assigned_at = now
        row.version = int(row.version or 0) + 1
        db.commit()
    except AppException:
        db.rollback()
        raise
    finally:
        db.close()
    _audit("MASTER_DATA_ISSUE_ASSIGN", issue_id, {"reason": reason,
                                                  "ownerUserId": str(owner_user_id)})
    return get_issue(issue_id, tenant_id=tid)


def resolve_issue(issue_id: int, *, note: str, expected_version: int | None = None,
                  tenant_id: int | None = None, user: dict | None = None) -> dict:
    """处理人声明已修复。**此时还不算完**，必须由复扫证明问题真的消失。"""
    if len(str(note or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "处理说明不少于 5 个字")
    tid = _tid(tenant_id)
    now = _now()
    db = get_sessionmaker()()
    try:
        row = _load_issue(db, tid, issue_id)
        _check_version(row, expected_version)
        if row.status == ISSUE_VERIFIED:
            raise AppException("VALIDATION_ERROR", "问题已核销")
        row.status = ISSUE_RESOLVED
        row.resolved_at = now
        row.resolved_by = _actor(user)
        row.resolve_note = note
        row.verify_result = None
        row.version = int(row.version or 0) + 1
        db.commit()
    except AppException:
        db.rollback()
        raise
    finally:
        db.close()
    _audit("MASTER_DATA_ISSUE_RESOLVE", issue_id, {"note": note})
    return get_issue(issue_id, tenant_id=tid)


def verify_issue(issue_id: int, *, tenant_id: int | None = None,
                 user: dict | None = None) -> dict:
    """复扫验证：重新跑这条规则，问题还在就打回 OPEN，不接受"我改好了"的口头结论。"""
    tid = _tid(tenant_id)
    now = _now()
    db = get_sessionmaker()()
    try:
        row = _load_issue(db, tid, issue_id)
        rule = db.scalars(select(DataQualityRule).where(
            DataQualityRule.tenant_id == tid, DataQualityRule.rule_code == row.rule_code,
            DataQualityRule.is_deleted.is_(False))).first()
        if rule is None:
            raise AppException("DATA_NOT_FOUND", f"质量规则已不存在：{row.rule_code}")
        executor = EXECUTORS.get(rule.executor_key)
        if executor is None:
            raise AppException("SERVER_ERROR",
                               f"扫描器不存在，无法验证：{rule.executor_key}", http_status=503)
        still_there = any(f["issueKey"] == row.issue_key for f in executor(db, tid))
        row.verified_at = now
        row.verified_by = _actor(user)
        if still_there:
            row.status = ISSUE_OPEN
            row.verify_result = "STILL_PRESENT"
        else:
            row.status = ISSUE_VERIFIED
            row.verify_result = "GONE"
        row.version = int(row.version or 0) + 1
        db.commit()
        result = row.verify_result
    except AppException:
        db.rollback()
        raise
    finally:
        db.close()
    _audit("MASTER_DATA_ISSUE_VERIFY", issue_id, {"verifyResult": result})
    return get_issue(issue_id, tenant_id=tid)


def except_issue(issue_id: int, *, reason: str, until: str, approved_by: int,
                 expected_version: int | None = None, tenant_id: int | None = None,
                 user: dict | None = None) -> dict:
    """例外必须同时有期限和审批人；到期后下一次扫描自动打回 OPEN。"""
    if len(str(reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "例外理由不少于 5 个字")
    deadline = _parse_dt(until, "until")
    if deadline is None:
        raise AppException("VALIDATION_ERROR", "例外必须设置到期时间")
    now = _now()
    if deadline <= now:
        raise AppException("VALIDATION_ERROR", "例外到期时间必须晚于当前时间")
    if not str(approved_by or "").strip().isdigit():
        raise AppException("VALIDATION_ERROR", "例外必须记录审批人")
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        row = _load_issue(db, tid, issue_id)
        _check_version(row, expected_version)
        if row.severity == SEVERITY_P0:
            raise AppException("VALIDATION_ERROR", "P0 问题不允许走例外，必须真实修复")
        row.status = ISSUE_EXCEPTED
        row.exception_until = deadline
        row.exception_reason = reason
        row.exception_approved_by = int(approved_by)
        row.version = int(row.version or 0) + 1
        db.commit()
    except AppException:
        db.rollback()
        raise
    finally:
        db.close()
    _audit("MASTER_DATA_ISSUE_EXCEPT", issue_id,
           {"reason": reason, "until": str(deadline), "approvedBy": str(approved_by)})
    return get_issue(issue_id, tenant_id=tid)


def get_issue(issue_id: int, *, tenant_id: int | None = None) -> dict:
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        return _issue_dto(_load_issue(db, tid, issue_id), now=_now())
    finally:
        db.close()


def _check_version(row, expected_version) -> None:
    if expected_version in (None, ""):
        return
    if int(expected_version) != int(row.version or 0):
        raise AppException("DATA_CONFLICT", "该问题已被他人更新，请刷新后重试")


def _audit(action: str, issue_id: int, detail: dict) -> None:
    from app.services import audit_log

    audit_log.record(action, f"data-quality-issue:{issue_id}",
                     detail={**detail, "moduleCode": "systemAdmin"})


# ── 合并预览 ─────────────────────────────────────────────────────────────────
# 被并对象的引用分布：真表真字段，合并前必须一条不漏地摆出来
MERGE_REFERENCES = {
    DOMAIN_STUDENT: [
        ("app.models.StudentAccountLink", "student_id", "账号绑定"),
        ("app.models.StudentContact", "student_id", "联系方式"),
        ("app.models.GraduationStudent", "student_id", "毕设台账"),
        ("app.models.InternshipRecord", "student_id", "实习记录"),
    ],
    DOMAIN_ORG: [
        ("app.models.StudentProfile", "class_id", "学生挂班"),
        ("app.models.SchoolClass", "major_id", "班级挂专业"),
        ("app.models.Major", "college_id", "专业挂学院"),
    ],
}


def merge_preview(domain_code: str, *, primary_object_id: str, merged_object_id: str,
                  reason: str, tenant_id: int | None = None,
                  user: dict | None = None) -> dict:
    """只出预览与引用清单，绝不自动执行合并。高风险主数据不允许一键合并。"""
    import importlib

    if str(primary_object_id) == str(merged_object_id):
        raise AppException("VALIDATION_ERROR", "保留方与被并方不能是同一个对象")
    if len(str(reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "合并原因不少于 5 个字")
    refs_spec = MERGE_REFERENCES.get(domain_code)
    if refs_spec is None:
        raise AppException("VALIDATION_ERROR", f"该数据域暂不支持合并预览：{domain_code}")
    tid = _tid(tenant_id)
    now = _now()

    references: list[dict] = []
    unavailable: list[dict] = []
    db = get_sessionmaker()()
    try:
        for dotted, field, label in refs_spec:
            module_name, _, cls_name = dotted.rpartition(".")
            try:
                model = getattr(importlib.import_module(module_name), cls_name)
                column = getattr(model, field)
            except Exception as exc:  # noqa: BLE001
                unavailable.append({"table": dotted, "field": field, "label": label,
                                    "reason": f"模型或字段不可用：{exc}"})
                continue
            count = int(db.scalar(select(func.count()).select_from(model).where(
                model.tenant_id == tid, model.is_deleted.is_(False),
                column == merged_object_id)) or 0)
            references.append({"table": getattr(model, "__tablename__", dotted),
                               "field": field, "label": label, "count": count})
        payload = {"domainCode": domain_code, "primaryObjectId": str(primary_object_id),
                   "mergedObjectId": str(merged_object_id), "references": references,
                   "unavailable": unavailable}
        preview_hash = _digest(payload)
        event = MasterMergeEvent(
            tenant_id=tid, domain_code=domain_code,
            primary_object_id=str(primary_object_id), merged_object_id=str(merged_object_id),
            preview_hash=preview_hash, references_json=payload, status=MERGE_PREVIEW,
            reason=reason, created_by=_actor(user), updated_by=_actor(user))
        db.add(event)
        db.commit()
        event_id = int(event.id)
    except AppException:
        db.rollback()
        raise
    finally:
        db.close()

    from app.services import audit_log

    audit_log.record("MASTER_DATA_MERGE_PREVIEW", f"data-domain:{domain_code}",
                     detail={"reason": reason, "primaryObjectId": str(primary_object_id),
                             "mergedObjectId": str(merged_object_id),
                             "previewHash": preview_hash, "moduleCode": "systemAdmin"})
    return {
        "mergeEventId": str(event_id), "previewHash": preview_hash,
        "domainCode": domain_code, "primaryObjectId": str(primary_object_id),
        "mergedObjectId": str(merged_object_id),
        "references": references, "unavailable": unavailable,
        "totalReferences": sum(r["count"] for r in references),
        "status": MERGE_PREVIEW,
        "createdAt": str(now)[:19],
        "note": ("系统管理只出预览与引用清单，合并动作必须由数据域责任人在业务模块执行；"
                 "本页不代业务部门确认学生、成绩、企业等业务事实。"),
        "autoMergeAllowed": False,
    }


def list_merge_events(*, tenant_id: int | None = None, domain_code: str = "") -> dict:
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        stmt = select(MasterMergeEvent).where(
            MasterMergeEvent.tenant_id == tid, MasterMergeEvent.is_deleted.is_(False))
        if domain_code:
            stmt = stmt.where(MasterMergeEvent.domain_code == domain_code)
        rows = db.scalars(stmt.order_by(MasterMergeEvent.id.desc())).all()
        return {"list": [{
            "mergeEventId": str(r.id), "domainCode": r.domain_code,
            "primaryObjectId": r.primary_object_id, "mergedObjectId": r.merged_object_id,
            "previewHash": r.preview_hash, "status": r.status, "reason": r.reason or "",
            "totalReferences": sum(x["count"] for x in
                                   ((r.references_json or {}).get("references") or [])),
            "createdAt": str(r.created_at or "")[:19],
        } for r in rows], "total": len(rows)}
    finally:
        db.close()
