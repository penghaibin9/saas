"""W3 tenant lifecycle commit/cache receipt and cache-only recovery.

The canonical transition service commits the database before invalidating auth
caches. If cache invalidation fails after commit, replaying the business command
is wrong: the business fact already changed.

A version delta alone is not proof that *this* request committed: a concurrent
administrator can advance the same tenant while the current request loses its
optimistic-lock race. The receipt therefore uses a request-local post-commit
probe on the canonical cache invalidation boundary. Only an exception raised
after this invocation crosses that boundary is converted into a degraded
materialized receipt; stale-version and all other pre-commit failures propagate.
"""
from __future__ import annotations

from contextvars import ContextVar
from functools import wraps

from app.services.tenant_effective_state_service import get_effective_state

_POST_COMMIT_PROBE: ContextVar[dict | None] = ContextVar(
    "platform_transition_post_commit_probe",
    default=None,
)


def _ensure_invalidation_probe() -> None:
    """Wrap the canonical tenant-cache boundary without sharing request state.

    ``tenant_effective_state_service.apply_transition`` imports the invalidator at
    call time and invokes it only after ``db.commit()``. A ContextVar marker is
    therefore an exact phase signal for this request and remains isolated across
    concurrent worker threads/tasks. Tests may monkeypatch the invalidator, so the
    wrapper is reinstalled whenever the current callable is not already probed.
    """
    from app.services import auth_service_db

    current = auth_service_db.invalidate_tenant_subject_caches
    if getattr(current, "_platform_transition_receipt_probe", False):
        return

    @wraps(current)
    def probed(tenant_id):
        probe = _POST_COMMIT_PROBE.get()
        if probe is not None and int(probe.get("tenantId") or 0) == int(tenant_id):
            probe["reached"] = True
        return current(tenant_id)

    probed._platform_transition_receipt_probe = True
    auth_service_db.invalidate_tenant_subject_caches = probed


def _materialized_receipt(
    *,
    tenant_id: int,
    action: str,
    before: dict,
    after: dict,
    error: Exception,
) -> dict:
    from app.services import audit_log, platform_service

    warning = "数据库变更已生效，但权限缓存刷新或提交后物化失败，请执行缓存恢复"
    try:
        audit_log.record(
            "PLATFORM_TENANT_CACHE_RECOVERY_REQUIRED",
            f"tenant:{tenant_id}",
            detail={
                "action": action,
                "beforeVersion": int(before.get("version") or 0),
                "afterVersion": int(after.get("version") or 0),
                "postCommitError": str(error)[:500],
                "runtimeMaterialized": True,
                "cacheInvalidated": False,
            },
            result="DEGRADED",
            tenant_id=int(tenant_id),
        )
    except Exception:
        pass
    meta = platform_service.tenant_meta(int(tenant_id))
    return {
        "tenantId": str(tenant_id),
        "action": action,
        "before": before,
        "after": after,
        "version": int(after.get("version") or 0),
        "status": after.get("effectiveStatus"),
        "packageCode": meta.get("packageCode"),
        "expireAt": meta.get("expireAt"),
        "maxStudents": meta.get("maxStudents"),
        "maxUsers": meta.get("maxUsers"),
        "storageLimitMb": meta.get("storageLimitMb"),
        "runtimeMaterialized": True,
        "cacheInvalidated": False,
        "cacheRecoveryRequired": True,
        "warning": warning,
        "postCommitError": str(error)[:500],
    }


def apply_transition_with_receipt(
    tenant_id: int,
    action: str,
    *,
    reason: str,
    expected_version: int,
    payload: dict | None = None,
    audit_action: str | None = None,
    commercial_authority: str | None = None,
) -> dict:
    from app.services.tenant_effective_state_service import apply_transition

    tid = int(tenant_id)
    normalized = str(action or "").strip().lower()
    before = get_effective_state(tid, strict=True)
    _ensure_invalidation_probe()
    probe = {"tenantId": tid, "reached": False}
    token = _POST_COMMIT_PROBE.set(probe)
    try:
        out = apply_transition(
            tid,
            normalized,
            reason=reason,
            expected_version=int(expected_version),
            payload=payload,
            audit_action=audit_action,
            commercial_authority=commercial_authority,
        )
    except Exception as exc:
        # The canonical invalidator is reached only after the business DB commit.
        # Never infer ownership from a version delta: another request may have won
        # the same optimistic-lock race while this invocation committed nothing.
        if probe["reached"]:
            after = get_effective_state(tid, strict=True)
            return _materialized_receipt(
                tenant_id=tid,
                action=normalized,
                before=before,
                after=after,
                error=exc,
            )
        raise
    finally:
        _POST_COMMIT_PROBE.reset(token)
    return {
        **out,
        "runtimeMaterialized": True,
        "cacheInvalidated": True,
        "cacheRecoveryRequired": False,
        "warning": "",
    }


def recover_tenant_auth_cache(tenant_id: int) -> dict:
    """Invalidate only auth caches. This command never replays lifecycle writes."""
    from app.services import audit_log
    from app.services.auth_service_db import invalidate_tenant_subject_caches

    tid = int(tenant_id)
    state = get_effective_state(tid, strict=True)
    version_before = int(state.get("version") or 0)
    try:
        removed = int(invalidate_tenant_subject_caches(tid) or 0)
        cache_ok = True
        warning = ""
        error = ""
    except Exception as exc:
        removed = 0
        cache_ok = False
        warning = "权限缓存恢复仍失败；数据库事实未重放，请稍后仅重试缓存恢复"
        error = str(exc)[:500]
    after = get_effective_state(tid, strict=True)
    version_after = int(after.get("version") or 0)
    # A different administrator may legitimately change the tenant while cache
    # recovery is running. The recovery command itself is cache-only, so report a
    # retryable concurrency conflict instead of falsely claiming it mutated state.
    if version_after != version_before:
        from app.core.exceptions import AppException
        raise AppException(
            "DATA_CONFLICT",
            "缓存恢复期间租户状态已被其他操作更新，请刷新后仅重试缓存恢复",
            http_status=409,
            details={"beforeVersion": version_before, "afterVersion": version_after},
        )
    try:
        audit_log.record(
            "PLATFORM_TENANT_AUTH_CACHE_RECOVERY",
            f"tenant:{tid}",
            detail={
                "cacheInvalidated": cache_ok,
                "removedKeys": removed,
                "version": version_after,
                "error": error,
            },
            result="SUCCESS" if cache_ok else "DEGRADED",
            tenant_id=tid,
        )
    except Exception:
        pass
    return {
        "tenantId": str(tid),
        "runtimeMaterialized": True,
        "cacheInvalidated": cache_ok,
        "cacheRecoveryRequired": not cache_ok,
        "removedKeys": removed,
        "version": version_after,
        "status": after.get("effectiveStatus"),
        "warning": warning,
        "postCommitError": error,
    }
