"""包 10：资助公示事务隔离、授予前资格复核与正式评审节点安全门。

旧实现把最多 200 条到期申请放进同一事务。只要其中一条触发名额或金额额度冲突，
整个事务都会回滚，已经成功占位的申请也会被撤销，后续扫描会重复失败。
本守卫先读取候选 ID，再逐条加锁、逐条提交；并发 worker 通过 SKIP LOCKED 互斥，
额度冲突只影响当前申请，不影响同批次其他合法申请。

SA-005 还要求助学金在真正授予前重新读取 SA-002 困难学生库事实：申请时冻结的资格
快照不能替代发放时的当前资格。自动扫描与人工公示确认最终都会调用 ``_grant_one``，
因此在同一写事务里统一重验，避免资格漂移后仍错误授予。

正式资助评审必须严格遵守辅导员→学院→学校三级节点及当前 WorkflowTask 受理人，
TENANT_ALL 只代表数据范围，不得作为越节点代审或绕过待办指派的授权。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.core.exceptions import AppException
from app.core.tenant_scoped import tenant_get
from app.services import affairs_funding_service as legacy
from app.services.db_service import _tid, session

_INSTALLED = False
_ORIGINAL_SCAN: Any = None
_ORIGINAL_GRANT_ONE: Any = None
_QUOTA_CONFLICT_MARKERS = {
    "FUNDING_QUOTA_OR_BUDGET_EXCEEDED",
    "FUNDING_QUOTA_EXCEEDED",
    "FUNDING_AMOUNT_BUDGET_EXCEEDED",
}
_REVIEW_SCOPE = {
    "COUNSELOR_REVIEW": "CLASS",
    "COLLEGE_REVIEW": "COLLEGE",
    "SCHOOL_REVIEW": "TENANT_ALL",
}


class _GrantEligibilityChanged(AppException):
    """助学金申请在提交后、真正授予前资格已经变化。"""

    def __init__(self, message: str):
        super().__init__("DATA_CONFLICT", message)


def _is_quota_conflict(exc: BaseException) -> bool:
    message = str(getattr(exc, "orig", exc) or exc)
    return any(marker in message for marker in _QUOTA_CONFLICT_MARKERS)


def _check_fund_review_node(db, application, user) -> None:
    """按正式三级链校验数据范围与当前待办受理人，禁止管理员越节点代审。"""
    from app.core.affairs_security import build_affairs_context
    from app.models import WorkflowTask

    node = str(getattr(application, "status", "") or "")
    expected_scope = _REVIEW_SCOPE.get(node)
    if not expected_scope:
        raise AppException("DATA_CONFLICT", "当前资助申请不在正式评审节点")

    context = build_affairs_context(user, db)
    if context.scope_type != expected_scope:
        raise AppException("NO_PERMISSION", f"当前账号不是 {legacy.L_FUND.get(node, node)} 的受理角色")

    instance_id = int(getattr(application, "workflow_instance_id", 0) or 0)
    if instance_id <= 0:
        raise AppException("DATA_CONFLICT", "资助审批流缺失，禁止绕过正式节点审批")

    task = db.scalars(select(WorkflowTask).where(
        WorkflowTask.tenant_id == _tid(),
        WorkflowTask.instance_id == instance_id,
        WorkflowTask.node_code == node,
        WorkflowTask.status == "PENDING",
        WorkflowTask.is_deleted.is_(False),
    ).order_by(WorkflowTask.id.desc())).first()
    if not task or int(task.assignee_id or 0) <= 0:
        raise AppException("DATA_CONFLICT", "当前资助审批节点没有有效受理人")

    uid = legacy._uid_int(user)
    if uid <= 0 or int(task.assignee_id) != uid:
        raise AppException("NO_PERMISSION", "当前资助审批任务未指派给您")


def _grant_eligibility_snapshot(db, application) -> dict | None:
    """GRANT 在授予前重读当前困难库资格；奖学金保持既有 SA-004 语义。"""
    if str(getattr(application, "project_type", "") or "").upper() != "GRANT":
        return None

    from app.models import FundingBatch, FundingProject

    tenant_id = _tid()
    batch = (
        tenant_get(db, FundingBatch, int(application.batch_id), tenant_id=tenant_id)
        if application.batch_id else None
    )
    if not batch or batch.is_deleted:
        raise _GrantEligibilityChanged("助学资格复核失败：资助批次不存在或已失效")
    project = (
        tenant_get(db, FundingProject, int(batch.project_id), tenant_id=tenant_id)
        if batch.project_id else None
    )
    if not project or project.is_deleted:
        raise _GrantEligibilityChanged("助学资格复核失败：资助项目不存在或已失效")

    snapshot = legacy._check_grant(db, int(application.student_id), project)
    if not snapshot.get("ok"):
        raise _GrantEligibilityChanged(
            f"助学资格已变化，不能授予：{legacy._reject_reason(snapshot)}"
        )
    return snapshot


def _grant_one(db, application):
    """所有 PUBLICITY→GRANTED 路径共用的最终资格闸。"""
    snapshot = _grant_eligibility_snapshot(db, application)
    if snapshot is not None:
        try:
            frozen = json.loads(application.check_snapshot_json or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            frozen = {}
        frozen["grantEligibilityRecheck"] = snapshot
        application.check_snapshot_json = json.dumps(
            frozen, ensure_ascii=False, sort_keys=True
        )
        legacy._audit(
            db,
            application.id,
            "GRANT_ELIGIBILITY_RECHECK",
            f"level={snapshot.get('aidLevel')};ruleVersion={snapshot.get('ruleVersion')}",
        )
    if _ORIGINAL_GRANT_ONE is None:
        raise RuntimeError("funding grant eligibility guard is not installed")
    return _ORIGINAL_GRANT_ONE(db, application)


def scan_publicity() -> dict:
    """逐申请确认公示，保证单条冲突不会回滚整批成功项。"""
    from app.models import FundingApplication, FundingBatch

    now = datetime.utcnow()
    tenant_id = _tid()
    candidates: list[int] = []
    skipped_appeal = 0
    invalid_batch = 0

    # 第一阶段只读取候选，不持有跨申请长事务锁。
    with session() as db:
        rows = db.execute(
            select(
                FundingApplication.id,
                FundingApplication.batch_id,
                FundingApplication.publicity_at,
            )
            .where(
                FundingApplication.tenant_id == tenant_id,
                FundingApplication.status == "PUBLICITY",
                FundingApplication.publicity_at.is_not(None),
                FundingApplication.is_deleted.is_(False),
            )
            .order_by(FundingApplication.id)
            .limit(200)
        ).all()
        pending = legacy._pending_appeal_ids(db, [row.id for row in rows])
        batch_ids = {int(row.batch_id) for row in rows if row.batch_id}
        batches = {
            int(batch.id): batch
            for batch in db.scalars(
                select(FundingBatch).where(
                    FundingBatch.tenant_id == tenant_id,
                    FundingBatch.id.in_(batch_ids) if batch_ids else FundingBatch.id == -1,
                    FundingBatch.is_deleted.is_(False),
                )
            ).all()
        }
        for row in rows:
            app_id = int(row.id)
            if app_id in pending:
                skipped_appeal += 1
                continue
            batch = batches.get(int(row.batch_id)) if row.batch_id else None
            if not batch:
                invalid_batch += 1
                continue
            due = row.publicity_at + timedelta(days=max(1, int(batch.publicity_days or 5)))
            if due <= now:
                candidates.append(app_id)

    confirmed = 0
    quota_conflict = 0
    eligibility_conflict = 0
    stale = 0

    # 第二阶段逐申请独立事务：一条失败不会污染其他申请。
    for app_id in candidates:
        with session() as db:
            application = db.scalars(
                select(FundingApplication)
                .where(
                    FundingApplication.id == app_id,
                    FundingApplication.tenant_id == tenant_id,
                    FundingApplication.status == "PUBLICITY",
                    FundingApplication.is_deleted.is_(False),
                )
                .with_for_update(skip_locked=True)
            ).first()
            if not application:
                stale += 1
                continue

            # 候选读取后可能新产生申诉，正式写入前必须再次核验。
            if legacy._pending_appeal_ids(db, [app_id]):
                skipped_appeal += 1
                continue

            batch = (
                tenant_get(db, FundingBatch, int(application.batch_id), tenant_id=tenant_id)
                if application.batch_id else None
            )
            if not batch or batch.is_deleted:
                invalid_batch += 1
                continue
            due = application.publicity_at + timedelta(days=max(1, int(batch.publicity_days or 5)))
            if due > datetime.utcnow():
                stale += 1
                continue

            try:
                legacy._grant_one(db, application)
                db.commit()
                confirmed += 1
            except _GrantEligibilityChanged:
                db.rollback()
                eligibility_conflict += 1
                continue
            except DBAPIError as exc:
                db.rollback()
                if _is_quota_conflict(exc):
                    quota_conflict += 1
                    continue
                raise

    legacy._drain_message_outbox()
    return {
        "count": confirmed,
        "skippedAppeal": skipped_appeal,
        "invalidBatch": invalid_batch,
        "quotaConflict": quota_conflict,
        "eligibilityConflict": eligibility_conflict,
        "stale": stale,
    }


def install() -> None:
    global _INSTALLED, _ORIGINAL_SCAN, _ORIGINAL_GRANT_ONE
    if _INSTALLED:
        return
    _ORIGINAL_SCAN = legacy.scan_publicity
    _ORIGINAL_GRANT_ONE = legacy._grant_one
    # 先包住最终授予原语；后安装的金额 Authority 会把本守卫保存为自己的
    # _grant_one 原实现，因此自动扫描与人工确认仍会经过同一资格复核。
    legacy._grant_one = _grant_one
    legacy.scan_publicity = scan_publicity
    legacy._check_fund_review_node = _check_fund_review_node
    _INSTALLED = True
