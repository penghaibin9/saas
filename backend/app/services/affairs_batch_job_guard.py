"""学工批处理安全门：请假逾期扫描与资助发放台账的并发、范围和副作用。"""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

_INSTALLED = False


def _require_tenant_all(user) -> None:
    from app.core.affairs_security import build_affairs_context
    with session() as db:
        if build_affairs_context(user or {}, db).scope_type != "TENANT_ALL":
            raise AppException("NO_PERMISSION", "该批量操作仅限学校/学工处全域管理员")


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.models import (
        CsLeave, FundingApplication, FundingBatch, FundingDisbursement,
        StudentProfile, StudentStageEvent,
    )
    from app.services import affairs_funding_service as funding
    from app.services import affairs_leave_service as leave

    old_disb_row = funding._disb_row

    def scan_overdue():
        now = datetime.utcnow()
        count = 0
        with session() as db:
            rows = db.scalars(select(CsLeave).where(
                CsLeave.tenant_id == _tid(),
                CsLeave.affairs_status == "APPROVED",
                CsLeave.overdue_pushed_at.is_(None),
                CsLeave.expected_return_at.is_not(None),
                CsLeave.expected_return_at < now,
                CsLeave.is_deleted.is_(False),
            ).order_by(CsLeave.id).limit(200).with_for_update(skip_locked=True)).all()
            for row in rows:
                # 行锁内再次检查，防止上一批已推进后仍被旧快照处理。
                if row.affairs_status != "APPROVED" or row.overdue_pushed_at is not None:
                    continue
                row.affairs_status, row.status, row.overdue_pushed_at = "OVERDUE", "APPROVED", now
                row.version = int(row.version or 0) + 1
                assignee = leave._assignee_for(db, "COUNSELOR_REVIEW", row.student_id)
                leave._todo_upsert(
                    db, row.id, assignee, row.student_id,
                    "请假逾期未销假，请跟进", todo_type="LEAVE_OVERDUE",
                )
                leave._msg(
                    db, row.student_id, "请假已逾期", "你的请假已到期未销假，请尽快销假",
                    "DEADLINE_REMINDER", row.id, event_code="LEAVE.OVERDUE",
                )
                leave._audit(db, row.id, "OVERDUE")
                count += 1
            db.commit()
        if count:
            leave._drain_message_outbox()
        return {"count": count}

    def disbursement_row(row, user, student=None):
        data = old_disb_row(row, user, student)
        data["version"] = int(row.version or 0)
        data["allowedActions"] = {
            "PENDING": ["ISSUE", "FAIL"],
            "FAILED": ["ISSUE"],
            "RETURNED": ["ISSUE", "FAIL"],
        }.get(row.bank_status, [])
        return data

    def generate_disbursements(batch_id, user):
        _require_tenant_all(user)
        with session() as db:
            batch = db.scalars(select(FundingBatch).where(
                FundingBatch.tenant_id == _tid(), FundingBatch.id == int(batch_id),
                FundingBatch.is_deleted.is_(False),
            ).with_for_update()).first()
            if not batch:
                raise not_found("资助批次不存在")
            applications = db.scalars(select(FundingApplication).where(
                FundingApplication.tenant_id == _tid(),
                FundingApplication.batch_id == batch.id,
                FundingApplication.status == "GRANTED",
                FundingApplication.is_deleted.is_(False),
            ).order_by(FundingApplication.id)).all()
            existing = set(db.scalars(select(FundingDisbursement.application_id).where(
                FundingDisbursement.tenant_id == _tid(),
                FundingDisbursement.application_id.in_({row.id for row in applications} or {-1}),
                FundingDisbursement.is_deleted.is_(False),
            )).all())
            made = 0
            for application in applications:
                if application.id in existing:
                    continue
                db.add(FundingDisbursement(
                    tenant_id=_tid(), application_id=application.id,
                    batch_id=application.batch_id, student_id=application.student_id,
                    project_type=application.project_type, amount=application.amount,
                    bank_status="PENDING", created_by=funding._disb_uid(user),
                ))
                made += 1
            if made:
                funding._audit(db, batch.id, "FUNDING_DISBURSE_GENERATE", f"{made}条")
            try:
                db.commit()
            except IntegrityError as exc:
                db.rollback()
                raise AppException("DATA_CONFLICT", "发放台账已由其他请求生成，请刷新") from exc
        return {"generated": made, "eligible": len(applications), "existing": len(existing)}

    def issue_disbursement(disbursement_id, body, user):
        number = str(getattr(body, "disburseNo", None) or "").strip()
        if not 2 <= len(number) <= 100:
            raise AppException("VALIDATION_ERROR", "发放批次号需2-100字")
        last4 = str(getattr(body, "bankLast4", None) or "").strip()
        if last4 and not re.fullmatch(r"\d{4}", last4):
            raise AppException("VALIDATION_ERROR", "银行卡后4位必须为4位数字")
        with session() as db:
            row = db.scalars(select(FundingDisbursement).where(
                FundingDisbursement.tenant_id == _tid(),
                FundingDisbursement.id == int(disbursement_id),
                FundingDisbursement.is_deleted.is_(False),
            ).with_for_update()).first()
            if not row:
                raise not_found("发放记录不存在")
            funding._scope_or_403(db, row.student_id, user)
            if row.bank_status not in ("PENDING", "FAILED", "RETURNED"):
                raise AppException("APPROVAL_VERSION_CONFLICT", "当前发放状态不可标记已发放")
            funding.atomic_claim_version(db, row, getattr(body, "version", None))
            row.bank_status, row.issued_at, row.fail_reason = "ISSUED", datetime.utcnow(), None
            row.disburse_no, row.bank_last4 = number, last4 or row.bank_last4
            row.version = int(row.version or 0) + 1
            funding._audit(db, row.id, "FUNDING_DISBURSE_ISSUE", number)
            db.add(StudentStageEvent(
                tenant_id=_tid(), student_id=int(row.student_id), from_stage=None,
                to_stage="FUNDING_DISBURSED", reason=f"资助已发放，批次号{number}",
                source_module="student-affairs",
            ))
            funding._msg(
                db, row.student_id, "资助已发放",
                f"你的资助已发放，批次号：{number}", "WORKFLOW_RESULT", row.application_id,
            )
            db.commit(); db.refresh(row)
            student = db.get(StudentProfile, int(row.student_id))
            result = disbursement_row(row, user, student)
        funding._drain_message_outbox()
        return result

    def fail_disbursement(disbursement_id, user, reason="", expected_version=None):
        text = str(reason or "").strip()
        if not 5 <= len(text) <= 500:
            raise AppException("VALIDATION_ERROR", "失败原因需5-500字")
        with session() as db:
            row = db.scalars(select(FundingDisbursement).where(
                FundingDisbursement.tenant_id == _tid(),
                FundingDisbursement.id == int(disbursement_id),
                FundingDisbursement.is_deleted.is_(False),
            ).with_for_update()).first()
            if not row:
                raise not_found("发放记录不存在")
            funding._scope_or_403(db, row.student_id, user)
            if row.bank_status not in ("PENDING", "RETURNED"):
                raise AppException("APPROVAL_VERSION_CONFLICT", "当前发放状态不可标记失败")
            funding.atomic_claim_version(db, row, expected_version)
            row.bank_status, row.fail_reason = "FAILED", text
            row.version = int(row.version or 0) + 1
            funding._audit(db, row.id, "FUNDING_DISBURSE_FAIL", text)
            funding._msg(
                db, row.student_id, "资助发放异常",
                "你的资助发放暂未成功，学校正在处理，请勿重复提交申请。",
                "STATUS_CHANGED", row.application_id,
            )
            db.commit(); db.refresh(row)
            student = db.get(StudentProfile, int(row.student_id))
            result = disbursement_row(row, user, student)
        funding._drain_message_outbox()
        return result

    def disbursement_stats(user):
        from app.services.affairs_dashboard_service import _allowed_class_ids
        from decimal import Decimal
        with session() as db:
            allowed, _ = _allowed_class_ids(db, user)
            conds = [
                FundingDisbursement.tenant_id == _tid(),
                FundingDisbursement.is_deleted.is_(False),
                StudentProfile.tenant_id == _tid(),
                StudentProfile.is_deleted.is_(False),
            ]
            if allowed is not None:
                conds.append(StudentProfile.class_id.in_(allowed or {-1}))
            rows = db.scalars(select(FundingDisbursement).join(
                StudentProfile, StudentProfile.id == FundingDisbursement.student_id,
            ).where(*conds)).all()
            by_status = {}
            issued_total = Decimal("0.00")
            for row in rows:
                by_status[row.bank_status] = by_status.get(row.bank_status, 0) + 1
                if row.bank_status == "ISSUED":
                    issued_total += Decimal(str(row.amount or 0))
            output = {
                "total": len(rows),
                "byStatus": [
                    {"key": key, "label": funding._L_BANK.get(key, key), "count": value}
                    for key, value in by_status.items()
                ],
            }
            if (user or {}).get("currentRoleCode") in funding._AMOUNT_ROLES:
                output["issuedAmountTotal"] = format(issued_total.quantize(Decimal("0.01")), ".2f")
            return output

    leave.scan_overdue = scan_overdue
    funding._disb_row = disbursement_row
    funding.generate_disbursements = generate_disbursements
    funding.issue_disbursement = issue_disbursement
    funding.fail_disbursement = fail_disbursement
    funding.disbursement_stats = disbursement_stats
    _INSTALLED = True
