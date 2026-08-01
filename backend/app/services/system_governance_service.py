"""系统管理治理服务：临时授权、接口凭证、同步任务、模块开关。

硬规则：
- 临时授权进入鉴权叠加（active_delegation_permission_patterns）
- 接口凭证加密存储，永不回传原文；无适配器仅称「接入配置登记」
- 同步任务无真实执行器不得写 SUCCESS
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker

DOC_DELEGATIONS = "DELEGATIONS"
DOC_INTEGRATIONS = "INTEGRATIONS"
DOC_SYNC_JOBS = "SYNC_JOBS"
DOC_MODULE_FEATURES = "MODULE_FEATURES"

SYNC_PENDING = "PENDING"
SYNC_RUNNING = "RUNNING"
SYNC_SUCCESS = "SUCCESS"
SYNC_FAILED = "FAILED"
SYNC_CANCELLED = "CANCELLED"

# 已知可执行适配器；未登记的只能 PENDING/FAILED，禁止 SUCCESS
KNOWN_SYNC_ADAPTERS: dict[str, str] = {
    # adapterCode -> label；本轮无外部系统适配器，保持空表 = 禁止伪造成功
}


def _tid() -> int:
    return int(current_tenant_id() or 0)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


_MEMORY_DOCS: dict[str, Any] = {}


def _empty_document(doc_key: str) -> list | dict:
    return {} if doc_key == DOC_MODULE_FEATURES else []


def _load_with_version(doc_key: str) -> tuple[list | dict, int]:
    from app.models.system_governance import SystemJsonDoc
    from app.db.session import db_enabled
    empty = _empty_document(doc_key)
    if not db_enabled():
        return _MEMORY_DOCS.get(doc_key, empty), int(_MEMORY_DOCS.get(f"{doc_key}__ver") or 0)
    try:
        db = get_sessionmaker()()
        try:
            row = db.scalars(select(SystemJsonDoc).where(
                SystemJsonDoc.tenant_id == _tid(), SystemJsonDoc.doc_key == doc_key,
                SystemJsonDoc.is_deleted.is_(False))).first()
            if row is None or row.payload is None:
                return empty, 0
            return row.payload, int(row.version or 0)
        finally:
            db.close()
    except Exception as exc:
        raise AppException(
            "SERVER_ERROR",
            "系统治理配置读取失败，请稍后重试或联系管理员",
            http_status=503,
        ) from exc


def _load(doc_key: str) -> list | dict:
    payload, _ = _load_with_version(doc_key)
    return payload


def _save(doc_key: str, payload: Any, user: dict | None = None,
          expected_version: int | None = None) -> int:
    from app.models.system_governance import SystemJsonDoc
    from app.db.session import db_enabled
    if not db_enabled():
        current_version = int(_MEMORY_DOCS.get(f"{doc_key}__ver") or 0)
        if expected_version is not None and int(expected_version) != current_version:
            raise AppException("DATA_CONFLICT", "配置已被他人更新，请刷新后重试")
        prev = current_version + 1
        _MEMORY_DOCS[doc_key] = payload
        _MEMORY_DOCS[f"{doc_key}__ver"] = prev
        return prev
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(SystemJsonDoc).where(
            SystemJsonDoc.tenant_id == _tid(), SystemJsonDoc.doc_key == doc_key,
            SystemJsonDoc.is_deleted.is_(False)).with_for_update()).first()
        current_version = int(row.version or 0) if row is not None else 0
        if expected_version is not None and int(expected_version) != current_version:
            raise AppException("DATA_CONFLICT", "配置已被他人更新，请刷新后重试")
        version = 1
        if row is None:
            db.add(SystemJsonDoc(tenant_id=_tid(), doc_key=doc_key, payload=payload, version=1))
        else:
            row.payload = payload
            row.version = int(row.version or 0) + 1
            version = row.version
            if user:
                raw = str(user.get("userId") or "").replace("db-", "")
                row.updated_by = int(raw) if raw.isdigit() else None
        db.commit()
        return version
    except AppException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise AppException("INTERNAL_ERROR", f"治理配置落库失败，请先执行数据库迁移：{exc}") from exc
    finally:
        db.close()


def _mask_credential(credential: str) -> str:
    c = str(credential or "")
    if len(c) > 4:
        return c[:2] + "****" + c[-2:]
    return "****" if c else ""


def _encrypt_credential(credential: str) -> str:
    from app.core.field_crypto import encrypt_field
    return encrypt_field(credential) or ""


def _validate_endpoint(endpoint: str) -> None:
    parsed = urlparse(str(endpoint or "").strip())
    if parsed.scheme not in ("https", "http"):
        raise AppException("VALIDATION_ERROR", "接口地址必须是 http/https URL")
    if not parsed.netloc:
        raise AppException("VALIDATION_ERROR", "接口地址缺少主机名")
    if parsed.scheme == "http" and "localhost" not in parsed.netloc and "127.0.0.1" not in parsed.netloc:
        raise AppException("VALIDATION_ERROR", "非本地环境禁止明文 http，请使用 https")


def _permission_pattern_covered(target: str, grantors: set[str]) -> bool:
    """判断一个待转授模式是否完全落在授权人的基础权限内。"""
    if "*" in grantors or target in grantors:
        return True
    for grant in grantors:
        if grant.endswith(".*") and target.startswith(grant[:-1]):
            return True
        if grant.startswith("*.") and "*" not in target and target.endswith(grant[1:]):
            return True
    return False


def _resolve_grantee(login_name: str) -> tuple[int, str]:
    """把页面输入的工号解析为本租户稳定 user_id，禁止跨租户和异常账号。"""
    from app.db.session import db_enabled
    if not db_enabled():
        raise AppException("SERVER_ERROR", "临时授权需要启用数据库", http_status=503)
    from app.models import User
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(User).where(
            User.tenant_id == _tid(),
            User.login_name == login_name,
            User.is_deleted.is_(False),
        )).first()
        if row is None:
            raise AppException("DATA_NOT_FOUND", "受权人不存在或不属于当前学校")
        if str(row.status or "").upper() != "ACTIVE":
            raise AppException("VALIDATION_ERROR", "只能给正常状态账号创建临时授权")
        return int(row.id), str(row.login_name)
    finally:
        db.close()


def _is_expired(value: str) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        now = datetime.now(parsed.tzinfo) if parsed.tzinfo else datetime.now()
        return parsed <= now
    except ValueError:
        return False


# ─── 临时授权（真实鉴权叠加）───────────────────────────────────────────

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
    expected = body.get("expectedVersion")
    if not grantee or not role_code or len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "受权人工号、角色与原因（≥5字）必填")
    if not expires_at or expires_at <= _now():
        raise AppException("VALIDATION_ERROR", "到期时间必须晚于当前时间")
    if role_code.startswith("PLATFORM_"):
        raise AppException("NO_PERMISSION", "学校临时授权禁止授予平台角色")
    from app.core.permissions import ROLE_PERMISSIONS, get_base_permission_patterns
    delegated_patterns = set(ROLE_PERMISSIONS.get(role_code) or set())
    if not delegated_patterns:
        raise AppException("VALIDATION_ERROR", "临时角色不存在或没有可授予权限")
    if "*" in delegated_patterns:
        raise AppException("NO_PERMISSION", "临时授权禁止授予全量通配权限")
    grantor_patterns = set(get_base_permission_patterns(user))
    uncovered = sorted(
        pattern for pattern in delegated_patterns
        if not _permission_pattern_covered(pattern, grantor_patterns)
    )
    if uncovered:
        raise AppException(
            "NO_PERMISSION",
            "不能授予超出当前操作者基础权限的临时角色",
            details={"roleCode": role_code, "uncoveredPermissions": uncovered[:20]},
        )
    grantee_user_id, grantee_login = _resolve_grantee(grantee)
    items = list_delegations()
    _, current_version = _load_with_version(DOC_DELEGATIONS)
    if expected is not None:
        if int(expected) != current_version:
            raise AppException("DATA_CONFLICT", "临时授权已被他人更新，请刷新后重试")
    row = {
        "id": str(uuid4()), "granteeUserId": str(grantee_user_id),
        "granteeUserNo": grantee_login, "roleCode": role_code,
        "expiresAt": expires_at, "reason": reason, "status": "ACTIVE", "statusLabel": "生效中",
        "createdAt": _now(), "createdBy": (user or {}).get("realName") or "系统",
        "effective": True, "version": 1,
        "docVersion": current_version + 1,
        "note": "临时授权已进入实时鉴权；过期或回收后立即失效",
    }
    items.insert(0, row)
    _save(DOC_DELEGATIONS, items, user, expected_version=current_version)
    from app.services import audit_log
    audit_log.record("DELEGATION_CREATE", f"delegation:{row['id']}",
                     detail={"grantee": grantee, "roleCode": role_code, "expiresAt": expires_at, "reason": reason,
                             "moduleCode": "systemAdmin"})
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
    hit["effective"] = False
    hit["version"] = int(hit.get("version") or 1) + 1
    _save(DOC_DELEGATIONS, items, user)
    from app.services import audit_log
    audit_log.record("DELEGATION_REVOKE", f"delegation:{delegation_id}",
                     detail={"reason": reason, "moduleCode": "systemAdmin"})
    return hit


def active_delegation_permission_patterns(user: dict) -> set[str]:
    """对当前用户生效的临时授权权限模式（供 get_effective_permission_patterns 叠加）。"""
    login = str((user or {}).get("loginName") or (user or {}).get("userNo") or "").strip()
    user_id = str((user or {}).get("userId") or "").removeprefix("db-").strip()
    if not login and not user_id:
        return set()
    from app.core.permissions import ROLE_PERMISSIONS
    patterns: set[str] = set()
    now = _now()
    for item in list_delegations():
        if item.get("status") != "ACTIVE" or not item.get("effective", True):
            continue
        stable_target = str(item.get("granteeUserId") or "").strip()
        if stable_target:
            if not user_id or stable_target != user_id:
                continue
        elif str(item.get("granteeUserNo") or "").strip() != login:
            continue
        if item.get("expiresAt") and item["expiresAt"] < now:
            continue
        role_code = str(item.get("roleCode") or "").upper()
        patterns.update(ROLE_PERMISSIONS.get(role_code) or set())
    return patterns


# ─── 接口凭证 ───────────────────────────────────────────────────────────

def list_integrations() -> list[dict]:
    rows = []
    for item in list(_load(DOC_INTEGRATIONS) or []):
        public = {k: v for k, v in item.items() if k not in ("credentialEncrypted", "credential")}
        public["connectionMode"] = "CONFIG_REGISTRY"
        public["connectionModeLabel"] = "接入配置登记（无真实适配器时不可显示已连接）"
        if public.get("status") == "CONNECTED":
            public["status"] = "CONFIGURED"
            public["statusLabel"] = "已登记"
        rows.append(public)
    return rows


def save_integration(user: dict, body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    endpoint = str(body.get("endpoint") or "").strip()
    if len(name) < 2 or not endpoint:
        raise AppException("VALIDATION_ERROR", "请填写连接名称与接口地址")
    _validate_endpoint(endpoint)
    items = list(_load(DOC_INTEGRATIONS) or [])
    row_id = str(body.get("id") or "")
    credential = str(body.get("credential") or "").strip()
    expected = body.get("expectedVersion")
    if row_id:
        hit = next((x for x in items if x.get("id") == row_id), None)
        if hit is None:
            raise AppException("DATA_NOT_FOUND", "接口连接不存在")
        if expected is not None and int(expected) != int(hit.get("version") or 0):
            raise AppException("DATA_CONFLICT", "接口配置版本冲突，请刷新后重试")
        hit.update({"name": name, "endpoint": endpoint, "authType": body.get("authType") or "TOKEN",
                    "updatedAt": _now(), "version": int(hit.get("version") or 0) + 1,
                    "status": "CONFIGURED", "statusLabel": "已登记"})
        if credential:
            hit["credentialEncrypted"] = _encrypt_credential(credential)
            hit["credentialMasked"] = _mask_credential(credential)
            hit["hasCredential"] = True
            hit.pop("credential", None)
        row = hit
    else:
        row = {
            "id": str(uuid4()), "name": name, "endpoint": endpoint,
            "authType": body.get("authType") or "TOKEN",
            "credentialEncrypted": _encrypt_credential(credential) if credential else "",
            "credentialMasked": _mask_credential(credential) if credential else "",
            "hasCredential": bool(credential), "status": "CONFIGURED", "statusLabel": "已登记",
            "connectionMode": "CONFIG_REGISTRY",
            "createdAt": _now(), "updatedAt": _now(), "version": 1,
            "lastTestAt": "", "lastError": "",
        }
        items.insert(0, row)
    _save(DOC_INTEGRATIONS, items, user)
    from app.services import audit_log
    audit_log.record("INTEGRATION_SAVE", f"integration:{row['id']}",
                     detail={"name": name, "endpoint": endpoint, "moduleCode": "systemAdmin"})
    return {k: v for k, v in row.items() if k not in ("credential", "credentialEncrypted")}


def rotate_integration_credential(user: dict, integration_id: str, credential: str,
                                  expected_version: int | None = None) -> dict:
    credential = str(credential or "").strip()
    if len(credential) < 8:
        raise AppException("VALIDATION_ERROR", "新凭证长度至少 8 位")
    items = list(_load(DOC_INTEGRATIONS) or [])
    hit = next((x for x in items if x.get("id") == integration_id), None)
    if hit is None:
        raise AppException("DATA_NOT_FOUND", "接口连接不存在")
    if expected_version is not None and int(expected_version) != int(hit.get("version") or 0):
        raise AppException("DATA_CONFLICT", "凭证版本冲突，请刷新后重试")
    hit["credentialEncrypted"] = _encrypt_credential(credential)
    hit["credentialMasked"] = _mask_credential(credential)
    hit["hasCredential"] = True
    hit["rotatedAt"] = _now()
    hit["version"] = int(hit.get("version") or 0) + 1
    hit.pop("credential", None)
    _save(DOC_INTEGRATIONS, items, user)
    from app.services import audit_log
    audit_log.record("INTEGRATION_ROTATE", f"integration:{integration_id}",
                     detail={"summary": "轮换接口凭证", "moduleCode": "systemAdmin"})
    return {k: v for k, v in hit.items() if k not in ("credential", "credentialEncrypted")}


def test_integration_connection(user: dict, integration_id: str, timeout_sec: float = 5.0) -> dict:
    """连接测试：仅做 URL 可达性探测；无业务适配器时不标记 CONNECTED。"""
    import socket
    from urllib.parse import urlparse as _up

    items = list(_load(DOC_INTEGRATIONS) or [])
    hit = next((x for x in items if x.get("id") == integration_id), None)
    if hit is None:
        raise AppException("DATA_NOT_FOUND", "接口连接不存在")
    endpoint = hit.get("endpoint") or ""
    _validate_endpoint(endpoint)
    parsed = _up(endpoint)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        sock = socket.create_connection((host, port), timeout=timeout_sec)
        sock.close()
        hit["lastTestAt"] = _now()
        hit["lastError"] = ""
        hit["lastTestResult"] = "REACHABLE"
        hit["status"] = "CONFIGURED"
        hit["statusLabel"] = "主机可达（配置登记）"
        message = "主机端口可达；尚未配置业务适配器，不能称为已连接"
    except OSError as exc:
        hit["lastTestAt"] = _now()
        hit["lastError"] = str(exc)[:200]
        hit["lastTestResult"] = "UNREACHABLE"
        message = f"连接测试失败：{exc}"
    _save(DOC_INTEGRATIONS, items, user)
    from app.services import audit_log
    audit_log.record("INTEGRATION_TEST", f"integration:{integration_id}",
                     detail={"result": hit.get("lastTestResult"), "moduleCode": "systemAdmin"})
    return {k: v for k, v in hit.items() if k not in ("credential", "credentialEncrypted")} | {"message": message}


# ─── 同步任务 ───────────────────────────────────────────────────────────

def list_sync_jobs() -> list[dict]:
    return list(_load(DOC_SYNC_JOBS) or [])


def enqueue_sync_job(user: dict, body: dict) -> dict:
    name = str(body.get("name") or "手工同步").strip()
    integration_id = str(body.get("integrationId") or "").strip()
    adapter = str(body.get("adapterCode") or "").strip()
    items = list_sync_jobs()
    # 无真实执行器：只能登记 PENDING，不得 SUCCESS
    has_executor = adapter in KNOWN_SYNC_ADAPTERS
    if body.get("forceFail"):
        status, label, message = SYNC_FAILED, "失败待重试", str(body.get("message") or "模拟失败，可重试")
    elif has_executor:
        status, label, message = SYNC_PENDING, "待执行", "已入队，等待调度器执行"
    else:
        status, label, message = SYNC_PENDING, "待执行（无适配器）", \
            "已登记同步任务，但当前没有真实执行器，禁止标记成功"
    row = {
        "id": str(uuid4()), "name": name, "integrationId": integration_id,
        "adapterCode": adapter, "hasExecutor": has_executor,
        "status": status, "statusLabel": label, "message": message,
        "createdAt": _now(), "updatedAt": _now(),
        "createdBy": (user or {}).get("realName") or "系统", "version": 1,
        "idempotencyKey": str(body.get("idempotencyKey") or "") or None,
    }
    if row["idempotencyKey"]:
        existing = next((x for x in items if x.get("idempotencyKey") == row["idempotencyKey"]), None)
        if existing:
            return existing
    items.insert(0, row)
    _save(DOC_SYNC_JOBS, items, user)
    from app.services import audit_log
    audit_log.record("SYNC_JOB_ENQUEUE", f"sync:{row['id']}",
                     detail={"name": name, "status": row["status"], "moduleCode": "systemAdmin"})
    return row


def run_sync_job_executor(job_id: str, user: dict | None = None) -> dict:
    """独立调度入口：仅当存在真实适配器时才可写 SUCCESS。"""
    items = list_sync_jobs()
    hit = next((x for x in items if x.get("id") == job_id), None)
    if hit is None:
        raise AppException("DATA_NOT_FOUND", "同步任务不存在")
    adapter = str(hit.get("adapterCode") or "")
    if adapter not in KNOWN_SYNC_ADAPTERS:
        hit["status"] = SYNC_FAILED
        hit["statusLabel"] = "失败"
        hit["message"] = "无真实执行器，不能同步成功"
        hit["updatedAt"] = _now()
        _save(DOC_SYNC_JOBS, items, user)
        raise AppException("VALIDATION_ERROR", "无真实执行器，禁止标记同步成功")
    hit["status"] = SYNC_RUNNING
    hit["statusLabel"] = "执行中"
    hit["updatedAt"] = _now()
    _save(DOC_SYNC_JOBS, items, user)
    # 预留适配器调用点；当前已知表为空，不会走到这里
    hit["status"] = SYNC_SUCCESS
    hit["statusLabel"] = "成功"
    hit["message"] = "执行器完成"
    hit["updatedAt"] = _now()
    _save(DOC_SYNC_JOBS, items, user)
    return hit


def retry_sync_job(user: dict, job_id: str) -> dict:
    items = list_sync_jobs()
    hit = next((x for x in items if x.get("id") == job_id), None)
    if hit is None:
        raise AppException("DATA_NOT_FOUND", "同步任务不存在")
    if hit.get("status") == SYNC_CANCELLED:
        raise AppException("VALIDATION_ERROR", "已取消任务不可重试")
    adapter = str(hit.get("adapterCode") or "")
    hit["status"] = SYNC_PENDING
    hit["statusLabel"] = "待执行"
    hit["message"] = "已重新入队" if adapter in KNOWN_SYNC_ADAPTERS else "已重新登记（仍无真实执行器）"
    hit["updatedAt"] = _now()
    hit["retriedBy"] = (user or {}).get("realName") or "系统"
    hit["version"] = int(hit.get("version") or 0) + 1
    _save(DOC_SYNC_JOBS, items, user)
    from app.services import audit_log
    audit_log.record("SYNC_JOB_RETRY", f"sync:{job_id}",
                     detail={"summary": "重试同步任务", "status": hit["status"], "moduleCode": "systemAdmin"})
    return hit


def cancel_sync_job(user: dict, job_id: str, reason: str) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "取消原因不少于 5 个字")
    items = list_sync_jobs()
    hit = next((x for x in items if x.get("id") == job_id), None)
    if hit is None:
        raise AppException("DATA_NOT_FOUND", "同步任务不存在")
    hit["status"] = SYNC_CANCELLED
    hit["statusLabel"] = "已取消"
    hit["message"] = reason
    hit["updatedAt"] = _now()
    _save(DOC_SYNC_JOBS, items, user)
    from app.services import audit_log
    audit_log.record("SYNC_JOB_CANCEL", f"sync:{job_id}",
                     detail={"reason": reason, "moduleCode": "systemAdmin"})
    return hit


# ─── 模块开关 ───────────────────────────────────────────────────────────

def get_module_features() -> dict:
    base = {
        "studentAffairs": {"enabled": True, "label": "学工中心", "expiresAt": "", "featureKey": "studentAffairs"},
        "orientation": {"enabled": True, "label": "数字迎新", "expiresAt": "", "featureKey": "orientation"},
        "campusService": {"enabled": True, "label": "在校服务", "expiresAt": "", "featureKey": "campusService"},
        "academicAffairs": {"enabled": True, "label": "教务中心", "expiresAt": "", "featureKey": "academicAffairs"},
        "graduationDesign": {"enabled": True, "label": "毕业设计中心", "expiresAt": "", "featureKey": "graduation"},
        "internship": {"enabled": True, "label": "岗位实习中心", "expiresAt": "", "featureKey": "internship"},
        "employment": {"enabled": True, "label": "就业服务", "expiresAt": "", "featureKey": "employment"},
        "workbench": {"enabled": True, "label": "工作台", "expiresAt": "", "featureKey": "todoMessage"},
        "systemAdmin": {"enabled": True, "label": "系统管理", "expiresAt": "", "featureKey": "auditLog"},
    }
    # 叠加平台 entitled
    tid = _tid()
    if tid:
        try:
            from app.services.platform_service import feature_enabled
            for key, val in base.items():
                fk = val.get("featureKey") or key
                val["entitled"] = bool(feature_enabled(tid, fk))
                if not val["entitled"]:
                    val["enabled"] = False
                    val["reason"] = "未购买或未授权"
        except Exception:
            pass
    saved, document_version = _load_with_version(DOC_MODULE_FEATURES)
    saved = saved or {}
    if isinstance(saved, dict):
        for key, val in saved.items():
            if key in base and isinstance(val, dict):
                # 学校只能改 enabled，不能伪造成 entitled
                if "enabled" in val and base[key].get("entitled", True):
                    base[key]["enabled"] = bool(val["enabled"])
                if val.get("expiresAt"):
                    base[key]["expiresAt"] = val["expiresAt"]
                    if _is_expired(val["expiresAt"]):
                        base[key]["enabled"] = False
                        base[key]["reason"] = "学校模块启用期限已到期"
    for val in base.values():
        val["version"] = document_version
    return base


def save_module_features(user: dict, body: dict, reason: str,
                         expected_version: int | None = None) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "调整原因不少于 5 个字")
    before = get_module_features()
    saved, current_version = _load_with_version(DOC_MODULE_FEATURES)
    if expected_version is not None and int(expected_version) != current_version:
        raise AppException("DATA_CONFLICT", "模块开关已被他人更新，请刷新后重试")
    current = {
        key: {
            "enabled": bool(value.get("enabled", True)),
            "expiresAt": str(value.get("expiresAt") or ""),
        }
        for key, value in (saved or {}).items()
        if key in before and isinstance(value, dict)
    }
    for key, val in (body or {}).items():
        if key not in before or not isinstance(val, dict):
            continue
        requested_enabled = bool(val.get("enabled")) if "enabled" in val else bool(before[key].get("enabled"))
        if requested_enabled and not before[key].get("entitled", True):
            raise AppException("VALIDATION_ERROR", f"未购买模块不可启用：{key}")
        current.setdefault(key, {
            "enabled": bool(before[key].get("enabled", True)),
            "expiresAt": str(before[key].get("expiresAt") or ""),
        })
        if "enabled" in val:
            current[key]["enabled"] = bool(val["enabled"])
    ver = _save(DOC_MODULE_FEATURES, current, user, expected_version=current_version)
    # 清缓存：模块清单 / 权限上下文
    try:
        from app.core.module_registry import load_module_manifest, module_index
        load_module_manifest.cache_clear()
        module_index.cache_clear()
    except Exception:
        pass
    from app.services import audit_log
    audit_log.record("MODULE_FEATURE_SAVE", "module_features",
                     detail={"reason": reason, "before": before, "after": current,
                              "version": ver, "moduleCode": "systemAdmin"})
    return get_module_features()
