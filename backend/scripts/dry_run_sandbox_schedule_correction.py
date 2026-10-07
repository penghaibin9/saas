"""Preview the sandbox current-term correction draft without changing schedule facts.

This deliberately calls the public autoscheduling service entrypoint so the preview
uses the same term-scoped task resolution and policy checks as the HTTP route.
"""
from __future__ import annotations

import json
import argparse
from collections import Counter

from sqlalchemy import select

from app.core.context import set_current_user, set_tenant
from app.core.tenant_identity import SANDBOX_SCHOOL
from app.db.session import get_sessionmaker
from app.models import AaScheduleBatch, Tenant
from app.modules.academic_affairs.services import academic_affairs_autoschedule_service
from app.modules.academic_affairs.services import academic_affairs_schedule_gate_service


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the verified incremental result to the correction DRAFT only.",
    )
    args = parser.parse_args()
    tenant_id = int(SANDBOX_SCHOOL.tenant_id)
    user = {
        "userId": "sandbox-relationship-auditor",
        "loginName": "sandbox-relationship-auditor",
        "realName": "沙箱关系闭包审计",
        "userType": "STAFF",
        "currentRoleCode": "SCHOOL_ADMIN",
    }
    set_tenant({
        "tenantId": str(tenant_id),
        "tenantCode": SANDBOX_SCHOOL.tenant_code,
        "tenantName": "体验沙箱学校",
        "status": "ACTIVE",
    })
    set_current_user(user)

    with get_sessionmaker()() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id))
        if tenant is None or tenant.tenant_code != SANDBOX_SCHOOL.tenant_code:
            raise RuntimeError("拒绝执行：当前数据库不是 sandbox-school")
        batch = db.scalar(
            select(AaScheduleBatch)
            .where(
                AaScheduleBatch.tenant_id == tenant_id,
                AaScheduleBatch.status == "DRAFT",
                AaScheduleBatch.is_deleted.is_(False),
                AaScheduleBatch.supersedes_batch_id.is_not(None),
            )
            .order_by(AaScheduleBatch.id.desc())
            .limit(1)
        )
        if batch is None:
            raise RuntimeError("未找到当前学期纠错草稿")
        batch_id = int(batch.id)

    result = academic_affairs_autoschedule_service.auto_schedule(
        user,
        batch_id,
        dry_run=not args.apply,
    )
    with get_sessionmaker()() as db:
        batch = db.scalar(
            select(AaScheduleBatch).where(
                AaScheduleBatch.id == batch_id,
                AaScheduleBatch.tenant_id == tenant_id,
                AaScheduleBatch.is_deleted.is_(False),
            )
        )
        if batch is None:
            raise RuntimeError("纠错草稿在校验前消失")
        gate = academic_affairs_schedule_gate_service.evaluate(db, batch)
    reason_counts = Counter(item.get("reason") or "UNKNOWN" for item in result["misses"])
    print(json.dumps({
        "batchId": result["batchId"],
        "termId": result["termId"],
        "dryRun": result["dryRun"],
        "placedSessions": result["placedSessions"],
        "placedTasks": result["placedTasks"],
        "missedTasks": result["missedTasks"],
        "invalidTaskCount": result["invalidTaskCount"],
        "roomPoolSize": result["roomPoolSize"],
        "missReasons": dict(sorted(reason_counts.items())),
        "capacityWarningCount": len(result["capacityWarnings"]),
        "publishGate": {
            "complete": gate["complete"],
            "canPrePublish": gate["canPrePublish"],
            "totalTasks": gate["totalTasks"],
            "expectedSessions": gate["expectedSessions"],
            "scheduledSessions": gate["scheduledSessions"],
            "missingTaskCount": gate["missingTaskCount"],
            "overScheduledTaskCount": gate["overScheduledTaskCount"],
            "orphanItemCount": gate["orphanItemCount"],
            "hardConflicts": gate["hardConflicts"],
            "softConflicts": gate["softConflicts"],
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
