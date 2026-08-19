"""包 10：资助金额权威化运行时收口。

保持既有 /student-affairs/funding/* URL 与 service 调用兼容：
- 客户端 amount 在进入旧申请服务前被剥离；
- 项目标准金额是默认批准规则；
- 人工调整必须独立申请、说明原因、由不同人员复核；
- 公示确认时把最终规则金额放入同一事务，数据库触发器完成名额/金额原子占用。
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any

from sqlalchemy import inspect, select, text

from app.core.exceptions import AppException, check_version
from app.services import affairs_funding_service as legacy
from app.services.db_service import _tid, session

_ALLOWED_ROLES = {"SCHOOL_ADMIN", "STUDENT_AFFAIRS_ADMIN", "FUNDING_TEACHER"}
_INSTALLED = False
_ORIGINALS: dict[str, Any] = {}


def _uid(user) -> int:
    raw = str((user or {}).get("userId") or (user or {}).get("id") or "").removeprefix("db-")
    return int(raw) if raw.isdigit() else 0


def _user_name(user) -> str:
    return str((user or {}).get("realName") or (user or {}).get("name") or (user or {}).get("loginName") or "系统")


def _roles(user) -> set[str]:
    values = {
        str((user or {}).get("currentRoleCode") or "").upper(),
        str((user or {}).get("roleCode") or "").upper(),
    }
    for key in ("roleCodes", "roles"):
        raw = (user or {}).get(key) or []
        if isinstance(raw, str):
            raw = [item.strip() for item in raw.split(",")]
        for item in raw:
            if isinstance(item, dict):
                item = item.get("roleCode") or item.get("code")
            values.add(str(item or "").upper())
    return {item for item in values if item}


def _permissions(user) -> set[str]:
    raw = (user or {}).get("permissions") or (user or {}).get("permissionCodes") or []
    if isinstance(raw, str):
        raw = [item.strip() for item in raw.split(",")]
    return {str(item or "") for item in raw if item}


def _require_amount_role(user) -> None:
    permissions = _permissions(user)
    if (_roles(user) & _ALLOWED_ROLES) or {
        "studentAffairs.funding.approve",
        "studentAffairs.funding.publicity.manage",
    } & permissions:
        return
    raise AppException("NO_PERMISSION", "仅持有资助审批权限的人员可调整批准金额")


def _money(value, field="金额") -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", f"{field}格式不正确") from exc
    if amount <= 0:
        raise AppException("VALIDATION_ERROR", f"{field}必须大于 0")
    return amount.quantize(Decimal("0.01"))


def _body_without_client_amount(body):
    if hasattr(body, "model_copy"):
        return body.model_copy(update={"amount": None})
    payload = dict(vars(body)) if hasattr(body, "__dict__") else {}
    payload["amount"] = None
    return SimpleNamespace(**payload)


def _table_exists(db, table: str) -> bool:
    return inspect(db.get_bind()).has_table(table)


def _formal_scholarship_eligibility(db, student_id, project=None) -> dict:
    """Reassert the project-aware scholarship contract after legacy runtime shims.

    Older compatibility installers may replace ``legacy._check_scholarship`` with a
    two-argument ``scholarship_eligible`` helper.  Formal funding apply/preflight
    passes the selected project so tenant config + project overrides can be frozen
    into the eligibility snapshot.  Package 10 is installed after those shims, so
    this authority layer restores that contract without weakening the old two-arg
    callers (``project`` remains optional).
    """
    from app.models import (AcademicGrade, AcademicStudent, CsDiscipline,
                            CsServiceStudent, StudentProfile)

    contract = legacy._eligibility_rules("SCHOLARSHIP", project)
    rules = contract["rules"]
    student = db.get(StudentProfile, int(student_id))
    status_fact = bool(
        student and student.student_status in (None, "NORMAL", "在籍", "ACTIVE")
    )

    discipline_fact = True
    cs_student = db.scalars(select(CsServiceStudent).where(
        CsServiceStudent.tenant_id == _tid(),
        CsServiceStudent.student_id == int(student_id),
        CsServiceStudent.is_deleted.is_(False),
    )).first()
    if cs_student:
        active_discipline = db.scalar(select(CsDiscipline.id).where(
            CsDiscipline.tenant_id == _tid(),
            CsDiscipline.cs_student_id == cs_student.id,
            CsDiscipline.record_status == "ACTIVE",
            CsDiscipline.is_deleted.is_(False),
        ).limit(1))
        discipline_fact = active_discipline is None

    grade_fact = True
    academic_student = db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == _tid(),
        AcademicStudent.student_id == int(student_id),
        AcademicStudent.is_deleted.is_(False),
    )).first()
    if academic_student:
        failed_grade = db.scalar(select(AcademicGrade.id).where(
            AcademicGrade.tenant_id == _tid(),
            AcademicGrade.acad_student_id == academic_student.id,
            AcademicGrade.pass_status == "FAILED",
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        ).limit(1))
        grade_fact = failed_grade is None

    status_ok = status_fact or not bool(rules.get("requireActiveStatus", True))
    discipline_ok = discipline_fact or not bool(
        rules.get("requireNoActiveDiscipline", True)
    )
    grade_ok = grade_fact or not bool(rules.get("requireNoFailedGrade", True))
    return {
        "type": "SCHOLARSHIP",
        "statusOk": status_ok,
        "disciplineOk": discipline_ok,
        "gradeOk": grade_ok,
        "facts": {
            "activeStatus": status_fact,
            "noActiveDiscipline": discipline_fact,
            "noFailedGrade": grade_fact,
        },
        "ruleVersion": contract["version"],
        "ruleSource": contract["source"],
        "ruleSourceChain": contract["sourceChain"],
        "projectId": contract["projectId"],
        "projectOverrides": contract["projectOverrides"],
        "rules": rules,
        "evaluatedAt": datetime.utcnow().isoformat(),
        "ok": status_ok and discipline_ok and grade_ok,
    }


def _project_rule(db, application) -> tuple[Decimal, dict]:
    from app.models import FundingBatch, FundingProject

    batch = db.get(FundingBatch, int(application.batch_id)) if application.batch_id else None
    if not batch or batch.is_deleted or int(batch.tenant_id) != int(_tid()):
        raise AppException("DATA_CONFLICT", "资助批次不存在或已失效")
    project = db.get(FundingProject, int(batch.project_id)) if batch.project_id else None
    if not project or project.is_deleted or int(project.tenant_id) != int(_tid()):
        raise AppException("DATA_CONFLICT", "资助项目不存在或已失效")
    amount = _money(project.amount, "项目标准金额")
    snapshot = {
        "source": "FUNDING_PROJECT",
        "projectId": int(project.id),
        "projectVersion": int(getattr(project, "version", 0) or 0),
        "amount": format(amount, ".2f"),
        "calculatedAt": datetime.utcnow().isoformat(timespec="seconds"),
    }
    return amount, snapshot


def _approved_adjustment(db, application_id: int) -> tuple[Decimal | None, dict | None]:
    if not _table_exists(db, "t_affairs_funding_amount_adjustment"):
        return None, None
    row = db.execute(text("""
        SELECT id, requested_amount, reason, requester_id, reviewer_id, reviewed_at
          FROM t_affairs_funding_amount_adjustment
         WHERE tenant_id = :tenant_id
           AND application_id = :application_id
           AND status = 'APPROVED'
           AND is_deleted = 0
         ORDER BY id DESC
         LIMIT 1
    """), {"tenant_id": _tid(), "application_id": int(application_id)}).mappings().first()
    if not row:
        return None, None
    amount = _money(row["requested_amount"], "复核批准金额")
    return amount, {
        "source": "DUAL_REVIEW_ADJUSTMENT",
        "adjustmentId": int(row["id"]),
        "reason": row["reason"],
        "requesterId": int(row["requester_id"]),
        "reviewerId": int(row["reviewer_id"]),
        "reviewedAt": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
        "amount": format(amount, ".2f"),
    }


def _freeze_rule_snapshot(application, snapshot: dict) -> None:
    try:
        current = json.loads(application.check_snapshot_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        current = {}
    current["amountAuthority"] = snapshot
    application.check_snapshot_json = json.dumps(current, ensure_ascii=False, sort_keys=True)


def _authoritative_amount(db, application) -> tuple[Decimal, dict]:
    adjusted, adjusted_snapshot = _approved_adjustment(db, int(application.id))
    if adjusted is not None:
        return adjusted, adjusted_snapshot or {}
    return _project_rule(db, application)


def _create_project(body, user):
    if str(getattr(body, "projectType", "") or "").upper() in legacy.V1_TYPES:
        _money(getattr(body, "amount", None), "项目标准金额")
    return _ORIGINALS["create_project"](body, user)


def _apply(body, user):
    # 申请端金额只可作为界面输入，不进入正式事实；旧服务收到的 amount 固定为空。
    result = _ORIGINALS["apply"](_body_without_client_amount(body), user)
    app_id = int(result["applicationId"])
    with session() as db:
        application, student = legacy._load(db, app_id)
        amount, snapshot = _project_rule(db, application)
        application.amount = amount
        application.requested_amount = amount
        application.approved_amount = None
        _freeze_rule_snapshot(application, snapshot)
        legacy._audit(db, application.id, "AMOUNT_RULE_FROZEN",
                      f"project={snapshot['projectId']};version={snapshot['projectVersion']};amount={snapshot['amount']}")
        db.commit()
        db.refresh(application)
        return _app_row(application, user, student)


def _grant_one(db, application):
    amount, snapshot = _authoritative_amount(db, application)
    application.amount = amount
    application.requested_amount = application.requested_amount or amount
    application.approved_amount = amount
    _freeze_rule_snapshot(application, snapshot)
    legacy._audit(db, application.id, "APPROVED_AMOUNT_FROZEN",
                  f"source={snapshot.get('source')};amount={format(amount, '.2f')}")
    return _ORIGINALS["_grant_one"](db, application)


def _app_row(application, user, student=None, *, has_pending_appeal: bool = False) -> dict:
    row = _ORIGINALS["_app_row"](
        application, user, student, has_pending_appeal=has_pending_appeal
    )
    formal = application.approved_amount if application.quota_reserved else application.requested_amount
    row["amount"] = legacy._amount_view(formal, user)
    row["requestedAmount"] = legacy._amount_view(application.requested_amount, user)
    row["approvedAmount"] = legacy._amount_view(application.approved_amount, user)
    row["quotaReserved"] = bool(application.quota_reserved)
    return row


def request_adjustment(application_id: int, user, amount, reason: str, expected_version: int) -> dict:
    _require_amount_role(user)
    amount = _money(amount, "调整金额")
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "调整原因不少于 5 字")
    requester_id = _uid(user)
    if requester_id <= 0:
        raise AppException("NO_PERMISSION", "无法识别调整申请人")

    with session() as db:
        application, _ = legacy._load(db, application_id)
        legacy._scope_or_403(db, application.student_id, user)
        if application.status not in {"SCHOOL_REVIEW", "PUBLICITY"} or application.quota_reserved:
            raise AppException("DATA_CONFLICT", "仅学校审批或公示阶段可申请金额调整")
        check_version(application.version, expected_version)
        standard, _ = _project_rule(db, application)
        if amount == standard:
            raise AppException("VALIDATION_ERROR", "调整金额与项目标准金额一致，无需申请")
        db.execute(text("""
            INSERT INTO t_affairs_funding_amount_adjustment
                (tenant_id, application_id, requested_amount, reason,
                 requester_id, requester_name, status, version,
                 created_at, updated_at, is_deleted)
            VALUES
                (:tenant_id, :application_id, :amount, :reason,
                 :requester_id, :requester_name, 'PENDING', 0,
                 CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)
        """), {
            "tenant_id": _tid(), "application_id": int(application.id),
            "amount": amount, "reason": reason, "requester_id": requester_id,
            "requester_name": _user_name(user),
        })
        adjustment_id = int(db.execute(text("SELECT LAST_INSERT_ID()" )).scalar_one())
        application.version = int(application.version or 0) + 1
        legacy._audit(db, application.id, "AMOUNT_ADJUST_REQUEST",
                      f"adjustment={adjustment_id};amount={format(amount, '.2f')};reason={reason}")
        db.commit()
        return {
            "adjustmentId": str(adjustment_id),
            "applicationId": str(application.id),
            "requestedAmount": format(amount, ".2f"),
            "status": "PENDING",
            "version": application.version,
        }


def review_adjustment(adjustment_id: int, user, action: str, reason: str,
                      expected_application_version: int) -> dict:
    _require_amount_role(user)
    action = str(action or "").upper()
    if action not in {"APPROVE", "REJECT"}:
        raise AppException("VALIDATION_ERROR", "无效复核动作")
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "复核意见不少于 5 字")
    reviewer_id = _uid(user)
    if reviewer_id <= 0:
        raise AppException("NO_PERMISSION", "无法识别复核人")

    with session() as db:
        row = db.execute(text("""
            SELECT *
              FROM t_affairs_funding_amount_adjustment
             WHERE id = :id AND tenant_id = :tenant_id AND is_deleted = 0
             FOR UPDATE
        """), {"id": int(adjustment_id), "tenant_id": _tid()}).mappings().first()
        if not row:
            raise AppException("DATA_NOT_FOUND", "金额调整申请不存在")
        if row["status"] != "PENDING":
            raise AppException("DATA_CONFLICT", "该金额调整已完成复核")
        if int(row["requester_id"]) == reviewer_id:
            raise AppException("NO_PERMISSION", "调整申请人与复核人必须为不同人员")
        application, _ = legacy._load(db, int(row["application_id"]))
        legacy._scope_or_403(db, application.student_id, user)
        check_version(application.version, expected_application_version)
        if application.status not in {"SCHOOL_REVIEW", "PUBLICITY"} or application.quota_reserved:
            raise AppException("DATA_CONFLICT", "当前申请状态不可复核金额调整")
        status = "APPROVED" if action == "APPROVE" else "REJECTED"
        db.execute(text("""
            UPDATE t_affairs_funding_amount_adjustment
               SET status = :status,
                   reviewer_id = :reviewer_id,
                   reviewer_name = :reviewer_name,
                   review_reason = :reason,
                   reviewed_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP,
                   version = version + 1
             WHERE id = :id AND tenant_id = :tenant_id AND status = 'PENDING'
        """), {
            "status": status, "reviewer_id": reviewer_id,
            "reviewer_name": _user_name(user), "reason": reason,
            "id": int(adjustment_id), "tenant_id": _tid(),
        })
        application.version = int(application.version or 0) + 1
        legacy._audit(db, application.id, f"AMOUNT_ADJUST_{status}",
                      f"adjustment={adjustment_id};reviewer={reviewer_id};reason={reason}")
        db.commit()
        return {
            "adjustmentId": str(adjustment_id),
            "applicationId": str(application.id),
            "status": status,
            "reviewerId": str(reviewer_id),
            "version": application.version,
        }


def list_adjustments(application_id: int, user) -> list[dict]:
    with session() as db:
        application, _ = legacy._load(db, application_id)
        legacy._scope_or_403(db, application.student_id, user)
        rows = db.execute(text("""
            SELECT id, requested_amount, reason, requester_id, requester_name,
                   status, reviewer_id, reviewer_name, review_reason,
                   reviewed_at, created_at, version
              FROM t_affairs_funding_amount_adjustment
             WHERE tenant_id = :tenant_id
               AND application_id = :application_id
               AND is_deleted = 0
             ORDER BY id DESC
        """), {"tenant_id": _tid(), "application_id": int(application_id)}).mappings().all()
        return [{
            "adjustmentId": str(row["id"]),
            "requestedAmount": format(row["requested_amount"], ".2f"),
            "reason": row["reason"],
            "requesterId": str(row["requester_id"]),
            "requesterName": row["requester_name"],
            "status": row["status"],
            "reviewerId": str(row["reviewer_id"]) if row["reviewer_id"] else None,
            "reviewerName": row["reviewer_name"],
            "reviewReason": row["review_reason"],
            "reviewedAt": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
            "version": int(row["version"] or 0),
        } for row in rows]


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    for name in ("create_project", "apply", "_grant_one", "_app_row", "_check_scholarship"):
        _ORIGINALS[name] = getattr(legacy, name)
    # Package 10 is the last funding authority installer. Restore the formal
    # project-aware scholarship contract after any older two-argument shim.
    legacy._check_scholarship = _formal_scholarship_eligibility
    legacy.create_project = _create_project
    legacy.apply = _apply
    legacy._grant_one = _grant_one
    legacy._app_row = _app_row
    _INSTALLED = True