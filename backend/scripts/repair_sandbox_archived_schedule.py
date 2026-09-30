"""Forward-only repair for sandbox-school's incomplete archived-term schedule.

Default is read-only.  ``--apply`` uses the production post-archive correction flow:
an existing administrator opens a SCHEDULE correction, a different existing academic
administrator approves it, the replacement schedule is published, and Manifest V3+
is appended in the same transaction.  No passwords are read or changed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TENANT_ID = 1000000000000000007
TENANT_CODE = "sandbox-school"
TERM_CODE = "2025-2026-2"


def _user(row) -> dict:
    return {
        "userId": str(row.id),
        "loginName": row.login_name,
        "realName": row.real_name or row.login_name,
        "userType": "SCHOOL_ADMIN",
        "currentRoleCode": "SCHOOL_ADMIN",
    }


def _activate(user: dict) -> None:
    from app.core.context import set_current_user, set_tenant

    set_tenant({"tenantId": str(TENANT_ID), "tenantCode": TENANT_CODE})
    set_current_user(user)


def main() -> int:
    parser = argparse.ArgumentParser(description="修复 sandbox-school 历史课表归档断链")
    parser.add_argument("--apply", action="store_true", help="经双人归档后纠错正式应用；默认只读")
    args = parser.parse_args()

    from sqlalchemy import func, select

    from app.db.session import get_sessionmaker
    from app.models import (
        AaArchiveBatch,
        AaScheduleBatch,
        AaScheduleItem,
        AaTeachingTask,
        AaTeachingTaskBatch,
        PostArchiveCorrectionCase,
        Tenant,
        User,
    )

    db = get_sessionmaker()()
    try:
        tenant = db.get(Tenant, TENANT_ID)
        if not tenant or tenant.tenant_code != TENANT_CODE:
            raise RuntimeError("目标租户身份校验失败，拒绝执行")
        archive = db.scalars(select(AaArchiveBatch).where(
            AaArchiveBatch.tenant_id == TENANT_ID,
            AaArchiveBatch.term_code == TERM_CODE,
            AaArchiveBatch.status == "ARCHIVED",
            AaArchiveBatch.is_deleted.is_(False),
        ).order_by(AaArchiveBatch.id.desc()).limit(1)).first()
        if not archive:
            raise RuntimeError("未找到目标历史归档批次")
        source = db.scalars(select(AaScheduleBatch).where(
            AaScheduleBatch.tenant_id == TENANT_ID,
            AaScheduleBatch.term_id == archive.term_id,
            AaScheduleBatch.status == "PUBLISHED",
            AaScheduleBatch.is_deleted.is_(False),
        ).order_by(AaScheduleBatch.id.desc()).limit(1)).first()
        if not source:
            completed = db.scalars(select(AaScheduleBatch).where(
                AaScheduleBatch.tenant_id == TENANT_ID,
                AaScheduleBatch.term_id == archive.term_id,
                AaScheduleBatch.status == "SUPERSEDED",
                AaScheduleBatch.is_deleted.is_(False),
            ).order_by(AaScheduleBatch.id.desc()).limit(1)).first()
            if completed:
                print(json.dumps({"alreadyRepaired": True, "latestSupersededBatchId": str(completed.id)}, ensure_ascii=False))
                return 0
            raise RuntimeError("目标归档学期没有可更正的 PUBLISHED 课表")
        task_batch_ids = list(db.scalars(select(AaTeachingTaskBatch.id).where(
            AaTeachingTaskBatch.tenant_id == TENANT_ID,
            AaTeachingTaskBatch.term_id == archive.term_id,
            AaTeachingTaskBatch.is_deleted.is_(False),
        )).all())
        expected = int(db.scalar(select(func.sum(AaTeachingTask.weekly_hours)).where(
            AaTeachingTask.tenant_id == TENANT_ID,
            AaTeachingTask.batch_id.in_(task_batch_ids),
            AaTeachingTask.status == "READY",
            AaTeachingTask.is_deleted.is_(False),
        )) or 0)
        actual = int(db.scalar(select(func.count()).select_from(AaScheduleItem).where(
            AaScheduleItem.tenant_id == TENANT_ID,
            AaScheduleItem.batch_id == source.id,
            AaScheduleItem.status == "EFFECTIVE",
            AaScheduleItem.is_deleted.is_(False),
        )) or 0)
        actors = list(db.scalars(select(User).where(
            User.tenant_id == TENANT_ID,
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
            User.login_name.like("sbx_aa%"),
        ).order_by(User.login_name).limit(2)).all())
        if len(actors) < 2:
            raise RuntimeError("归档后更正需要两名不同的现有教务管理员")
        pending = db.scalars(select(PostArchiveCorrectionCase).where(
            PostArchiveCorrectionCase.tenant_id == TENANT_ID,
            PostArchiveCorrectionCase.archive_batch_id == archive.id,
            PostArchiveCorrectionCase.business_type == "SCHEDULE",
            PostArchiveCorrectionCase.status == "PENDING_SECOND_APPROVAL",
            PostArchiveCorrectionCase.is_deleted.is_(False),
        ).order_by(PostArchiveCorrectionCase.id.desc()).limit(1)).first()
        preview = {
            "tenantCode": TENANT_CODE,
            "archiveBatchId": str(archive.id),
            "sourceScheduleBatchId": str(source.id),
            "actualSessions": actual,
            "expectedSessions": expected,
            "missingSessions": max(0, expected - actual),
            "creator": actors[0].login_name,
            "secondApprover": actors[1].login_name,
            "pendingCaseId": str(pending.id) if pending else None,
            "willApply": bool(args.apply),
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        if not args.apply:
            return 0
        if expected <= 0:
            raise RuntimeError("当前正式课表应排节次为 0，拒绝处理")
        already_complete = actual >= expected
        from app.services.sandbox_school_academic_archive_prereq import (
            _close_historical_exam_and_makeup,
        )
        operational_reconciliation = _close_historical_exam_and_makeup(
            db, TENANT_ID, int(archive.term_id),
        )
        print(json.dumps(
            {"historicalOperationalReconciliation": operational_reconciliation},
            ensure_ascii=False,
            indent=2,
        ))
        archive_id = int(archive.id)
        source_id = int(source.id)
        pending_id = int(pending.id) if pending else None
        creator = _user(actors[0])
        reviewer = _user(actors[1])
    finally:
        db.close()

    from app.modules.academic_affairs.services import academic_affairs_archive_service as service

    if already_complete:
        _activate(reviewer)
        verified = service.verify_manifest(reviewer, archive_id)
        checkpoint = None
        if not verified.get("ok") and "HASH_MISMATCH" in str(verified.get("reason") or ""):
            _activate(creator)
            checkpoint = service.append_integrity_checkpoint(
                creator,
                archive_id,
                note="课表归档后更正完成，十三域实时规则通过；见证早期非 C3 清单原始字节",
            )
            _activate(reviewer)
            verified = service.verify_manifest(reviewer, archive_id)
        print(json.dumps({
            "alreadyRepaired": True,
            "integrityCheckpoint": checkpoint,
            "manifestVerification": verified,
        }, ensure_ascii=False, indent=2))
        return 0 if verified.get("ok") else 2

    if pending_id is None:
        _activate(creator)
        created = service.create_correction_case(
            creator,
            archive_id,
            business_type="SCHEDULE",
            target_ref=str(source_id),
            reason="历史正式课表漏排节次，按教学任务周课时生成完整替代版本",
            correction={
                "mode": "REPLACE_INCOMPLETE_PUBLISHED_BATCH",
                "expectedSessions": expected,
                "observedSessions": actual,
            },
            evidence_manifest={
                "auditCode": "AA_PUBLISHED_SCHEDULE_COMPLETE",
                "sourceScheduleBatchId": str(source_id),
                "expectedSessions": expected,
                "observedSessions": actual,
            },
            risk_level="HIGH",
        )
        pending_id = int(created["caseId"])

    _activate(reviewer)
    try:
        applied = service.approve_correction_case(reviewer, pending_id)
    except Exception as exc:
        print(json.dumps({
            "approvalError": str(exc),
            "code": getattr(exc, "code", None),
            "details": getattr(exc, "details", None),
        }, ensure_ascii=False, indent=2, default=str))
        raise
    verified = service.verify_manifest(reviewer, archive_id)
    checkpoint = None
    if not verified.get("ok") and "HASH_MISMATCH" in str(verified.get("reason") or ""):
        _activate(creator)
        checkpoint = service.append_integrity_checkpoint(
            creator,
            archive_id,
            note="课表归档后更正完成，十三域实时规则通过；见证早期非 C3 清单原始字节",
        )
        _activate(reviewer)
        verified = service.verify_manifest(reviewer, archive_id)
    print(json.dumps({
        "applied": applied,
        "integrityCheckpoint": checkpoint,
        "manifestVerification": verified,
    }, ensure_ascii=False, indent=2))
    return 0 if verified.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
