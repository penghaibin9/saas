"""审批模板真实化；审批导出统一委托 approval_export_service。"""
from __future__ import annotations

import uuid
from datetime import datetime

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
from app.db.session import db_enabled
from app.services.message_identity import resolve_message_user_id


def _require_db():
    if not db_enabled():
        raise AppException(
            "APPROVAL_BACKEND_UNAVAILABLE",
            "审批模板需要真实数据库，当前不可回落演示数据",
            http_status=503,
        )


def _user(user=None):
    return user or get_current_user_ctx() or {}


def _tid():
    try:
        value = int(current_tenant_id() or 0)
    except (TypeError, ValueError):
        value = 0
    if not value:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文", http_status=400)
    return value


def _require_manage(user=None):
    u = _user(user)
    # 流程定义会影响全校后续业务发起；即使其他角色拥有审批办理权限，也不能修改。
    # 租户来源只取认证/上下文，客户端没有可传入 tenantId 的入口。
    role = str(u.get("currentRoleCode") or u.get("userType") or "").upper()
    if role != "SCHOOL_ADMIN" or not has_permission(u, "approval.manage"):
        raise no_permission("仅学校管理员可维护流程模板")


def _nodes(db, definition_id, *, active_only=True):
    from sqlalchemy import select
    from app.models import WorkflowNodeDefinition

    cond = [
        WorkflowNodeDefinition.tenant_id == _tid(),
        WorkflowNodeDefinition.workflow_definition_id == definition_id,
        WorkflowNodeDefinition.is_deleted.is_(False),
    ]
    if active_only:
        cond.append(WorkflowNodeDefinition.status == "ACTIVE")
    return db.scalars(select(WorkflowNodeDefinition).where(*cond)
                      .order_by(WorkflowNodeDefinition.sequence_no, WorkflowNodeDefinition.id)).all()


def _snapshot(definition, nodes) -> dict:
    return {
        "definitionVersion": str(definition.definition_version),
        "name": definition.workflow_name,
        "bizType": definition.source_biz_type,
        "status": definition.status,
        "capturedAt": datetime.utcnow().isoformat(timespec="seconds"),
        "nodes": [{
            "nodeCode": x.node_code,
            "name": x.node_name,
            "role": x.approver_role_code,
            "sla": x.timeout_hours,
            "sequence": x.sequence_no,
            "status": x.status,
        } for x in nodes],
    }


def _store_snapshot(definition, nodes, *, preserve_previous=True) -> None:
    existing = definition.policy_snapshot_json if isinstance(definition.policy_snapshot_json, dict) else {}
    history = list(existing.get("history") or [])
    current = existing.get("current")
    if preserve_previous and current:
        history.append(current)
    definition.policy_snapshot_json = {
        "current": _snapshot(definition, nodes),
        "history": history[-20:],
        **{
            key: existing[key]
            for key in ("draftOfWorkflowCode", "baseDefinitionId")
            if existing.get(key) not in (None, "")
        },
    }


def _row(db, definition):
    ns = _nodes(db, definition.id)
    snap = definition.policy_snapshot_json if isinstance(definition.policy_snapshot_json, dict) else {}
    return {
        "id": str(definition.id),
        "workflowCode": definition.workflow_code,
        "name": definition.workflow_name,
        "sourceModule": definition.source_module,
        "bizType": definition.source_biz_type,
        "status": (
            "ENABLED" if definition.status == "ENABLED"
            else "VOIDED" if definition.status == "DISABLED"
            else definition.status
        ),
        "definitionVersion": definition.definition_version,
        "rowVersion": definition.version,
        "policyConfirmed": bool(definition.policy_confirmed),
        "updatedBy": str(definition.updated_by or definition.created_by or ""),
        "updatedAt": definition.updated_at.isoformat(timespec="seconds") if definition.updated_at else "",
        "voidReason": definition.description if definition.status == "DISABLED" else "",
        "draftOfWorkflowCode": str(snap.get("draftOfWorkflowCode") or ""),
        "versionHistory": list(snap.get("history") or []),
        "nodes": [{
            "name": x.node_name,
            "role": x.approver_role_code,
            "sla": x.timeout_hours,
            "nodeCode": x.node_code,
        } for x in ns],
    }


def get_template(template_id, *, user=None):
    _require_db()
    _require_manage(user)
    from sqlalchemy import select
    from app.models import WorkflowDefinition
    from app.services import db_service

    with db_service.session() as db:
        definition = db.scalars(select(WorkflowDefinition).where(
            WorkflowDefinition.id == int(template_id),
            WorkflowDefinition.tenant_id == _tid(),
            WorkflowDefinition.is_deleted.is_(False),
        )).first()
        if not definition:
            raise not_found("审批模板不存在")
        return _row(db, definition)


def list_templates(page, page_size, *, user=None, keyword=None, biz_type=None, status=None):
    _require_db()
    _require_manage(user)
    from sqlalchemy import func, select
    from app.models import WorkflowDefinition
    from app.services import db_service

    # 发布时为在途实例保留的 ARCHIVED 行是运行时历史版本，不作为可维护模板展示。
    cond = [
        WorkflowDefinition.tenant_id == _tid(),
        WorkflowDefinition.is_deleted.is_(False),
        WorkflowDefinition.status != "ARCHIVED",
    ]
    if keyword:
        cond.append(WorkflowDefinition.workflow_name.like(f"%{keyword.strip()}%"))
    if biz_type:
        cond.append(WorkflowDefinition.source_biz_type == biz_type)
    if status:
        cond.append(WorkflowDefinition.status == ("DISABLED" if status == "VOIDED" else status))
    with db_service.session() as db:
        total = int(db.scalar(select(func.count()).select_from(WorkflowDefinition).where(*cond)) or 0)
        rows = db.scalars(select(WorkflowDefinition).where(*cond)
                          .order_by(WorkflowDefinition.updated_at.desc(), WorkflowDefinition.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        return [_row(db, x) for x in rows], total


def _validate_nodes(nodes):
    if not nodes:
        raise AppException("VALIDATION_ERROR", "至少配置 1 个审批节点")
    out = []
    codes = set()
    for idx, node in enumerate(nodes, start=1):
        name = str(node.get("name") or "").strip()
        role = str(node.get("role") or "").strip()
        try:
            sla = int(node.get("sla") or 0)
        except (TypeError, ValueError):
            sla = 0
        code = str(node.get("nodeCode") or f"NODE_{idx:02d}").strip().upper()
        if not name or not role or sla <= 0:
            raise AppException("VALIDATION_ERROR", f"第 {idx} 个节点信息不完整")
        if not code:
            raise AppException("VALIDATION_ERROR", f"第 {idx} 个节点编码为空")
        if code in codes:
            raise AppException("VALIDATION_ERROR", f"节点编码 {code} 重复")
        codes.add(code)
        out.append({"name": name, "role": role, "sla": sla, "nodeCode": code})
    return out


def _assert_node_roles(db, nodes):
    """责任角色必须是当前学校的有效角色，不能由浏览器任意写入一个角色编码。"""
    from sqlalchemy import select
    from app.models import Role

    codes = {str(node["role"]).upper() for node in nodes}
    found = set(db.scalars(select(Role.role_code).where(
        Role.tenant_id == _tid(), Role.role_code.in_(codes),
        Role.status.in_(("ACTIVE", "active")), Role.is_deleted.is_(False),
    )).all())
    missing = sorted(codes - found)
    if missing:
        raise AppException("VALIDATION_ERROR", f"责任角色不存在或未启用：{', '.join(missing)}")


def create_template(payload, *, user=None):
    _require_db()
    _require_manage(user)
    name = str(payload.get("name") or "").strip()
    biz_type = str(payload.get("bizType") or "").strip()
    nodes = _validate_nodes(payload.get("nodes") or [])
    if not name or not biz_type:
        raise AppException("VALIDATION_ERROR", "模板名称和适用业务必填")
    from app.models import WorkflowDefinition, WorkflowNodeDefinition
    from app.services import db_service
    from app.services import mock_audit_service as audit

    uid = resolve_message_user_id(_user(user)) or None
    code = f"APPROVAL_{biz_type}_{uuid.uuid4().hex[:8].upper()}"
    with db_service.session() as db:
        _assert_node_roles(db, nodes)
        definition = WorkflowDefinition(
            tenant_id=_tid(),
            workflow_code=code,
            workflow_name=name,
            source_module="approval",
            source_biz_type=biz_type,
            definition_version="1",
            status="DRAFT",
            policy_confirmed=False,
            policy_snapshot_json={},
            source_profile="MANUAL",
            installed_project_id=0,
            created_by=uid,
            updated_by=uid,
        )
        db.add(definition)
        db.flush()
        created_nodes = []
        for idx, node in enumerate(nodes, start=1):
            row = WorkflowNodeDefinition(
                tenant_id=_tid(),
                workflow_definition_id=definition.id,
                node_code=node["nodeCode"],
                node_name=node["name"],
                sequence_no=idx,
                approver_role_code=node["role"],
                timeout_hours=node["sla"],
                status="ACTIVE",
                created_by=uid,
                updated_by=uid,
            )
            db.add(row)
            created_nodes.append(row)
        db.flush()
        _store_snapshot(definition, created_nodes, preserve_previous=False)
        audit.record_critical(
            "审批模板新增",
            method="POST", path="/api/v1/approvals/templates",
            status_code=200, target_type="approval-template", target_id=str(definition.id),
            detail={"workflowCode": code, "bizType": biz_type, "definitionVersion": "1", "status": "DRAFT"}, db=db,
        )
        db.commit()
        db.refresh(definition)
        return _row(db, definition)


def update_template(template_id, payload, *, user=None, expected_version=0):
    _require_db()
    _require_manage(user)
    name = str(payload.get("name") or "").strip()
    biz_type = str(payload.get("bizType") or "").strip()
    nodes = _validate_nodes(payload.get("nodes") or [])
    if not name or not biz_type:
        raise AppException("VALIDATION_ERROR", "模板名称和适用业务必填")
    from sqlalchemy import select
    from app.models import WorkflowDefinition, WorkflowNodeDefinition
    from app.services import db_service
    from app.services import mock_audit_service as audit

    uid = resolve_message_user_id(_user(user)) or None
    with db_service.session() as db:
        _assert_node_roles(db, nodes)
        definition = db.scalars(select(WorkflowDefinition).where(
            WorkflowDefinition.id == int(template_id),
            WorkflowDefinition.tenant_id == _tid(),
            WorkflowDefinition.is_deleted.is_(False),
        ).with_for_update()).first()
        if not definition:
            raise not_found("审批模板不存在")
        if definition.status not in {"DRAFT", "PENDING_CONFIRMATION"}:
            raise AppException("DATA_CONFLICT", "已发布模板请先创建新版本草稿再编辑", http_status=409)
        if int(definition.version or 0) != int(expected_version):
            raise AppException("APPROVAL_VERSION_CONFLICT", "模板已被他人修改，请刷新后重试", http_status=409)

        existing_rows = db.scalars(select(WorkflowNodeDefinition).where(
            WorkflowNodeDefinition.tenant_id == _tid(),
            WorkflowNodeDefinition.workflow_definition_id == definition.id,
        ).with_for_update()).all()
        existing = {str(x.node_code).upper(): x for x in existing_rows}
        active_codes = set()
        final_nodes = []
        for idx, node in enumerate(nodes, start=1):
            code = node["nodeCode"]
            active_codes.add(code)
            row = existing.get(code)
            if row is None:
                row = WorkflowNodeDefinition(
                    tenant_id=_tid(),
                    workflow_definition_id=definition.id,
                    node_code=code,
                    created_by=uid,
                )
                db.add(row)
            else:
                row.is_deleted = False
                row.version = int(row.version or 0) + 1
            row.node_name = node["name"]
            row.sequence_no = idx
            row.approver_role_code = node["role"]
            row.timeout_hours = node["sla"]
            row.status = "ACTIVE"
            row.updated_by = uid
            final_nodes.append(row)

        for code, row in existing.items():
            if code not in active_codes:
                row.status = "DISABLED"
                row.version = int(row.version or 0) + 1
                row.updated_by = uid

        definition.workflow_name = name
        definition.source_biz_type = biz_type
        # 草稿保存只推进 row.version 以保护并发；definition_version 是发布版本，
        # 只在从已发布模板创建下一版草稿时推进一次。
        definition.version = int(definition.version or 0) + 1
        definition.updated_by = uid
        db.flush()
        _store_snapshot(definition, final_nodes, preserve_previous=True)
        audit.record_critical(
            "审批模板更新",
            method="PUT", path=f"/api/v1/approvals/templates/{template_id}",
            status_code=200, target_type="approval-template", target_id=str(template_id),
            detail={
                "definitionVersion": definition.definition_version,
                "activeNodeCodes": [x.node_code for x in final_nodes],
            }, db=db,
        )
        db.commit()
        db.refresh(definition)
        return _row(db, definition)


def _draft_code(workflow_code: str) -> str:
    base = str(workflow_code or "").strip().upper()
    suffix = f"__DRAFT_{uuid.uuid4().hex[:8].upper()}"
    return f"{base[:100 - len(suffix)]}{suffix}"


def _archive_code(workflow_code: str, definition_version: str) -> str:
    base = str(workflow_code or "").strip().upper()
    suffix = f"__ARCHIVE_V{str(definition_version or '0')[:12]}_{uuid.uuid4().hex[:6].upper()}"
    return f"{base[:100 - len(suffix)]}{suffix}"


def _next_definition_version(value: str) -> str:
    """发布版本只在创建下一版时推进；支持既有的 2026.1 形式。"""
    parts = str(value or "1").split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    except (TypeError, ValueError):
        return f"{value}.1"


def create_draft(template_id, *, user=None, expected_version=0):
    """复制已发布定义。草稿没有运行入口，发布时才成为原 workflow_code。"""
    _require_db()
    _require_manage(user)
    from sqlalchemy import select
    from app.models import WorkflowDefinition, WorkflowNodeDefinition
    from app.models.workflow_security_policy import WorkflowActionPolicy
    from app.services import db_service
    from app.services import mock_audit_service as audit

    uid = resolve_message_user_id(_user(user)) or None
    with db_service.session() as db:
        source = db.scalars(select(WorkflowDefinition).where(
            WorkflowDefinition.id == int(template_id),
            WorkflowDefinition.tenant_id == _tid(),
            WorkflowDefinition.is_deleted.is_(False),
        ).with_for_update()).first()
        if not source:
            raise not_found("审批模板不存在")
        if source.status != "ENABLED":
            raise AppException("DATA_CONFLICT", "只有已发布模板可以创建下一版草稿", http_status=409)
        if int(source.version or 0) != int(expected_version):
            raise AppException("APPROVAL_VERSION_CONFLICT", "模板已被他人修改，请刷新后重试", http_status=409)
        source_nodes = _nodes(db, source.id, active_only=False)
        draft = WorkflowDefinition(
            tenant_id=_tid(), workflow_code=_draft_code(source.workflow_code),
            workflow_name=source.workflow_name, source_module=source.source_module,
            source_biz_type=source.source_biz_type,
            definition_version=_next_definition_version(source.definition_version),
            status="DRAFT", policy_confirmed=False,
            timeout_hours=source.timeout_hours, allow_transfer=source.allow_transfer,
            allow_reject=source.allow_reject, allow_withdraw=source.allow_withdraw,
            starter_role_codes_json=list(source.starter_role_codes_json or []),
            cc_role_codes_json=list(source.cc_role_codes_json or []),
            policy_snapshot_json={"draftOfWorkflowCode": source.workflow_code, "baseDefinitionId": str(source.id)},
            source_profile=source.source_profile, installed_project_id=source.installed_project_id,
            description=source.description, created_by=uid, updated_by=uid,
        )
        db.add(draft); db.flush()
        copied_nodes = []
        for node in source_nodes:
            copied = WorkflowNodeDefinition(
                tenant_id=_tid(), workflow_definition_id=draft.id, node_code=node.node_code,
                node_name=node.node_name, sequence_no=node.sequence_no,
                approver_role_code=node.approver_role_code, assignee_strategy=node.assignee_strategy,
                data_scope_code=node.data_scope_code, timeout_hours=node.timeout_hours,
                condition_json=dict(node.condition_json or {}), status=node.status,
                created_by=uid, updated_by=uid,
            )
            db.add(copied); copied_nodes.append(copied)
        for policy in db.scalars(select(WorkflowActionPolicy).where(
            WorkflowActionPolicy.tenant_id == _tid(),
            WorkflowActionPolicy.workflow_code == source.workflow_code,
            WorkflowActionPolicy.is_deleted.is_(False),
        )).all():
            db.add(WorkflowActionPolicy(
                tenant_id=_tid(), workflow_code=draft.workflow_code, node_code=policy.node_code,
                policy_type=policy.policy_type, status=policy.status,
                action_permission_code=policy.action_permission_code,
                version_strategy=policy.version_strategy, reason=policy.reason,
                submitted_by=uid, submitted_at=datetime.utcnow(), created_by=uid, updated_by=uid,
            ))
        db.flush(); _store_snapshot(draft, copied_nodes, preserve_previous=False)
        audit.record_critical("审批模板创建草稿", method="POST", path=f"/api/v1/approvals/templates/{template_id}/draft",
                              status_code=200, target_type="approval-template", target_id=str(draft.id),
                              detail={"sourceTemplateId": str(source.id), "sourceWorkflowCode": source.workflow_code}, db=db)
        db.commit(); db.refresh(draft)
        return _row(db, draft)


def publish_draft(template_id, *, user=None, expected_version=0):
    """原 code 留给新版本；在途实例及其策略转入历史 code，故仍按旧定义运行。"""
    _require_db()
    _require_manage(user)
    from sqlalchemy import select
    from app.models import WorkflowDefinition, WorkflowInstance
    from app.models.workflow_security_policy import WorkflowActionPolicy, WorkflowVersionMigrationEvent
    from app.services import db_service
    from app.services import mock_audit_service as audit

    uid = resolve_message_user_id(_user(user)) or None
    with db_service.session() as db:
        draft = db.scalars(select(WorkflowDefinition).where(
            WorkflowDefinition.id == int(template_id), WorkflowDefinition.tenant_id == _tid(),
            WorkflowDefinition.is_deleted.is_(False),
        ).with_for_update()).first()
        if not draft:
            raise not_found("审批模板不存在")
        if draft.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "仅草稿可以发布", http_status=409)
        if int(draft.version or 0) != int(expected_version):
            raise AppException("APPROVAL_VERSION_CONFLICT", "草稿已被他人修改，请刷新后重试", http_status=409)
        metadata = draft.policy_snapshot_json if isinstance(draft.policy_snapshot_json, dict) else {}
        live_code = str(metadata.get("draftOfWorkflowCode") or "").strip()
        # 独立新建模板没有旧版本和在途实例，直接启用其唯一 workflow_code。
        if not live_code:
            draft.status = "ENABLED"
            draft.policy_confirmed = True
            draft.policy_confirmed_by = uid
            draft.policy_confirmed_at = datetime.utcnow()
            draft.version = int(draft.version or 0) + 1
            draft.updated_by = uid
            audit.record_critical("审批模板首次发布", method="POST", path=f"/api/v1/approvals/templates/{template_id}/publish",
                                  status_code=200, target_type="approval-template", target_id=str(draft.id),
                                  detail={"workflowCode": draft.workflow_code, "definitionVersion": draft.definition_version}, db=db)
            db.commit(); db.refresh(draft)
            return _row(db, draft)
        source = db.scalars(select(WorkflowDefinition).where(
            WorkflowDefinition.tenant_id == _tid(), WorkflowDefinition.workflow_code == live_code,
            WorkflowDefinition.status == "ENABLED", WorkflowDefinition.is_deleted.is_(False),
        ).with_for_update()).first()
        if not source:
            raise AppException("DATA_CONFLICT", "草稿对应的已发布版本不存在，请重新创建草稿", http_status=409)
        archive_code = _archive_code(live_code, source.definition_version)
        # The unique code is moved in two steps. Instances must move with the old
        # definition before the new draft receives the public runtime code.
        source.workflow_code = archive_code
        source.status = "ARCHIVED"
        source.updated_by = uid
        db.flush()
        instances = db.scalars(select(WorkflowInstance).where(
            WorkflowInstance.tenant_id == _tid(), WorkflowInstance.workflow_code == live_code,
            WorkflowInstance.is_deleted.is_(False),
        ).with_for_update()).all()
        for instance in instances:
            instance.workflow_code = archive_code
            instance.updated_by = uid
        for policy in db.scalars(select(WorkflowActionPolicy).where(
            WorkflowActionPolicy.tenant_id == _tid(), WorkflowActionPolicy.workflow_code == live_code,
            WorkflowActionPolicy.is_deleted.is_(False),
        ).with_for_update()).all():
            policy.workflow_code = archive_code
            policy.updated_by = uid
        draft_code = draft.workflow_code
        draft.workflow_code = live_code
        draft.status = "ENABLED"
        draft.policy_confirmed = True
        draft.policy_confirmed_by = uid
        draft.policy_confirmed_at = datetime.utcnow()
        draft.version = int(draft.version or 0) + 1
        draft.updated_by = uid
        for policy in db.scalars(select(WorkflowActionPolicy).where(
            WorkflowActionPolicy.tenant_id == _tid(), WorkflowActionPolicy.workflow_code == draft_code,
            WorkflowActionPolicy.is_deleted.is_(False),
        ).with_for_update()).all():
            policy.workflow_code = live_code
            policy.updated_by = uid
        db.add(WorkflowVersionMigrationEvent(
            tenant_id=_tid(), workflow_code=live_code,
            from_definition_version=source.definition_version, to_definition_version=draft.definition_version,
            affected_instance_count=len(instances), affected_instance_ids_json=[int(x.id) for x in instances],
            reason="发布新版本：在途实例保留旧定义", created_by=uid, updated_by=uid,
        ))
        audit.record_critical("审批模板发布新版本", method="POST", path=f"/api/v1/approvals/templates/{template_id}/publish",
                              status_code=200, target_type="approval-template", target_id=str(draft.id),
                              detail={"workflowCode": live_code, "archivedWorkflowCode": archive_code,
                                      "preservedRunningInstanceCount": len(instances)}, db=db)
        db.commit(); db.refresh(draft)
        return _row(db, draft)


def void_template(template_id, reason, *, user=None, expected_version=0):
    _require_db()
    _require_manage(user)
    text = str(reason or "").strip()
    if len(text) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因不少于 5 个字")
    from sqlalchemy import select
    from app.models import WorkflowDefinition
    from app.services import db_service
    from app.services import mock_audit_service as audit

    uid = resolve_message_user_id(_user(user)) or None
    with db_service.session() as db:
        definition = db.scalars(select(WorkflowDefinition).where(
            WorkflowDefinition.id == int(template_id),
            WorkflowDefinition.tenant_id == _tid(),
            WorkflowDefinition.is_deleted.is_(False),
        ).with_for_update()).first()
        if not definition:
            raise not_found("审批模板不存在")
        if int(definition.version or 0) != int(expected_version):
            raise AppException("APPROVAL_VERSION_CONFLICT", "模板已被他人修改，请刷新后重试", http_status=409)
        if definition.status == "DISABLED":
            raise AppException("APPROVAL_TEMPLATE_VOIDED", "模板已经作废，请刷新", http_status=409)
        definition.status = "DISABLED"
        definition.description = text
        definition.version = int(definition.version or 0) + 1
        definition.updated_by = uid
        _store_snapshot(definition, _nodes(db, definition.id), preserve_previous=True)
        audit.record_critical(
            "审批模板作废",
            method="POST", path=f"/api/v1/approvals/templates/{template_id}/void",
            status_code=200, target_type="approval-template", target_id=str(template_id),
            detail={"reason": text, "definitionVersion": definition.definition_version}, db=db,
        )
        db.commit()
        db.refresh(definition)
        return _row(db, definition)


# 兼容旧内部调用点：不再维护第二套同步 Workbook / ExportTask 实现。
def create_export(scope, purpose, *, user=None):
    from app.services import approval_export_service as export_service

    return export_service.create_job(scope, purpose, user=user)


def export_file_path(task_id, *, user=None):
    raise AppException(
        "APPROVAL_EXPORT_TICKET_REQUIRED",
        "审批导出已统一使用 ExportJob + 一次性下载票据，请通过正式下载票据接口访问文件",
        http_status=409,
    )
