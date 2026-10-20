"""Promote the complete sandbox correction draft through the governed publish flow."""
from __future__ import annotations

import json

from sqlalchemy import func, select

from app.core.context import set_current_user, set_tenant
from app.core.tenant_identity import SANDBOX_SCHOOL
from app.db.session import get_sessionmaker
from app.models import (
    AaScheduleBatch,
    AaScheduleItem,
    AaSchedulePublish,
    AaScheduleScopeHead,
    Tenant,
)
from app.modules.academic_affairs.services import academic_affairs_schedule_service
from app.modules.academic_affairs.services import academic_affairs_schedule_gate_service


def _sandbox_context() -> tuple[int, dict]:
    tenant_id = int(SANDBOX_SCHOOL.tenant_id)
    user = {
        "userId": "sandbox-schedule-correction",
        "loginName": "sandbox-schedule-correction",
        "realName": "沙箱课表纠错",
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
    return tenant_id, user


def _load_target(db, tenant_id: int) -> AaScheduleBatch:
    tenant = db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if tenant is None or tenant.tenant_code != SANDBOX_SCHOOL.tenant_code:
        raise RuntimeError("拒绝执行：当前数据库不是 sandbox-school")
    batch = db.scalar(
        select(AaScheduleBatch)
        .where(
            AaScheduleBatch.tenant_id == tenant_id,
            AaScheduleBatch.status.in_(("DRAFT", "PRE_PUBLISHED", "PUBLISHED")),
            AaScheduleBatch.is_deleted.is_(False),
            AaScheduleBatch.supersedes_batch_id.is_not(None),
        )
        .order_by(AaScheduleBatch.id.desc())
        .limit(1)
    )
    if batch is None:
        raise RuntimeError("未找到当前学期纠错批次")
    return batch


def main() -> None:
    tenant_id, user = _sandbox_context()
    with get_sessionmaker()() as db:
        batch = _load_target(db, tenant_id)
        gate = academic_affairs_schedule_gate_service.evaluate(db, batch)
        if not gate["complete"]:
            raise RuntimeError(
                "拒绝发布：纠错草稿未通过完整性闸门 "
                + json.dumps(gate, ensure_ascii=False)
            )
        batch_id = int(batch.id)
        initial_status = str(batch.status)

    pre_publish = None
    if initial_status == "DRAFT":
        pre_publish = academic_affairs_schedule_service.pre_publish(batch_id, user)
    publish = academic_affairs_schedule_service.publish(batch_id, user)

    with get_sessionmaker()() as db:
        batch = _load_target(db, tenant_id)
        item_count = int(db.scalar(
            select(func.count()).select_from(AaScheduleItem).where(
                AaScheduleItem.tenant_id == tenant_id,
                AaScheduleItem.batch_id == batch_id,
                AaScheduleItem.status == "EFFECTIVE",
                AaScheduleItem.is_deleted.is_(False),
            )
        ) or 0)
        publish_count = int(db.scalar(
            select(func.count()).select_from(AaSchedulePublish).where(
                AaSchedulePublish.tenant_id == tenant_id,
                AaSchedulePublish.batch_id == batch_id,
                AaSchedulePublish.action == "PUBLISH",
                AaSchedulePublish.is_deleted.is_(False),
            )
        ) or 0)
        head = db.scalar(
            select(AaScheduleScopeHead).where(
                AaScheduleScopeHead.tenant_id == tenant_id,
                AaScheduleScopeHead.term_id == int(batch.term_id),
                AaScheduleScopeHead.active_batch_id == batch_id,
                AaScheduleScopeHead.is_deleted.is_(False),
            )
        )
        source = db.scalar(select(AaScheduleBatch).where(
            AaScheduleBatch.id == int(batch.supersedes_batch_id),
            AaScheduleBatch.tenant_id == tenant_id,
        ))
        final = {
            "batchId": str(batch_id),
            "initialStatus": initial_status,
            "prePublishStatus": (pre_publish or {}).get("status"),
            "publishStatus": publish.get("status"),
            "finalStatus": batch.status,
            "scheduleItems": item_count,
            "publishLedgers": publish_count,
            "scopeHeadActive": head is not None,
            "supersededBatchId": str(source.id) if source else None,
            "supersededBatchStatus": source.status if source else None,
            "notified": publish.get("notified", 0),
        }
    print(json.dumps(final, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
