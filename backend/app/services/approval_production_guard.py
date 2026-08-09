"""PR #52 pre-merge production guard for approval execution.

Keep the existing approval runtime as the single business implementation, but close
production-only authorization gaps that must be evaluated against persisted workflow
configuration:

* TRANSFER is allowed only when the workflow definition explicitly allows transfer.
* The transfer target must hold the current node's configured approver role.
* REJECT respects ``WorkflowDefinition.allow_reject``.
* ``allowedActions`` is projected from the same persisted flags so clients do not
  advertise actions that the server will refuse.

The installer mutates the already imported ``approval_runtime_service`` module. This
keeps batch processing safe as well: its global ``transfer`` / ``reject`` lookups resolve
to the guarded functions after installation.
"""
from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException, no_permission, not_found


def _load_policy(db, task, inst, tenant_id: int):
    from sqlalchemy import select
    from app.models import WorkflowDefinition, WorkflowNodeDefinition

    definition = db.scalars(select(WorkflowDefinition).where(
        WorkflowDefinition.tenant_id == tenant_id,
        WorkflowDefinition.workflow_code == inst.workflow_code,
        WorkflowDefinition.is_deleted.is_(False),
    )).first()
    if not definition:
        return None, None
    node = db.scalars(select(WorkflowNodeDefinition).where(
        WorkflowNodeDefinition.tenant_id == tenant_id,
        WorkflowNodeDefinition.workflow_definition_id == definition.id,
        WorkflowNodeDefinition.node_code == (task.node_code or ""),
        WorkflowNodeDefinition.is_deleted.is_(False),
    )).first()
    return definition, node


def _action_flags(definition, node) -> dict[str, bool]:
    """Return persisted action switches. Missing transfer policy is fail-closed."""
    return {
        "REJECT": True if definition is None else bool(definition.allow_reject),
        "TRANSFER": bool(
            definition is not None
            and definition.allow_transfer
            and node is not None
            and str(node.status or "").upper() == "ACTIVE"
            and str(node.approver_role_code or "").strip()
        ),
    }


def _assert_transfer_policy(definition, node) -> str:
    flags = _action_flags(definition, node)
    if not flags["TRANSFER"]:
        if definition is not None and not bool(definition.allow_transfer):
            raise no_permission("当前流程已禁止转办")
        raise no_permission("当前审批节点缺少可验证的转办责任角色，禁止转办")
    return str(node.approver_role_code).strip()


def _assert_target_role(db, *, tenant_id: int, target_id: int, role_code: str) -> None:
    from sqlalchemy import select
    from app.models import Role, UserRole

    membership = db.scalar(select(UserRole.id).join(
        Role, Role.id == UserRole.role_id,
    ).where(
        UserRole.tenant_id == tenant_id,
        UserRole.user_id == target_id,
        UserRole.is_deleted.is_(False),
        UserRole.status.in_(("ACTIVE", "active")),
        Role.tenant_id == tenant_id,
        Role.role_code == role_code,
        Role.is_deleted.is_(False),
        Role.status.in_(("ACTIVE", "active")),
    ).limit(1))
    if not membership:
        raise no_permission(f"转办目标不属于当前节点责任角色 {role_code}")


def _apply_action_policy(rows: list[dict], runtime_module) -> list[dict]:
    """Remove actions disabled by persisted workflow configuration from API rows."""
    if not rows:
        return rows
    from sqlalchemy import select
    from app.models import WorkflowInstance, WorkflowTask
    from app.services import db_service

    task_ids: list[int] = []
    for row in rows:
        try:
            task_ids.append(int(row.get("taskId") or 0))
        except (TypeError, ValueError):
            continue
    task_ids = [x for x in task_ids if x]
    if not task_ids:
        return rows

    tenant_id = runtime_module._tid()
    with db_service.session() as db:
        tasks = db.scalars(select(WorkflowTask).where(
            WorkflowTask.tenant_id == tenant_id,
            WorkflowTask.id.in_(task_ids),
            WorkflowTask.is_deleted.is_(False),
        )).all()
        task_map = {int(x.id): x for x in tasks}
        instance_ids = {int(x.instance_id) for x in tasks}
        instances = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.tenant_id == tenant_id,
            WorkflowInstance.id.in_(instance_ids),
            WorkflowInstance.is_deleted.is_(False),
        )).all() if instance_ids else []
        inst_map = {int(x.id): x for x in instances}

        for row in rows:
            try:
                task = task_map.get(int(row.get("taskId") or 0))
            except (TypeError, ValueError):
                task = None
            if not task:
                continue
            inst = inst_map.get(int(task.instance_id))
            if not inst:
                row["allowedActions"] = []
                continue
            definition, node = _load_policy(db, task, inst, tenant_id)
            flags = _action_flags(definition, node)
            actions = list(row.get("allowedActions") or [])
            if not flags["REJECT"]:
                actions = [x for x in actions if x != "REJECT"]
            if not flags["TRANSFER"]:
                actions = [x for x in actions if x != "TRANSFER"]
            row["allowedActions"] = actions
    return rows


def install(runtime_module):
    if getattr(runtime_module, "_production_guard_installed", False):
        return runtime_module

    original_get_task = runtime_module.get_task
    original_list_tasks = runtime_module.list_tasks
    original_summary = runtime_module.summary
    original_reject = runtime_module.reject

    def guarded_get_task(task_id: str, *, user=None):
        row = original_get_task(task_id, user=user)
        return _apply_action_policy([row], runtime_module)[0]

    def guarded_list_tasks(page, page_size, *, user=None, keyword=None, biz_type=None):
        rows, total = original_list_tasks(
            page, page_size, user=user, keyword=keyword, biz_type=biz_type,
        )
        return _apply_action_policy(rows, runtime_module), total

    def guarded_summary(*, user=None):
        value = original_summary(user=user)
        value["overdueList"] = _apply_action_policy(
            list(value.get("overdueList") or []), runtime_module,
        )
        return value

    def guarded_reject(task_id, reason, *, user=None, version=None):
        runtime_module._require_db()
        from sqlalchemy import select
        from app.models import WorkflowInstance, WorkflowTask
        from app.services import db_service

        tenant_id = runtime_module._tid()
        with db_service.session() as db:
            task = db.scalars(select(WorkflowTask).where(
                WorkflowTask.id == int(task_id),
                WorkflowTask.tenant_id == tenant_id,
                WorkflowTask.is_deleted.is_(False),
            )).first()
            if not task:
                raise not_found("审批任务不存在")
            db_service._assert_task_assignee(db, task, user)
            inst = db.scalars(select(WorkflowInstance).where(
                WorkflowInstance.id == task.instance_id,
                WorkflowInstance.tenant_id == tenant_id,
                WorkflowInstance.is_deleted.is_(False),
            )).first()
            if not inst:
                raise not_found("审批实例不存在")
            definition, node = _load_policy(db, task, inst, tenant_id)
            if not _action_flags(definition, node)["REJECT"]:
                raise no_permission("当前流程已禁止驳回终止")
        return original_reject(task_id, reason, user=user, version=version)

    def guarded_transfer(task_id, target_user_id, comment, *, user=None, version=None):
        """Atomic transfer with workflow switch + node-role target authorization."""
        runtime_module._require_db()
        from sqlalchemy import select
        from app.core.optimistic_lock import atomic_versioned_update, require_expected_version
        from app.models import User, WorkflowInstance, WorkflowTask
        from app.services import db_service
        from app.services import mock_audit_service as audit

        require_expected_version(version)
        try:
            target_id = int(target_user_id)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "转办目标无效")

        tenant_id = runtime_module._tid()
        with db_service.session() as db:
            task = db.scalars(select(WorkflowTask).where(
                WorkflowTask.id == int(task_id),
                WorkflowTask.tenant_id == tenant_id,
                WorkflowTask.is_deleted.is_(False),
            ).with_for_update()).first()
            if not task:
                raise not_found("审批任务不存在")
            db_service._assert_task_assignee(db, task, user)
            if int(task.assignee_id) == target_id:
                raise AppException("VALIDATION_ERROR", "不能转办给当前办理人")

            inst = db.scalars(select(WorkflowInstance).where(
                WorkflowInstance.id == task.instance_id,
                WorkflowInstance.tenant_id == tenant_id,
                WorkflowInstance.is_deleted.is_(False),
            ).with_for_update()).first()
            if not inst:
                raise not_found("审批实例不存在")
            definition, node = _load_policy(db, task, inst, tenant_id)
            role_code = _assert_transfer_policy(definition, node)

            target = db.scalars(select(User).where(
                User.id == target_id,
                User.tenant_id == tenant_id,
                User.is_deleted.is_(False),
                User.status.in_(("ACTIVE", "active")),
            )).first()
            if not target or str(getattr(target, "user_type", "")).upper() == "STUDENT":
                raise AppException("VALIDATION_ERROR", "转办目标不存在、已停用或不是教职工")
            _assert_target_role(
                db, tenant_id=tenant_id, target_id=target_id, role_code=role_code,
            )

            atomic_versioned_update(
                db, WorkflowTask, entity_id=int(task_id), tenant_id=tenant_id,
                expected_version=version, expected_status="PENDING",
                values={
                    "status": "TRANSFERRED",
                    "acted_at": datetime.utcnow(),
                    "action_reason": (comment or "").strip(),
                },
            )
            new_task = WorkflowTask(
                tenant_id=tenant_id,
                instance_id=task.instance_id,
                node_code=task.node_code,
                assignee_id=target_id,
                status="PENDING",
                deadline_at=task.deadline_at,
                remark=task.remark,
            )
            db.add(new_task)
            db.flush()
            audit.record_critical(
                "审批转办", method="POST",
                path=f"/api/v1/approvals/tasks/{task_id}/transfer",
                status_code=200, target_type="approval", target_id=str(task_id),
                detail={
                    "action": "TRANSFERRED",
                    "to": str(target_id),
                    "targetRole": role_code,
                    "newTaskId": str(new_task.id),
                },
                db=db,
            )
            db.commit()
            return runtime_module._contract({
                "taskId": str(task_id),
                "status": "TRANSFERRED",
                "instanceStatus": inst.status,
                "version": int(version) + 1,
                "newTaskId": str(new_task.id),
                "transferredTo": target.real_name or target.login_name or str(target_id),
            })

    def guarded_transfer_targets(*, user=None, limit=100):
        """Return only users who are members of at least one active transferable node role."""
        runtime_module._require_db()
        from sqlalchemy import func, select
        from app.models import (
            Role,
            User,
            UserRole,
            WorkflowDefinition,
            WorkflowNodeDefinition,
            WorkflowTask,
        )
        from app.services import db_service
        from app.services.message_identity import resolve_message_user_id

        tenant_id = runtime_module._tid()
        me = resolve_message_user_id(runtime_module._user(user))
        cap = min(max(int(limit), 1), 200)
        with db_service.session() as db:
            role_codes = list(db.scalars(select(WorkflowNodeDefinition.approver_role_code).join(
                WorkflowDefinition,
                WorkflowDefinition.id == WorkflowNodeDefinition.workflow_definition_id,
            ).where(
                WorkflowNodeDefinition.tenant_id == tenant_id,
                WorkflowNodeDefinition.is_deleted.is_(False),
                WorkflowNodeDefinition.status.in_(("ACTIVE", "active")),
                WorkflowDefinition.tenant_id == tenant_id,
                WorkflowDefinition.is_deleted.is_(False),
                WorkflowDefinition.allow_transfer.is_(True),
            ).distinct()))
            role_codes = [str(x).strip() for x in role_codes if str(x or "").strip()]
            if not role_codes:
                return []

            pairs = db.execute(select(User, Role).join(
                UserRole,
                (UserRole.user_id == User.id) & (UserRole.tenant_id == User.tenant_id),
            ).join(
                Role,
                (Role.id == UserRole.role_id) & (Role.tenant_id == UserRole.tenant_id),
            ).where(
                User.tenant_id == tenant_id,
                User.is_deleted.is_(False),
                User.status.in_(("ACTIVE", "active")),
                UserRole.tenant_id == tenant_id,
                UserRole.is_deleted.is_(False),
                UserRole.status.in_(("ACTIVE", "active")),
                Role.tenant_id == tenant_id,
                Role.is_deleted.is_(False),
                Role.status.in_(("ACTIVE", "active")),
                Role.role_code.in_(role_codes),
            ).order_by(User.id, Role.id)).all()

            candidates: dict[int, tuple[object, object]] = {}
            for row, role in pairs:
                if int(row.id) == int(me or 0) or str(row.user_type or "").upper() == "STUDENT":
                    continue
                candidates.setdefault(int(row.id), (row, role))
                if len(candidates) >= cap:
                    break
            ids = list(candidates)
            pending_map = {}
            if ids:
                pending_map = {
                    int(uid): int(count)
                    for uid, count in db.execute(select(
                        WorkflowTask.assignee_id, func.count(),
                    ).where(
                        WorkflowTask.tenant_id == tenant_id,
                        WorkflowTask.is_deleted.is_(False),
                        WorkflowTask.status == "PENDING",
                        WorkflowTask.assignee_id.in_(ids),
                    ).group_by(WorkflowTask.assignee_id)).all()
                }
            return [{
                "userId": str(uid),
                "userName": row.real_name or row.login_name or str(uid),
                "roleName": role.role_name or role.role_code,
                "roleCode": role.role_code,
                "orgName": "",
                "pendingCount": pending_map.get(uid, 0),
            } for uid, (row, role) in candidates.items()]

    runtime_module.get_task = guarded_get_task
    runtime_module.list_tasks = guarded_list_tasks
    runtime_module.summary = guarded_summary
    runtime_module.reject = guarded_reject
    runtime_module.transfer = guarded_transfer
    runtime_module.transfer_targets = guarded_transfer_targets
    runtime_module._production_guard_installed = True
    return runtime_module
