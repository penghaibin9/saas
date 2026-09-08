"""M4 module-generation/data-state fence installed on the canonical access service.

The commercial authority still decides purchase. This wrapper adds only the
independent module-data lifecycle fence, so FROZEN/RETAINED/PURGING/PURGED
cannot be bypassed by a still-valid role or stale paid-order entitlement.
"""
from __future__ import annotations

from typing import Any

from app.core.exceptions import AppException

_BLOCKED_DATA_STATES = {"FROZEN", "RETAINED", "PURGING", "PURGED"}


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


def install(module):
    if getattr(module, "_module_commerce_m4_fence_installed", False):
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
                    detail={
                        "state": state,
                        "write": bool(write),
                        "expectedGeneration": expected_generation,
                    },
                    result="DENIED",
                )
            except Exception:
                pass
            raise no_permission(state.get("reason") or f"该模块不可用：{module_key}")
        return state

    module.module_access_state = module_access_state
    module.assert_module_access = assert_module_access
    module._module_commerce_m4_fence_installed = True
    return module
