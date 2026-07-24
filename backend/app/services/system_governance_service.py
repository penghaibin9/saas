"""系统管理治理服务：临时授权、接口凭证、同步任务、模块开关（JSON 文档）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker

DOC_DELEGATIONS = "DELEGATIONS"
DOC_INTEGRATIONS = "INTEGRATIONS"
DOC_SYNC_JOBS = "SYNC_JOBS"
DOC_MODULE_FEATURES = "MODULE_FEATURES"


def _tid() -> int:
    return int(current_tenant_id() or 0)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load(doc_key: str) -> list | dict:
    from app.models.system_governance import SystemJsonDoc
    empty = [] if doc_key != DOC_MODULE_FEATURES else {}
    try:
        db = get_sessionmaker()()
        try:
            row = db.scalars(select(SystemJsonDoc).where(
                SystemJsonDoc.tenant_id == _tid(), SystemJsonDoc.doc_key == doc_key,
                SystemJsonDoc.is_deleted.is_(False))).first()
            if row is None or row.payload is None:
                return empty
            return row.payload
        finally:
            db.close()
    except Exception:
        # 表未迁移时 fail-open 返回空，避免整页 500
        return empty


def _save(doc_key: str, payload: Any, user: dict | None = None) -> None:
    from app.models.system_governance import SystemJsonDoc
    from app.core.exceptions import AppException
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(SystemJsonDoc).where(
            SystemJsonDoc.tenant_id == _tid(), SystemJsonDoc.doc_key == doc_key,
            SystemJsonDoc.is_deleted.is_(False))).first()
        if row is None:
            db.add(SystemJsonDoc(tenant_id=_tid(), doc_key=doc_key, payload=payload))
        else:
            row.payload = payload
            row.version = int(row.version or 0) + 1
            if user:
                raw = str(user.get("userId") or "").replace("db-", "")
                row.updated_by = int(raw) if raw.isdigit() else None
        db.commit()
    except Exception as exc:
        db.rollback()
        raise AppException("INTERNAL_ERROR", f"治理配置落库失败，请先执行数据库迁移：{exc}") from exc
    finally:
        db.close()


def list_delegations() -> list[dict]:
    items = list(_load(DOC_DELEGATIONS) or [])
    now = _now()
    changed = False
    for item in items:
        if item.get("status") == "ACTIVE" and item.get("expiresAt") and item["expiresAt"] < now:
            item["status"] = "EXPIRED"
            item["statusLabel"] = "已过期自动回收"
            changed = True
    if changed:
        _save(DOC_DELEGATIONS, items)
    return items


def create_delegation(user: dict, body: dict) -> dict:
    grantee = str(body.get("granteeUserNo") or "").strip()
    role_code = str(body.get("roleCode") or "").strip().upper()
    expires_at = str(body.get("expiresAt") or "").strip()
    reason = str(body.get("reason") or "").strip()
    if not grantee or not role_code or len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "受权人工号、角色与原因（≥5字）必填")
    if not expires_at or expires_at <= _now():
        raise AppException("VALIDATION_ERROR", "到期时间必须晚于当前时间")
    items = list_delegations()
    row = {
        "id": str(uuid4()), "granteeUserNo": grantee, "roleCode": role_code,
        "expiresAt": expires_at, "reason": reason, "status": "ACTIVE", "statusLabel": "生效中",
        "createdAt": _now(), "createdBy": (user or {}).get("realName") or "系统",
    }
    items.insert(0, row)
    _save(DOC_DELEGATIONS, items, user)
    from app.services import audit_log
    audit_log.record("DELEGATION_CREATE", f"delegation:{row['id']}",
                     detail={"grantee": grantee, "roleCode": role_code, "expiresAt": expires_at, "reason": reason})
    return row


def revoke_delegation(user: dict, delegation_id: str, reason: str) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "回收原因不少于 5 个字")
    items = list_delegations()
    hit = next((x for x in items if x.get("id") == delegation_id), None)
    if hit is None:
        raise AppException("DATA_NOT_FOUND", "临时授权不存在")
    hit["status"] = "REVOKED"
    hit["statusLabel"] = "已回收"
    hit["revokedAt"] = _now()
    hit["revokeReason"] = reason
    _save(DOC_DELEGATIONS, items, user)
    from app.services import audit_log
    audit_log.record("DELEGATION_REVOKE", f"delegation:{delegation_id}", detail={"reason": reason})
    return hit


def list_integrations() -> list[dict]:
    return list(_load(DOC_INTEGRATIONS) or [])


def save_integration(user: dict, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    endpoint = str(body.get("endpoint") or "").strip()
    if len(name) < 2 or not endpoint:
        raise AppException("VALIDATION_ERROR", "请填写连接名称与接口地址")
    items = list_integrations()
    row_id = str(body.get("id") or "")
    credential = str(body.get("credential") or "").strip()
    if row_id:
        hit = next((x for x in items if x.get("id") == row_id), None)
        if hit is None:
            raise AppException("DATA_NOT_FOUND", "接口连接不存在")
        hit.update({"name": name, "endpoint": endpoint, "authType": body.get("authType") or "TOKEN",
                    "updatedAt": _now()})
        if credential:
            hit["credentialMasked"] = credential[:2] + "****" + credential[-2:] if len(credential) > 4 else "****"
            hit["hasCredential"] = True
        row = hit
    else:
        row = {
            "id": str(uuid4()), "name": name, "endpoint": endpoint,
            "authType": body.get("authType") or "TOKEN",
            "credentialMasked": (credential[:2] + "****" + credential[-2:]) if len(credential) > 4 else ("****" if credential else ""),
            "hasCredential": bool(credential), "status": "ACTIVE", "statusLabel": "已启用",
            "createdAt": _now(), "updatedAt": _now(),
        }
        items.insert(0, row)
    _save(DOC_INTEGRATIONS, items, user)
    from app.services import audit_log
    audit_log.record("INTEGRATION_SAVE", f"integration:{row['id']}",
                     detail={"name": name, "endpoint": endpoint})
    return {k: v for k, v in row.items() if k != "credential"}


def rotate_integration_credential(user: dict, integration_id: str, credential: str) -> dict:
    credential = str(credential or "").strip()
    if len(credential) < 8:
        raise AppException("VALIDATION_ERROR", "新凭证长度至少 8 位")
    items = list_integrations()
    hit = next((x for x in items if x.get("id") == integration_id), None)
    if hit is None:
        raise AppException("DATA_NOT_FOUND", "接口连接不存在")
    hit["credentialMasked"] = credential[:2] + "****" + credential[-2:]
    hit["hasCredential"] = True
    hit["rotatedAt"] = _now()
    _save(DOC_INTEGRATIONS, items, user)
    from app.services import audit_log
    audit_log.record("INTEGRATION_ROTATE", f"integration:{integration_id}", detail={"summary": "轮换接口凭证"})
    return hit


def list_sync_jobs() -> list[dict]:
    return list(_load(DOC_SYNC_JOBS) or [])


def enqueue_sync_job(user: dict, body: dict) -> dict:
    name = str(body.get("name") or "手工同步").strip()
    integration_id = str(body.get("integrationId") or "").strip()
    items = list_sync_jobs()
    row = {
        "id": str(uuid4()), "name": name, "integrationId": integration_id,
        "status": "FAILED" if body.get("forceFail") else "SUCCESS",
        "statusLabel": "失败待重试" if body.get("forceFail") else "成功",
        "message": str(body.get("message") or ("模拟失败，可重试" if body.get("forceFail") else "同步完成")),
        "createdAt": _now(), "updatedAt": _now(),
        "createdBy": (user or {}).get("realName") or "系统",
    }
    items.insert(0, row)
    _save(DOC_SYNC_JOBS, items, user)
    from app.services import audit_log
    audit_log.record("SYNC_JOB_ENQUEUE", f"sync:{row['id']}", detail={"name": name, "status": row["status"]})
    return row


def retry_sync_job(user: dict, job_id: str) -> dict:
    items = list_sync_jobs()
    hit = next((x for x in items if x.get("id") == job_id), None)
    if hit is None:
        raise AppException("DATA_NOT_FOUND", "同步任务不存在")
    hit["status"] = "SUCCESS"
    hit["statusLabel"] = "成功"
    hit["message"] = "重试成功"
    hit["updatedAt"] = _now()
    hit["retriedBy"] = (user or {}).get("realName") or "系统"
    _save(DOC_SYNC_JOBS, items, user)
    from app.services import audit_log
    audit_log.record("SYNC_JOB_RETRY", f"sync:{job_id}", detail={"summary": "重试同步任务"})
    return hit


def cancel_sync_job(user: dict, job_id: str, reason: str) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "取消原因不少于 5 个字")
    items = list_sync_jobs()
    hit = next((x for x in items if x.get("id") == job_id), None)
    if hit is None:
        raise AppException("DATA_NOT_FOUND", "同步任务不存在")
    hit["status"] = "CANCELLED"
    hit["statusLabel"] = "已取消"
    hit["message"] = reason
    hit["updatedAt"] = _now()
    _save(DOC_SYNC_JOBS, items, user)
    from app.services import audit_log
    audit_log.record("SYNC_JOB_CANCEL", f"sync:{job_id}", detail={"reason": reason})
    return hit


def get_module_features() -> dict:
    base = {
        "studentAffairs": {"enabled": True, "label": "学工中心", "expiresAt": ""},
        "academicAffairs": {"enabled": True, "label": "教务中心", "expiresAt": ""},
        "graduationDesign": {"enabled": True, "label": "毕业设计中心", "expiresAt": ""},
        "internship": {"enabled": True, "label": "岗位实习中心", "expiresAt": ""},
    }
    saved = _load(DOC_MODULE_FEATURES) or {}
    if isinstance(saved, dict):
        for key, val in saved.items():
            if key in base and isinstance(val, dict):
                base[key].update(val)
    return base


def save_module_features(user: dict, body: dict, reason: str) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "调整原因不少于 5 个字")
    current = get_module_features()
    for key, val in (body or {}).items():
        if key in current and isinstance(val, dict):
            # 学校只能改业务开关，不能伪造成未购买模块
            if "enabled" in val:
                current[key]["enabled"] = bool(val["enabled"])
    _save(DOC_MODULE_FEATURES, current, user)
    from app.services import audit_log
    audit_log.record("MODULE_FEATURE_SAVE", "module_features", detail={"reason": reason, "features": current})
    return current
