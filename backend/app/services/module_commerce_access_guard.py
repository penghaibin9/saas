"""M4 module-generation/data-state fence installed on the canonical access service.

The commercial authority still decides purchase. This wrapper adds the independent
module-data lifecycle fence and a final-commit fence for unsafe HTTP requests.
A request that passed at generation N must lock/recheck the same ModuleState before
its business transaction commits; a freeze or generation change therefore wins a
single linearization race instead of allowing stale writes after FROZEN.

Workers do not inherit HTTP intent implicitly. They must use ``module_write_fence``
with tenant/module/generation from their durable task payload; the context is reset
when the worker step exits.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Any

from app.core.exceptions import AppException

_BLOCKED_DATA_STATES = {"FROZEN", "RETAINED", "PURGING", "PURGED"}
_SAFE_HTTP_METHODS = {"GET", "HEAD", "OPTIONS"}
_write_fence_ctx: ContextVar[dict[str, Any] | None] = ContextVar(
    "module_commerce_write_fence", default=None
)
_final_commit_listener_installed = False


def _lifecycle(tenant_id: int, module_key: str) -> dict[str, Any] | None:
    from app.db.session import db_enabled, get_sessionmaker
    from app.services.module_commerce_lifecycle_service import canonical_module

    if not db_enabled():
        return None
    try:
        module = canonical_module(module_key)
    except AppException:
        return None

    from sqlalchemy import select
    from app.models import TenantModuleState

    db = get_sessionmaker()()
    try:
        row = db.scalars(select(TenantModuleState).where(
            TenantModuleState.tenant_id == int(tenant_id),
            TenantModuleState.module_key == module,
            TenantModuleState.is_deleted.is_(False),
        )).first()
        if row is None:
            return None
        return {
            "moduleKey": module,
            "dataState": str(row.data_state or "AVAILABLE").upper(),
            "generation": int(row.generation or 0),
            "lifecycleVersion": int(row.lifecycle_version or 0),
        }
    except AppException:
        raise
    except Exception as exc:
        raise AppException(
            "MODULE_STATE_UNAVAILABLE",
            "模块数据状态服务暂时不可用，已按安全策略拒绝访问",
            details={"retryable": True},
            http_status=503,
        ) from exc
    finally:
        db.close()


def _http_write_intent() -> tuple[bool, str]:
    from app.core.context import get_request_meta, get_trace_id

    meta = get_request_meta() or {}
    method = str(meta.get("method") or "").upper().strip()
    trace = str(get_trace_id() or "-")
    return bool(method and method not in _SAFE_HTTP_METHODS and trace != "-"), trace


def _remember_http_fence(tenant_id: int, lifecycle: dict[str, Any] | None) -> None:
    if lifecycle is None or int(lifecycle.get("generation") or 0) <= 0:
        return
    intent, trace = _http_write_intent()
    if not intent:
        return
    current = _write_fence_ctx.get()
    if not current or current.get("kind") != "HTTP" or current.get("traceId") != trace:
        current = {"kind": "HTTP", "traceId": trace, "modules": {}}
    else:
        current = {**current, "modules": dict(current.get("modules") or {})}
    module = str(lifecycle["moduleKey"])
    key = f"{int(tenant_id)}:{module}"
    snapshot = {
        "tenantId": int(tenant_id),
        "moduleKey": module,
        "generation": int(lifecycle["generation"]),
        "lifecycleVersion": int(lifecycle.get("lifecycleVersion") or 0),
    }
    existing = current["modules"].get(key)
    if existing and int(existing["generation"]) != snapshot["generation"]:
        raise AppException(
            "DATA_CONFLICT",
            "同一请求观察到模块代次变化，已拒绝继续写入",
            details={"previousGeneration": existing["generation"], "currentGeneration": snapshot["generation"]},
            http_status=409,
        )
    current["modules"][key] = snapshot
    _write_fence_ctx.set(current)


@contextmanager
def module_write_fence(tenant_id: int, module_key: str, expected_generation: int):
    """Explicit worker/CLI fence; task payload must supply the immutable generation."""
    from app.services.module_commerce_lifecycle_service import canonical_module

    module = canonical_module(module_key)
    generation = int(expected_generation or 0)
    if generation <= 0:
        raise AppException("VALIDATION_ERROR", "后台任务缺少有效 moduleGeneration", http_status=422)
    token = _write_fence_ctx.set({
        "kind": "WORKER",
        "traceId": "-",
        "modules": {
            f"{int(tenant_id)}:{module}": {
                "tenantId": int(tenant_id),
                "moduleKey": module,
                "generation": generation,
                "lifecycleVersion": None,
            }
        },
    })
    try:
        yield
    finally:
        _write_fence_ctx.reset(token)


def _active_fences() -> list[dict[str, Any]]:
    from app.core.context import get_trace_id

    current = _write_fence_ctx.get()
    if not current:
        return []
    if current.get("kind") == "HTTP":
        trace = str(get_trace_id() or "-")
        if trace == "-" or trace != current.get("traceId"):
            return []
    return sorted(
        list((current.get("modules") or {}).values()),
        key=lambda item: (int(item["tenantId"]), str(item["moduleKey"])),
    )


def _assert_final_fences(session) -> None:
    fences = _active_fences()
    if not fences:
        return
    from sqlalchemy import select
    from app.models import (
        TenantCommercialProfile,
        TenantModuleState,
        TenantModuleSubscriptionSource,
    )

    # Acquire module/source locks first, then shared profile locks. Fulfillment
    # also reaches the profile after module/source rows; reversing that order here
    # would introduce a profile/source lock inversion. Shared profile locks allow
    # independent module business writes without serializing the whole school.
    locked_modules = []
    for fence in fences:
        tid = int(fence["tenantId"])
        module = str(fence["moduleKey"])
        expected_generation = int(fence["generation"])
        state = session.scalars(select(TenantModuleState).where(
            TenantModuleState.tenant_id == tid,
            TenantModuleState.module_key == module,
            TenantModuleState.is_deleted.is_(False),
        ).with_for_update().execution_options(populate_existing=True)).first()
        if state is None:
            raise AppException(
                "DATA_CONFLICT", "模块实例状态不存在，旧请求/任务不能提交新事实",
                details={"tenantId": str(tid), "moduleKey": module}, http_status=409,
            )
        generation = int(state.generation or 0)
        if generation != expected_generation:
            raise AppException(
                "DATA_CONFLICT",
                "模块实例代次已变化，旧请求/任务不能提交新事实",
                details={
                    "expectedGeneration": expected_generation,
                    "currentGeneration": generation,
                    "moduleKey": module,
                },
                http_status=409,
            )
        data_state = str(state.data_state or "AVAILABLE").upper()
        if data_state != "AVAILABLE":
            raise AppException(
                "NO_PERMISSION",
                "模块已冻结或进入保留阶段，本次业务事务已回滚",
                details={"moduleKey": module, "dataState": data_state, "generation": generation},
                http_status=403,
            )

        # A locking SELECT alone does not overwrite a resident ORM instance.
        # Refresh locked source rows too; an old identity-map value is not evidence
        # of the current contract. Keep future sources so a scheduled renewal that
        # starts during lock contention can be assessed at the final timestamp.
        query_time = datetime.utcnow()
        sources = list(session.scalars(select(TenantModuleSubscriptionSource).where(
            TenantModuleSubscriptionSource.tenant_id == tid,
            TenantModuleSubscriptionSource.module_key == module,
            TenantModuleSubscriptionSource.module_generation == generation,
            TenantModuleSubscriptionSource.status.in_(('ACTIVE', 'SCHEDULED')),
            TenantModuleSubscriptionSource.ends_at > query_time,
            TenantModuleSubscriptionSource.is_deleted.is_(False),
        ).order_by(TenantModuleSubscriptionSource.id).with_for_update()
          .execution_options(populate_existing=True)).all())
        locked_modules.append((tid, module, generation, sources))

    profiles = {}
    for tid in sorted({item[0] for item in locked_modules}):
        profiles[tid] = session.scalars(select(TenantCommercialProfile).where(
            TenantCommercialProfile.tenant_id == tid,
            TenantCommercialProfile.is_deleted.is_(False),
        ).with_for_update(read=True).execution_options(populate_existing=True)).first()

    # Sample once AFTER every potentially blocking lock, not before its SQL was
    # submitted. An earlier module's contract can expire while a later module or
    # the reader-cutover profile is contended. Validate all sources at this same
    # final fence point; no persisted source status/time is modified here.
    now = datetime.utcnow()
    for tid, module, generation, sources in locked_modules:
        profile = profiles[tid]
        if profile is not None and str(profile.reader_version) == 'MODULE_V2':
            if not any(
                row.starts_at is not None and row.ends_at is not None
                and row.starts_at <= now < row.ends_at
                for row in sources
            ):
                raise AppException(
                    'NO_PERMISSION',
                    '模块商业授权已结束，本次业务事务已回滚',
                    details={'moduleKey': module, 'generation': generation},
                    http_status=403,
                )


def _install_final_commit_listener() -> None:
    global _final_commit_listener_installed
    if _final_commit_listener_installed:
        return
    from sqlalchemy import event
    from sqlalchemy.orm import Session

    event.listen(Session, "before_commit", _assert_final_fences)
    _final_commit_listener_installed = True


def install(module):
    if getattr(module, "_module_commerce_m4_fence_installed", False):
        _install_final_commit_listener()
        return module

    original_state = module.module_access_state

    def module_access_state(tenant_id: int, module_key: str) -> dict[str, Any]:
        state = dict(original_state(int(tenant_id), module_key))
        lifecycle = _lifecycle(int(tenant_id), module_key)
        if lifecycle is None:
            return state
        state.update(lifecycle)
        data_state = lifecycle["dataState"]
        if data_state in _BLOCKED_DATA_STATES:
            state["ready"] = False
            state["healthy"] = False
            state["allowed"] = False
            state["writable"] = False
            state["readonly"] = True
            state["reasonCode"] = f"MODULE_DATA_{data_state}"
            state["reason"] = {
                "FROZEN": "模块已进入退出冻结，普通业务访问已停止",
                "RETAINED": "模块处于合规保留期，仅允许退出管理与受控导出",
                "PURGING": "模块已进入不可逆清理阶段，普通业务访问已停止",
                "PURGED": "模块数据实例已销毁，旧代次不可恢复",
            }[data_state]
        return state

    def assert_module_access(
        tenant_id: int,
        module_key: str,
        *,
        write: bool = False,
        expected_generation: int | None = None,
    ) -> dict:
        from app.core.exceptions import no_permission
        from app.services import audit_log

        state = module_access_state(int(tenant_id), module_key)
        if expected_generation is not None:
            generation = int(state.get("generation") or 0)
            if generation and generation != int(expected_generation):
                raise AppException(
                    "DATA_CONFLICT",
                    "模块实例代次已变化，旧请求/任务不能提交新事实",
                    details={
                        "expectedGeneration": int(expected_generation),
                        "currentGeneration": generation,
                        "moduleKey": state.get("moduleKey") or module_key,
                    },
                    http_status=409,
                )
        denied = (
            not state.get("entitled")
            or not state.get("enabled")
            or not state.get("allowed")
            or (write and not state.get("writable"))
        )
        if denied:
            try:
                audit_log.record(
                    "MODULE_DENIED",
                    f"module:{state.get('featureKey') or module_key}",
                    detail={"state": state, "write": bool(write), "expectedGeneration": expected_generation},
                    result="DENIED",
                )
            except Exception:
                pass
            raise no_permission(state.get("reason") or f"该模块不可用：{module_key}")
        _remember_http_fence(int(tenant_id), state)
        return state

    module.module_access_state = module_access_state
    module.assert_module_access = assert_module_access
    module._module_commerce_m4_fence_installed = True
    _install_final_commit_listener()
    return module
