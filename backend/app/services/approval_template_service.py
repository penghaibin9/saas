"""A1 审批模板与导出真实化：WorkflowDefinition/NodeDefinition + ExportTask。"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.core.permissions import has_permission
from app.core.request_context import get_trace_id
from app.db.session import db_enabled
from app.services.message_identity import resolve_message_user_id


def _require_db():
    if not db_enabled():
        raise AppException(
            "APPROVAL_BACKEND_UNAVAILABLE",
            "审批模板与导出需要真实数据库，当前不可回落演示数据",
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
    if not (has_permission(u, "*") or has_permission(u, "approval.manage")):
        raise no_permission("无审批中心管理权限（approval.manage）")


def _nodes(db, definition_id):
    from sqlalchemy import select
    from app.models import WorkflowNodeDefinition
    return db.scalars(select(WorkflowNodeDefinition).where(
        WorkflowNodeDefinition.tenant_id == _tid(),
        WorkflowNodeDefinition.workflow_definition_id == definition_id,
        WorkflowNodeDefinition.is_deleted.is_(False),
        WorkflowNodeDefinition.status == "ACTIVE",
    ).order_by(WorkflowNodeDefinition.sequence_no, WorkflowNodeDefinition.id)).all()


def _row(db, definition):
    ns = _nodes(db, definition.id)
    return {
        "id": str(definition.id),
        "name": definition.workflow_name,
        "bizType": definition.source_biz_type,
        "status": (
            "ENABLED" if definition.status == "ENABLED"
            else "VOIDED" if definition.status == "DISABLED"
            else definition.status
        ),
        "definitionVersion": definition.definition_version,
        "rowVersion": definition.version,
        "updatedBy": str(definition.updated_by or definition.created_by or ""),
        "updatedAt": definition.updated_at.isoformat(timespec="seconds") if definition.updated_at else "",
        "voidReason": definition.description if definition.status == "DISABLED" else "",
        "nodes": [{
            "name": x.node_name,
            "role": x.approver_role_code,
            "sla": x.timeout_hours,
            "nodeCode": x.node_code,
        } for x in ns],
    }


def list_templates(page, page_size, *, user=None, keyword=None, biz_type=None, status=None):
    _require_db()
    _require_manage(user)
    from sqlalchemy import func, select
    from app.models import WorkflowDefinition
    from app.services import db_service

    cond = [WorkflowDefinition.tenant_id == _tid(), WorkflowDefinition.is_deleted.is_(False)]
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
    for idx, node in enumerate(nodes, start=1):
        name = str(node.get("name") or "").strip()
        role = str(node.get("role") or "").strip()
        try:
            sla = int(node.get("sla") or 0)
        except (TypeError, ValueError):
            sla = 0
        if not name or not role or sla <= 0:
            raise AppException("VALIDATION_ERROR", f"第 {idx} 个节点信息不完整")
        out.append({
            "name": name,
            "role": role,
            "sla": sla,
            "nodeCode": str(node.get("nodeCode") or f"NODE_{idx:02d}"),
        })
    return out


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
        definition = WorkflowDefinition(
            tenant_id=_tid(),
            workflow_code=code,
            workflow_name=name,
            source_module="approval",
            source_biz_type=biz_type,
            definition_version="1",
            status="ENABLED",
            policy_confirmed=True,
            policy_confirmed_by=uid,
            policy_confirmed_at=datetime.utcnow(),
            source_profile="MANUAL",
            installed_project_id=0,
            created_by=uid,
            updated_by=uid,
        )
        db.add(definition)
        db.flush()
        for idx, node in enumerate(nodes, start=1):
            db.add(WorkflowNodeDefinition(
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
            ))
        audit.record_critical(
            "审批模板新增",
            method="POST", path="/api/v1/approvals/templates",
            status_code=200, target_type="approval-template", target_id=str(definition.id),
            detail={"workflowCode": code, "bizType": biz_type}, db=db,
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
        definition = db.scalars(select(WorkflowDefinition).where(
            WorkflowDefinition.id == int(template_id),
            WorkflowDefinition.tenant_id == _tid(),
            WorkflowDefinition.is_deleted.is_(False),
        ).with_for_update()).first()
        if not definition:
            raise not_found("审批模板不存在")
        if definition.status == "DISABLED":
            raise AppException("APPROVAL_TEMPLATE_VOIDED", "已作废模板不可编辑", http_status=409)
        if int(definition.version or 0) != int(expected_version):
            raise AppException("APPROVAL_VERSION_CONFLICT", "模板已被他人修改，请刷新后重试", http_status=409)
        definition.workflow_name = name
        definition.source_biz_type = biz_type
        try:
            definition.definition_version = str(int(definition.definition_version or "0") + 1)
        except ValueError:
            definition.definition_version = f"{definition.definition_version}.1"
        definition.version = int(definition.version or 0) + 1
        definition.updated_by = uid
        for old in _nodes(db, definition.id):
            old.is_deleted = True
            old.version = int(old.version or 0) + 1
        for idx, node in enumerate(nodes, start=1):
            db.add(WorkflowNodeDefinition(
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
            ))
        audit.record_critical(
            "审批模板更新",
            method="PUT", path=f"/api/v1/approvals/templates/{template_id}",
            status_code=200, target_type="approval-template", target_id=str(template_id),
            detail={"definitionVersion": definition.definition_version}, db=db,
        )
        db.commit()
        db.refresh(definition)
        return _row(db, definition)


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
        definition.status = "DISABLED"
        definition.description = text
        definition.version = int(definition.version or 0) + 1
        definition.updated_by = uid
        audit.record_critical(
            "审批模板作废",
            method="POST", path=f"/api/v1/approvals/templates/{template_id}/void",
            status_code=200, target_type="approval-template", target_id=str(template_id),
            detail={"reason": text}, db=db,
        )
        db.commit()
        db.refresh(definition)
        return _row(db, definition)


def create_export(scope, purpose, *, user=None):
    _require_db()
    _require_manage(user)
    scope = str(scope or "").upper()
    if scope not in {"TODO", "DONE", "RETURNED", "CC", "TEMPLATE"}:
        raise AppException("VALIDATION_ERROR", "未知审批导出范围")
    purpose = str(purpose or "").strip()
    if len(purpose) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填且不少于 5 字")

    from openpyxl import Workbook
    from app.models import ExportTask
    from app.services import approval_runtime_service as runtime
    from app.services import db_service
    from app.services import mock_audit_service as audit
    from app.services.import_export_service import upload_dir

    max_rows = 5000
    if scope == "TODO":
        rows, total = runtime.list_tasks(1, max_rows, user=user)
    elif scope == "DONE":
        rows, total = runtime.list_processed(1, max_rows, user=user)
    elif scope == "RETURNED":
        rows, total = runtime.list_returned(1, max_rows, user=user)
    elif scope == "CC":
        rows, total = runtime.list_cc(1, max_rows, user=user)
    else:
        rows, total = list_templates(1, max_rows, user=user)
    if total > max_rows:
        raise AppException("VALIDATION_ERROR", f"导出数据量 {total} 行超过单次上限 {max_rows} 行，请缩小范围")

    actor = _user(user)
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title="审批中心")
    ws.append([f"审批中心 · {scope} · 导出人：{actor.get('realName') or '-'} · 时间：{datetime.now():%Y-%m-%d %H:%M} · 用途：{purpose}"])
    ws.append(["任务/模板ID", "标题/名称", "业务类型", "状态", "办理时间", "原因/说明"])
    for row in rows:
        ws.append([
            str(row.get("taskId") or row.get("id") or ""),
            str(row.get("title") or row.get("name") or ""),
            str(row.get("sourceBizType") or row.get("bizType") or ""),
            str(row.get("status") or row.get("rectifyStatus") or ""),
            str(row.get("actedAt") or row.get("updatedAt") or row.get("ccTime") or ""),
            str(row.get("actionReason") or row.get("reason") or row.get("ccReason") or ""),
        ])

    key = f"exports/{datetime.now():%Y%m%d}/approval_{scope.lower()}_{uuid.uuid4().hex[:8]}.xlsx"
    target = upload_dir() / key
    target.parent.mkdir(parents=True, exist_ok=True)
    wb.save(target)

    uid = resolve_message_user_id(actor) or None
    with db_service.session() as db:
        task = ExportTask(
            tenant_id=_tid(),
            export_mode="LIST",
            module_code="approval",
            row_count=total,
            purpose=purpose,
            file_hash=hashlib.sha256(target.read_bytes()).hexdigest(),
            status="SUCCESS",
            remark=key,
            created_by=uid,
        )
        db.add(task)
        db.flush()
        audit.record_critical(
            "审批导出",
            method="POST", path="/api/v1/approvals/export",
            status_code=200, target_type="approval-export", target_id=str(task.id),
            detail={"scope": scope, "rows": total, "purpose": purpose}, db=db,
        )
        db.commit()
        return {
            "taskId": str(task.id),
            "status": "SUCCESS",
            "rowCount": total,
            "downloadUrl": f"/api/v1/approvals/export/{task.id}/download",
            "auditId": get_trace_id(),
            "scope": scope,
        }


def export_file_path(task_id, *, user=None):
    _require_db()
    _require_manage(user)
    from sqlalchemy import select
    from app.models import ExportTask
    from app.services import db_service
    from app.services.import_export_service import upload_dir

    with db_service.session() as db:
        task = db.scalars(select(ExportTask).where(
            ExportTask.id == int(task_id),
            ExportTask.tenant_id == _tid(),
            ExportTask.module_code == "approval",
        )).first()
        if not task:
            raise not_found("导出任务不存在或文件已清理")
        path = upload_dir() / str(task.remark or "")
        if not task.remark or not Path(path).exists():
            raise not_found("导出任务不存在或文件已清理")
        return path
