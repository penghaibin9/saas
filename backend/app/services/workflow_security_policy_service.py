"""SYS-14：流程节点动作安全策略、版本变更策略、人工推进与异常治理。

这张卡管两件事，读代码前先说清楚
──────────────────────────────
1. **节点动作权限 ≠ 页面权限**。真实审批执行链路
   （``db_service.act_task`` → ``_can_manage_all_approvals``）里，任何持有通配页面权限
   ``approval.manage``/``*`` 的账号可以代批任意流程任意节点，不管节点的责任角色是谁。
   本模块提供一条 NODE_ACTION 策略：一旦对某个 (workflow_code[, node_code]) **激活**，
   就把该范围的"通配旁路"关掉，只放行真正的 assignee 或额外持有
   ``action_permission_code`` 的人。没有激活策略＝行为跟以前完全一样（向后兼容）。
   真正把这条策略接进 ``db_service.act_task`` 执行路径的改动是**独立提交**（见该提交
   说明），不在本卡白名单内，但没有它这张卡就是自说自话的摆设——细节见提交历史。
2. **VERSION_STRATEGY**：流程定义被改（``runtime_preset_install_service.update_workflow``）
   且该流程还有 RUNNING 实例时怎么办。SNAPSHOT 直接拒绝改动；MIGRATE 允许改但留痕
   受影响实例数；不设策略（DYNAMIC，默认）保持现状。

激活走"本地两人复核"，不是字面意义的"统一走 SYS-09"
──────────────────────────────────────────────
SYS-09 的安全变更目标类型 ``TARGET_TYPES`` 目前只有 ``CUSTOM_ROLE``/``SCOPE_POLICY``
两种，扩展它需要改 ``app/models/security_change.py`` 和
``app/services/security_change_service.py``——这两个文件不在本卡白名单内，属于
SYS-09 的施工范围。所以激活复用 SYS-09 已经验证过的"自复核 fail-closed"语义
（提交人 ≠ 复核人才能激活），在本模块内独立实现，不去动 SYS-09 的目标类型枚举。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.workflow_security_policy import (POLICY_NODE_ACTION,
                                                  POLICY_TYPES,
                                                  POLICY_VERSION_STRATEGY,
                                                  STATUS_ACTIVE, STATUS_DRAFT,
                                                  STATUS_PENDING_REVIEW,
                                                  STATUS_RETIRED,
                                                  STRATEGY_DYNAMIC,
                                                  STRATEGY_MIGRATE,
                                                  STRATEGY_SNAPSHOT,
                                                  VERSION_STRATEGIES,
                                                  WORKFLOW_LEVEL_NODE,
                                                  WorkflowActionPolicy,
                                                  WorkflowVersionMigrationEvent)

SELF_REVIEW_TEXT = "自复核通过，已确认影响面"


def _tid(tenant_id: int | None = None) -> int:
    return int(tenant_id if tenant_id is not None else (current_tenant_id() or 0))


def _now() -> datetime:
    # MySQL DATETIME 无微秒位会四舍五入进位，统一截断到秒（阶段2已踩过的坑）。
    return datetime.now().replace(microsecond=0)


def _actor(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or "").replace("db-", "")
    return int(raw) if raw.isdigit() else None


def _dto(row: WorkflowActionPolicy) -> dict:
    return {
        "policyId": str(row.id), "workflowCode": row.workflow_code,
        "nodeCode": row.node_code or "", "policyType": row.policy_type,
        "status": row.status,
        "actionPermissionCode": row.action_permission_code or "",
        "versionStrategy": row.version_strategy,
        "reason": row.reason or "",
        "submittedBy": str(row.submitted_by or ""), "submittedAt": str(row.submitted_at or "")[:19],
        "reviewedBy": str(row.reviewed_by or ""), "reviewedAt": str(row.reviewed_at or "")[:19],
        "version": int(row.version or 0),
    }


def _load(db, tenant_id: int, policy_id: int) -> WorkflowActionPolicy:
    row = db.scalars(select(WorkflowActionPolicy).where(
        WorkflowActionPolicy.id == int(policy_id), WorkflowActionPolicy.tenant_id == tenant_id,
        WorkflowActionPolicy.is_deleted.is_(False))).first()
    if row is None:
        raise AppException("DATA_NOT_FOUND", "流程安全策略不存在")
    return row


def _check_version(row, expected_version) -> None:
    if expected_version in (None, ""):
        return
    if int(expected_version) != int(row.version or 0):
        raise AppException("DATA_CONFLICT", "该策略已被他人更新，请刷新后重试")


def list_policies(*, workflow_code: str = "", tenant_id: int | None = None) -> dict:
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        stmt = select(WorkflowActionPolicy).where(
            WorkflowActionPolicy.tenant_id == tid, WorkflowActionPolicy.is_deleted.is_(False))
        if workflow_code:
            stmt = stmt.where(WorkflowActionPolicy.workflow_code == workflow_code)
        rows = db.scalars(stmt.order_by(WorkflowActionPolicy.workflow_code,
                                        WorkflowActionPolicy.node_code)).all()
        return {"list": [_dto(r) for r in rows], "total": len(rows)}
    finally:
        db.close()


def get_draft(workflow_code: str, *, node_code: str = WORKFLOW_LEVEL_NODE,
             policy_type: str = POLICY_NODE_ACTION, tenant_id: int | None = None) -> dict:
    """按 (workflow_code, node_code, policy_type) 取当前记录；没有则返回一个空白草稿视图。"""
    if policy_type not in POLICY_TYPES:
        raise AppException("VALIDATION_ERROR", f"未知策略类型：{policy_type}")
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(WorkflowActionPolicy).where(
            WorkflowActionPolicy.tenant_id == tid,
            WorkflowActionPolicy.workflow_code == workflow_code,
            WorkflowActionPolicy.node_code == node_code,
            WorkflowActionPolicy.policy_type == policy_type,
            WorkflowActionPolicy.is_deleted.is_(False))).first()
        if row is None:
            return {"policyId": "", "workflowCode": workflow_code, "nodeCode": node_code,
                    "policyType": policy_type, "status": "", "actionPermissionCode": "",
                    "versionStrategy": STRATEGY_DYNAMIC, "reason": "", "version": 0}
        return _dto(row)
    finally:
        db.close()


def save_draft(workflow_code: str, *, node_code: str = WORKFLOW_LEVEL_NODE,
               policy_type: str = POLICY_NODE_ACTION, action_permission_code: str | None = None,
               version_strategy: str = STRATEGY_DYNAMIC, reason: str,
               expected_version: int | None = None, tenant_id: int | None = None,
               user: dict | None = None) -> dict:
    """新建或修改草稿。已 ACTIVE 的策略要改必须先走 retire，不能原地静默覆盖生效中的规则。"""
    if policy_type not in POLICY_TYPES:
        raise AppException("VALIDATION_ERROR", f"未知策略类型：{policy_type}")
    if policy_type == POLICY_NODE_ACTION and not str(action_permission_code or "").strip():
        raise AppException("VALIDATION_ERROR", "节点动作策略必须指定 actionPermissionCode")
    if policy_type == POLICY_VERSION_STRATEGY and version_strategy not in VERSION_STRATEGIES:
        raise AppException("VALIDATION_ERROR", f"版本策略必须是 {VERSION_STRATEGIES} 之一")
    if len(str(reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "策略原因不少于 5 个字")
    tid = _tid(tenant_id)
    actor = _actor(user)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(WorkflowActionPolicy).where(
            WorkflowActionPolicy.tenant_id == tid,
            WorkflowActionPolicy.workflow_code == workflow_code,
            WorkflowActionPolicy.node_code == node_code,
            WorkflowActionPolicy.policy_type == policy_type,
            WorkflowActionPolicy.is_deleted.is_(False))).first()
        if row is not None:
            _check_version(row, expected_version)
            if row.status == STATUS_ACTIVE:
                raise AppException("DATA_CONFLICT", "生效中的策略不能直接修改，请先下线（retire）")
            row.action_permission_code = action_permission_code
            row.version_strategy = version_strategy
            row.reason = reason
            row.status = STATUS_DRAFT
            row.submitted_by = None
            row.submitted_at = None
            row.reviewed_by = None
            row.reviewed_at = None
            row.updated_by = actor
            row.version = int(row.version or 0) + 1
        else:
            row = WorkflowActionPolicy(
                tenant_id=tid, workflow_code=workflow_code, node_code=node_code,
                policy_type=policy_type, status=STATUS_DRAFT,
                action_permission_code=action_permission_code, version_strategy=version_strategy,
                reason=reason, created_by=actor, updated_by=actor)
            db.add(row)
        db.commit()
        policy_id = int(row.id)
    except AppException:
        db.rollback()
        raise
    finally:
        db.close()
    from app.services import audit_log

    audit_log.record("WORKFLOW_POLICY_DRAFT_SAVED", f"workflow-policy:{workflow_code}:{node_code}",
                     detail={"reason": reason, "policyType": policy_type, "moduleCode": "systemAdmin"})
    return get_draft(workflow_code, node_code=node_code, policy_type=policy_type, tenant_id=tid)


def submit_for_review(policy_id: int, *, expected_version: int | None = None,
                      tenant_id: int | None = None, user: dict | None = None) -> dict:
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        row = _load(db, tid, policy_id)
        _check_version(row, expected_version)
        if row.status != STATUS_DRAFT:
            raise AppException("DATA_CONFLICT", "只有草稿状态可以提交复核")
        row.status = STATUS_PENDING_REVIEW
        row.submitted_by = _actor(user)
        row.submitted_at = _now()
        row.version = int(row.version or 0) + 1
        db.commit()
        out = _dto(row)
    except AppException:
        db.rollback()
        raise
    finally:
        db.close()
    from app.services import audit_log

    audit_log.record("WORKFLOW_POLICY_SUBMITTED", f"workflow-policy:{policy_id}",
                     detail={"moduleCode": "systemAdmin"})
    return out


def activate(policy_id: int, *, reason: str, self_review_ack: str = "",
            expected_version: int | None = None, tenant_id: int | None = None,
            user: dict | None = None) -> dict:
    """激活：fail-closed 自复核——只有能确证复核人不是提交人才放行（复用阶段2 SYS-09 的教训）。"""
    if len(str(reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "激活原因不少于 5 个字")
    tid = _tid(tenant_id)
    reviewer = _actor(user)
    db = get_sessionmaker()()
    try:
        row = _load(db, tid, policy_id)
        _check_version(row, expected_version)
        if row.status != STATUS_PENDING_REVIEW:
            raise AppException("DATA_CONFLICT", "只有待复核状态可以激活")
        is_self_review = reviewer is not None and row.submitted_by is not None \
            and int(reviewer) == int(row.submitted_by)
        if is_self_review and self_review_ack != SELF_REVIEW_TEXT:
            raise AppException(
                "VALIDATION_ERROR",
                f'提交人与激活人相同，需额外确认：请传 selfReviewAck="{SELF_REVIEW_TEXT}"')
        # 同一 (workflow_code, node_code, policy_type) 只允许一条 ACTIVE：先把旧的退役
        old_active = db.scalars(select(WorkflowActionPolicy).where(
            WorkflowActionPolicy.tenant_id == tid,
            WorkflowActionPolicy.workflow_code == row.workflow_code,
            WorkflowActionPolicy.node_code == row.node_code,
            WorkflowActionPolicy.policy_type == row.policy_type,
            WorkflowActionPolicy.status == STATUS_ACTIVE,
            WorkflowActionPolicy.id != row.id,
            WorkflowActionPolicy.is_deleted.is_(False))).first()
        if old_active is not None:
            old_active.status = STATUS_RETIRED
            old_active.retired_by = reviewer
            old_active.retired_at = _now()
            old_active.version = int(old_active.version or 0) + 1
        row.status = STATUS_ACTIVE
        row.reviewed_by = reviewer
        row.reviewed_at = _now()
        row.reason = reason
        row.version = int(row.version or 0) + 1
        db.commit()
        out = _dto(row)
    except AppException:
        db.rollback()
        raise
    finally:
        db.close()
    from app.services import audit_log

    audit_log.record("WORKFLOW_POLICY_ACTIVATED", f"workflow-policy:{policy_id}",
                     detail={"reason": reason, "workflowCode": row.workflow_code,
                             "nodeCode": row.node_code, "policyType": row.policy_type,
                             "moduleCode": "systemAdmin"})
    return out


def retire(policy_id: int, *, reason: str, expected_version: int | None = None,
          tenant_id: int | None = None, user: dict | None = None) -> dict:
    if len(str(reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "下线原因不少于 5 个字")
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        row = _load(db, tid, policy_id)
        _check_version(row, expected_version)
        if row.status not in (STATUS_ACTIVE, STATUS_PENDING_REVIEW):
            raise AppException("DATA_CONFLICT", "该策略当前状态不能下线")
        row.status = STATUS_RETIRED
        row.retired_by = _actor(user)
        row.retired_at = _now()
        row.reason = reason
        row.version = int(row.version or 0) + 1
        db.commit()
        out = _dto(row)
    except AppException:
        db.rollback()
        raise
    finally:
        db.close()
    from app.services import audit_log

    audit_log.record("WORKFLOW_POLICY_RETIRED", f"workflow-policy:{policy_id}",
                     detail={"reason": reason, "moduleCode": "systemAdmin"})
    return out


# ── 节点动作权限判定（真实数据：WorkflowNodeDefinition + WorkflowTask + WorkflowInstance）──
def _active_node_policy(db, tenant_id: int, workflow_code: str, node_code: str):
    row = db.scalars(select(WorkflowActionPolicy).where(
        WorkflowActionPolicy.tenant_id == tenant_id,
        WorkflowActionPolicy.workflow_code == workflow_code,
        WorkflowActionPolicy.node_code.in_([node_code, WORKFLOW_LEVEL_NODE]),
        WorkflowActionPolicy.policy_type == POLICY_NODE_ACTION,
        WorkflowActionPolicy.status == STATUS_ACTIVE,
        WorkflowActionPolicy.is_deleted.is_(False),
    ).order_by(WorkflowActionPolicy.node_code.desc())).first()  # 节点级优先于流程级（''排最后）
    return row


def action_permission_required(workflow_code: str, node_code: str, *,
                               tenant_id: int | None = None) -> str | None:
    """给真实执行路径（db_service.act_task）用的轻量查询：这个节点当前需要哪个越权许可码。

    没有 ACTIVE 策略返回 None——调用方按 None 理解为"维持旧行为，不额外收紧"。
    """
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        policy = _active_node_policy(db, tid, workflow_code, node_code)
        return policy.action_permission_code if policy else None
    finally:
        db.close()


def simulate(workflow_code: str, node_code: str, *, actor_user_id: str, actor_permissions: list[str],
            task_assignee_id: str, tenant_id: int | None = None) -> dict:
    """只读推演：这个人能不能代批这个节点。跟真实执行路径用同一份判定，不是另一套猜测。"""
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        policy = _active_node_policy(db, tid, workflow_code, node_code)
    finally:
        db.close()
    is_assignee = str(actor_user_id) == str(task_assignee_id)
    is_true_super = "*" in (actor_permissions or [])
    has_wildcard = is_true_super or "approval.manage" in (actor_permissions or [])
    if is_assignee:
        return {"allowed": True, "reason": "本人为该节点 assignee", "policyActive": policy is not None}
    if is_true_super:
        # `*` 是真超管通配，跟真实执行路径 _can_manage_all_approvals 一致：不受节点策略约束。
        return {"allowed": True, "reason": "持有通配权限 *（真超管，不受节点策略约束）",
                "policyActive": policy is not None}
    if policy is None:
        return {"allowed": has_wildcard,
                "reason": "有通配审批权限（未激活节点策略，维持旧行为）" if has_wildcard else "既非 assignee 也无通配权限",
                "policyActive": False}
    has_action_perm = policy.action_permission_code in (actor_permissions or [])
    return {
        "allowed": has_action_perm,
        "reason": (f"持有节点动作权限 {policy.action_permission_code}" if has_action_perm
                  else f"节点策略已激活：仅 assignee 或持有 {policy.action_permission_code} 的人可代批，"
                       f"通配页面权限（approval.manage/*）在此节点不再生效"),
        "policyActive": True,
        "requiredActionPermission": policy.action_permission_code,
    }


# ── 版本变更策略（配合 update_workflow 调用）──────────────────────────────────
def version_strategy_for(workflow_code: str, *, tenant_id: int | None = None) -> str:
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(WorkflowActionPolicy).where(
            WorkflowActionPolicy.tenant_id == tid,
            WorkflowActionPolicy.workflow_code == workflow_code,
            WorkflowActionPolicy.node_code == WORKFLOW_LEVEL_NODE,
            WorkflowActionPolicy.policy_type == POLICY_VERSION_STRATEGY,
            WorkflowActionPolicy.status == STATUS_ACTIVE,
            WorkflowActionPolicy.is_deleted.is_(False))).first()
        return row.version_strategy if row else STRATEGY_DYNAMIC
    finally:
        db.close()


def guard_definition_change(db, tenant_id: int, workflow_code: str, *, reason: str,
                            from_version: str, to_version: str, actor: int | None) -> None:
    """在 update_workflow 真正落库前调用；同一 db 会话内完成，失败即整体回滚。

    不查询/写入调用方已经打开的事务之外的东西，只做三件事：
    数一下这条流程当前有多少 RUNNING 实例、按策略决定放行/拒绝、MIGRATE 时留痕。
    """
    from app.models import WorkflowInstance

    strategy = version_strategy_for(workflow_code, tenant_id=tenant_id)
    if strategy == STRATEGY_DYNAMIC:
        return
    running = db.scalars(select(WorkflowInstance).where(
        WorkflowInstance.tenant_id == tenant_id,
        WorkflowInstance.workflow_code == workflow_code,
        WorkflowInstance.status == "RUNNING",
        WorkflowInstance.is_deleted.is_(False))).all()
    if not running:
        return
    if strategy == STRATEGY_SNAPSHOT:
        raise AppException(
            "DATA_CONFLICT",
            f"该流程有 {len(running)} 个在途实例，版本策略为 SNAPSHOT，拒绝修改定义；"
            "请等在途实例结束，或将策略改为 MIGRATE 后再修改")
    # MIGRATE：允许改，但必须留痕
    db.add(WorkflowVersionMigrationEvent(
        tenant_id=tenant_id, workflow_code=workflow_code,
        from_definition_version=from_version, to_definition_version=to_version,
        affected_instance_count=len(running),
        affected_instance_ids_json=[int(r.id) for r in running],
        reason=reason, created_by=actor, updated_by=actor))


# ── 人工推进（异常处理）───────────────────────────────────────────────────────
def force_advance_task(task_id: int, *, action: str, reason: str,
                       tenant_id: int | None = None, user: dict | None = None) -> dict:
    """管理员强制推进一个卡住的审批任务。必须有理由，必须留审计——这是 SYS14-T04 的落点。

    不复制审批服务的业务副作用（消息联动等），只做状态机本身的强制推进；
    真实业务副作用仍由原审批服务负责，管理员人工推进只解卡，不代替业务判断。
    """
    action = str(action or "").strip().upper()
    if action not in ("APPROVED", "REJECTED", "CANCELLED"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVED/REJECTED/CANCELLED")
    if len(str(reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "人工推进必须填写理由（不少于 5 个字）")
    tid = _tid(tenant_id)
    actor = _actor(user)
    from app.models import WorkflowInstance, WorkflowTask

    db = get_sessionmaker()()
    try:
        task = db.scalars(select(WorkflowTask).where(
            WorkflowTask.id == int(task_id), WorkflowTask.tenant_id == tid,
            WorkflowTask.is_deleted.is_(False))).first()
        if task is None:
            raise AppException("DATA_NOT_FOUND", "审批任务不存在")
        if task.status != "PENDING":
            raise AppException("DATA_CONFLICT", "任务已不是待处理状态，无需人工推进")
        before_status = task.status
        task.status = action
        task.action_reason = f"[人工推进] {reason}"
        task.acted_at = _now()
        task.version = int(task.version or 0) + 1
        instance = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.id == task.instance_id, WorkflowInstance.tenant_id == tid,
            WorkflowInstance.is_deleted.is_(False))).first()
        if instance is not None and action in ("APPROVED", "REJECTED"):
            instance.status = action
            instance.version = int(instance.version or 0) + 1
        db.commit()
        out = {"taskId": str(task.id), "beforeStatus": before_status, "afterStatus": action,
              "instanceId": str(task.instance_id)}
    except AppException:
        db.rollback()
        raise
    finally:
        db.close()
    from app.services import audit_log

    audit_log.record("WORKFLOW_TASK_FORCE_ADVANCED", f"workflow-task:{task_id}",
                     detail={"reason": reason, "action": action, "beforeStatus": before_status,
                             "moduleCode": "systemAdmin"})
    return out


# ── 首屏结论 ─────────────────────────────────────────────────────────────────
def governance_overview(*, tenant_id: int | None = None) -> dict:
    """启用流程、无审批人、节点冲突、在途异常、人工推进和版本分布——SYS-14 首屏结论。"""
    from app.models import Role, UserRole, WorkflowDefinition, WorkflowInstance, WorkflowNodeDefinition

    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        definitions = db.scalars(select(WorkflowDefinition).where(
            WorkflowDefinition.tenant_id == tid, WorkflowDefinition.is_deleted.is_(False))).all()
        enabled = [d for d in definitions if d.status == "ENABLED" and d.policy_confirmed]
        version_distribution: dict[str, int] = {}
        no_approver: list[dict] = []
        for d in definitions:
            version_distribution[d.definition_version] = version_distribution.get(d.definition_version, 0) + 1
            nodes = db.scalars(select(WorkflowNodeDefinition).where(
                WorkflowNodeDefinition.tenant_id == tid,
                WorkflowNodeDefinition.workflow_definition_id == d.id,
                WorkflowNodeDefinition.is_deleted.is_(False))).all()
            for node in nodes:
                role = db.scalars(select(Role).where(
                    Role.tenant_id == tid, Role.role_code == node.approver_role_code,
                    Role.is_deleted.is_(False), Role.status == "ACTIVE")).first()
                members = 0
                if role is not None:
                    from sqlalchemy import func

                    members = int(db.scalar(select(func.count(UserRole.id)).where(
                        UserRole.tenant_id == tid, UserRole.role_id == role.id,
                        UserRole.is_deleted.is_(False), UserRole.status == "ACTIVE")) or 0)
                if role is None or members == 0:
                    no_approver.append({"workflowCode": d.workflow_code, "nodeCode": node.node_code,
                                        "roleCode": node.approver_role_code})
        running = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.tenant_id == tid, WorkflowInstance.status == "RUNNING",
            WorkflowInstance.is_deleted.is_(False))).all()
        stale_cutoff = _now().timestamp() - 30 * 86400
        stale = [r for r in running if r.updated_at and r.updated_at.timestamp() < stale_cutoff]
        active_policies = db.scalars(select(WorkflowActionPolicy).where(
            WorkflowActionPolicy.tenant_id == tid, WorkflowActionPolicy.status == STATUS_ACTIVE,
            WorkflowActionPolicy.is_deleted.is_(False))).all()
        return {
            "enabledWorkflows": len(enabled), "totalWorkflows": len(definitions),
            "noApproverNodes": no_approver, "runningInstances": len(running),
            "staleRunningInstances": len(stale),
            "versionDistribution": version_distribution,
            "activeNodeActionPolicies": sum(1 for p in active_policies if p.policy_type == POLICY_NODE_ACTION),
            "activeVersionStrategies": sum(1 for p in active_policies if p.policy_type == POLICY_VERSION_STRATEGY),
        }
    finally:
        db.close()
