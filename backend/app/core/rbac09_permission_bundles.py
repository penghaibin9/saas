"""RBAC-09 文件与数据交换原子权限包及旧权限兼容层。

本模块只提供权限元数据和兼容判定，不建立第二套鉴权引擎。所有最终判定仍委托
``app.core.permissions.has_permission``；旧权限只在一个发布周期内映射到新的原子动作，
每个进程对同一主体/旧码/新码首次命中时写弃用日志和审计证据。
"""
from __future__ import annotations

import logging
from typing import Iterable

from fastapi import Depends

from app.core.exceptions import no_permission
from app.core.permissions import has_permission, is_super_admin
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

FILE_GOVERNANCE_VIEW = "systemAdmin.fileGovernance.view"
FILE_QUOTA_MANAGE = "systemAdmin.fileGovernance.quota.manage"
FILE_RETENTION_MANAGE = "systemAdmin.fileGovernance.retention.manage"
FILE_CLEANUP_EXECUTE = "systemAdmin.fileGovernance.cleanup.execute"
FILE_LEGAL_HOLD_MANAGE = "systemAdmin.fileGovernance.legalHold.manage"
FILE_SCAN_RETRY = "systemAdmin.fileGovernance.scan.retry"

DATA_EXCHANGE_VIEW_OWN = "systemAdmin.dataExchange.viewOwn"
DATA_EXCHANGE_VIEW_TENANT = "systemAdmin.dataExchange.viewTenant"
DATA_EXCHANGE_CONFIRM = "systemAdmin.dataExchange.confirm"
DATA_EXCHANGE_DOWNLOAD = "systemAdmin.dataExchange.download"
DATA_EXCHANGE_REVOKE = "systemAdmin.dataExchange.revoke"
DATA_EXCHANGE_RETRY = "systemAdmin.dataExchange.retry"

PERMISSION_BUNDLES: dict[str, dict] = {
    "FILE_GOVERNANCE_VIEW": {
        "permissions": (FILE_GOVERNANCE_VIEW,),
        "allows": "查看容量、扫描健康和异常数量",
        "denies": "文件原文预览与下载",
    },
    "FILE_QUOTA_ADMIN": {
        "permissions": (FILE_QUOTA_MANAGE,),
        "allows": "配置学校和模块存储配额",
        "denies": "扩大平台商业授权上限",
    },
    "FILE_RETENTION_ADMIN": {
        "permissions": (FILE_RETENTION_MANAGE,),
        "allows": "维护保留策略和历史截止日回填",
        "denies": "直接删除文件字节",
    },
    "FILE_CLEANUP_EXECUTOR": {
        "permissions": (FILE_CLEANUP_EXECUTE,),
        "allows": "执行已校验的清理预演或清理",
        "denies": "跳过引用、法律保留与审计",
    },
    "FILE_LEGAL_HOLD_ADMIN": {
        "permissions": (FILE_LEGAL_HOLD_MANAGE,),
        "allows": "设置或解除法律保留",
        "denies": "默认查看被保留文件原文",
    },
    "FILE_SCAN_OPERATOR": {
        "permissions": (FILE_SCAN_RETRY,),
        "allows": "重试安全扫描失败任务",
        "denies": "下载感染或隔离文件",
    },
    "DATA_EXCHANGE_VIEW_OWN": {
        "permissions": (DATA_EXCHANGE_VIEW_OWN,),
        "scope": "本人创建任务",
    },
    "DATA_EXCHANGE_VIEW_TENANT": {
        "permissions": (DATA_EXCHANGE_VIEW_TENANT,),
        "scope": "本校全部任务，仍叠加 moduleCode 和敏感等级",
    },
    "DATA_EXCHANGE_CONFIRM": {
        "permissions": (DATA_EXCHANGE_CONFIRM,),
        "scope": "确认被授权类型的导入任务",
    },
    "DATA_EXCHANGE_DOWNLOAD": {
        "permissions": (DATA_EXCHANGE_DOWNLOAD,),
        "scope": "下载被授权回执；查看任务不自动获得此权限",
    },
    "DATA_EXCHANGE_REVOKE": {
        "permissions": (DATA_EXCHANGE_REVOKE,),
        "scope": "撤销被授权导出任务",
    },
    "DATA_EXCHANGE_RETRY": {
        "permissions": (DATA_EXCHANGE_RETRY,),
        "scope": "在原始租户、模块和数据范围内重试失败任务",
    },
}

# 兼容期只允许旧码映射到治理元数据或既有数据交换动作；绝不映射到文件内容访问。
# 旧 user.import 历史上没有“全校任务查看”能力，因此不得借兼容期升级为 viewTenant。
LEGACY_ALIAS_BY_PERMISSION: dict[str, tuple[str, ...]] = {
    FILE_GOVERNANCE_VIEW: ("systemAdmin.file.manage",),
    FILE_QUOTA_MANAGE: ("systemAdmin.file.manage",),
    FILE_RETENTION_MANAGE: ("systemAdmin.file.manage",),
    FILE_CLEANUP_EXECUTE: ("systemAdmin.file.manage",),
    FILE_LEGAL_HOLD_MANAGE: ("systemAdmin.file.manage",),
    FILE_SCAN_RETRY: ("systemAdmin.file.manage",),
    DATA_EXCHANGE_VIEW_OWN: ("systemAdmin.user.import",),
    DATA_EXCHANGE_CONFIRM: ("systemAdmin.user.import",),
    DATA_EXCHANGE_DOWNLOAD: ("systemAdmin.user.import",),
    DATA_EXCHANGE_REVOKE: ("systemAdmin.user.import",),
    DATA_EXCHANGE_RETRY: ("systemAdmin.user.import",),
}

_WARNED_LEGACY_USES: set[tuple[str, str, str, str]] = set()
_MAX_WARNED_KEYS = 5000


def permission_bundle_catalog() -> list[dict]:
    return [
        {"bundleCode": code, **payload}
        for code, payload in sorted(PERMISSION_BUNDLES.items())
    ]


def _actor_key(user: dict) -> tuple[str, str]:
    return (
        str(user.get("tenantId") or ""),
        str(user.get("userId") or user.get("id") or user.get("loginName") or ""),
    )


def _record_legacy_alias_use(user: dict, legacy_code: str, target_code: str) -> None:
    tenant_key, actor_key = _actor_key(user)
    key = (tenant_key, actor_key, legacy_code, target_code)
    if key in _WARNED_LEGACY_USES:
        return
    if len(_WARNED_LEGACY_USES) >= _MAX_WARNED_KEYS:
        _WARNED_LEGACY_USES.clear()
    _WARNED_LEGACY_USES.add(key)
    logger.warning(
        "RBAC-09 deprecated permission alias used tenant=%s actor=%s legacy=%s target=%s",
        tenant_key,
        actor_key,
        legacy_code,
        target_code,
    )
    try:
        from app.services import audit_log

        audit_log.record(
            "LEGACY_PERMISSION_ALIAS_USED",
            f"permission:{target_code}",
            detail={
                "legacyPermission": legacy_code,
                "targetPermission": target_code,
                "releaseWindow": "RBAC-09-COMPAT-1",
            },
            result="SUCCESS",
        )
    except Exception:  # noqa: BLE001 - 鉴权不能因审计服务异常而放宽或崩溃
        logger.exception("RBAC-09 legacy permission audit failed")


def permission_decision(user: dict, permission_code: str) -> tuple[bool, str | None]:
    """返回 ``(allowed, legacy_code)``；直接新权限命中时 legacy_code 为 None。"""
    if is_super_admin(user) or has_permission(user, permission_code):
        return True, None
    for legacy_code in LEGACY_ALIAS_BY_PERMISSION.get(permission_code, ()):
        if has_permission(user, legacy_code):
            _record_legacy_alias_use(user, legacy_code, permission_code)
            return True, legacy_code
    return False, None


def has_permission_compat(user: dict, permission_code: str) -> bool:
    return permission_decision(user, permission_code)[0]


def has_any_permission_compat(user: dict, permission_codes: Iterable[str]) -> bool:
    return any(has_permission_compat(user, code) for code in permission_codes)


def require_permission_compat(permission_code: str):
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if has_permission_compat(user, permission_code):
            return user
        raise no_permission(f"无权限执行该操作（{permission_code}）")

    return _dep


def require_any_permission_compat(*permission_codes: str):
    codes = tuple(dict.fromkeys(str(code) for code in permission_codes if str(code)))

    def _dep(user: dict = Depends(get_current_user)) -> dict:
        if is_super_admin(user) or has_any_permission_compat(user, codes):
            return user
        raise no_permission("无权限执行该操作")

    return _dep

# ── RBAC-09 service-policy closeout ──────────────────────────────────────────
# Background workers do not inherit a human role or a wildcard tenant context.
# Every supported job type is bound to an explicit policy version, exact tenant,
# payload field allow-list and byte ceiling.  The returned evidence is suitable
# for audit/event payloads and deliberately contains no token material.
SERVICE_POLICY_VERSION = "RBAC09-SP-1"
SERVICE_POLICIES: dict[str, dict] = {
    "FILE_SCAN": {
        "allowedFields": {"fileId", "attempt", "requestedAt"},
        "maxBytes": 16 * 1024,
    },
    "FILE_RETENTION_CLEANUP": {
        "allowedFields": {"previewId", "candidateHash", "limit"},
        "maxBytes": 64 * 1024,
    },
    "DATA_EXCHANGE_IMPORT": {
        "allowedFields": {"jobId", "specCode", "fileId", "version"},
        "maxBytes": 128 * 1024,
    },
    "DATA_EXCHANGE_EXPORT": {
        "allowedFields": {"jobId", "specCode", "filterHash", "version"},
        "maxBytes": 128 * 1024,
    },
}


def authorize_service_job(
    service_context: dict,
    *,
    job_type: str,
    tenant_id: int,
    payload_fields: Iterable[str] = (),
    payload_bytes: int = 0,
) -> dict:
    """Fail-closed worker authorization for RBAC-09 service identities.

    Required context keys: ``subjectType=SERVICE``, ``serviceId``, exact
    ``tenantId`` and a short-lived ``tokenTtlSeconds``.  Human/user tokens,
    wildcard tenant scopes, unregistered job types and oversized/unknown fields
    are rejected.  The caller must persist the returned policy evidence.
    """
    import hashlib
    import uuid

    from app.core.exceptions import AppException

    ctx = dict(service_context or {})
    policy = SERVICE_POLICIES.get(str(job_type or "").upper())
    if policy is None:
        raise AppException("SERVICE_POLICY_DENIED", "未注册的后台任务类型", http_status=403)
    if str(ctx.get("subjectType") or "").upper() != "SERVICE" or not ctx.get("serviceId"):
        raise AppException("SERVICE_POLICY_DENIED", "后台任务必须使用服务身份", http_status=403)
    if ctx.get("userId") or ctx.get("actorUserId"):
        raise AppException("SERVICE_POLICY_DENIED", "后台任务不得继承人工账号令牌", http_status=403)
    scoped_tenant = ctx.get("tenantId")
    if scoped_tenant in (None, "", "*") or int(scoped_tenant) != int(tenant_id):
        raise AppException("SERVICE_POLICY_DENIED", "服务身份租户范围不匹配", http_status=403)
    ttl = int(ctx.get("tokenTtlSeconds") or 0)
    if ttl <= 0 or ttl > 900:
        raise AppException("SERVICE_POLICY_DENIED", "服务令牌必须短时有效（不超过15分钟）", http_status=403)
    fields = {str(value) for value in payload_fields}
    unknown = fields - set(policy["allowedFields"])
    if unknown:
        raise AppException(
            "SERVICE_POLICY_DENIED",
            "后台任务包含未授权字段",
            http_status=403,
            details={"unknownFields": sorted(unknown)},
        )
    size = max(0, int(payload_bytes or 0))
    if size > int(policy["maxBytes"]):
        raise AppException("SERVICE_POLICY_DENIED", "后台任务载荷超过策略上限", http_status=403)
    trace_id = str(ctx.get("traceId") or uuid.uuid4().hex)
    evidence_seed = (
        f"{SERVICE_POLICY_VERSION}|{job_type.upper()}|{int(tenant_id)}|"
        f"{ctx['serviceId']}|{','.join(sorted(fields))}|{size}|{trace_id}"
    )
    return {
        "allowed": True,
        "jobType": str(job_type).upper(),
        "tenantId": int(tenant_id),
        "serviceId": str(ctx["serviceId"]),
        "policyVersion": SERVICE_POLICY_VERSION,
        "traceId": trace_id,
        "evidenceHash": hashlib.sha256(evidence_seed.encode("utf-8")).hexdigest(),
    }
