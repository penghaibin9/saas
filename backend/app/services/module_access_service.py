"""模块四态：entitled / enabled / ready / healthy。

规则：
- entitled：平台套餐/订单是否授权（feature_enabled）
- enabled：学校是否在已购范围内启用（MODULE_FEATURES）
- ready：基础数据与配置是否齐全（实施检查）
- healthy：运行是否正常（同步失败/安全风险等）

学校只能在已购买范围内启停；停用不删历史；到期默认禁止新增修改。
"""
from __future__ import annotations

from typing import Any


def _school_enabled_map(tenant_id: int) -> dict[str, bool]:
    from app.services import system_governance_service as gov
    features = gov.get_module_features()
    out = {}
    for key, val in (features or {}).items():
        if isinstance(val, dict):
            out[key] = bool(val.get("enabled", True))
    return out


def module_access_state(tenant_id: int, module_key: str) -> dict[str, Any]:
    from app.core.module_registry import resolve_feature_key, resolve_module
    from app.services.platform_service import feature_enabled, tenant_meta

    mod = resolve_module(module_key)
    feature_key = resolve_feature_key(module_key)
    if feature_key is None:
        return {
            "moduleKey": module_key,
            "featureKey": None,
            "entitled": False,
            "enabled": False,
            "ready": False,
            "healthy": False,
            "writable": False,
            "reason": f"未知功能键：{module_key}",
        }

    entitled = True
    if mod is None or mod.get("entitlementRequired", True):
        entitled = bool(feature_enabled(int(tenant_id), feature_key))

    school_map = _school_enabled_map(int(tenant_id))
    # 学校开关键优先用 moduleKey / graduationDesign 等业务键
    school_key = (mod or {}).get("moduleKey") or module_key
    if school_key == "graduation":
        school_key = "graduationDesign"
    enabled = bool(school_map.get(school_key, school_map.get(feature_key, True))) if entitled else False

    try:
        from app.services.tenant_effective_state_service import get_effective_state
        effective_state = get_effective_state(int(tenant_id), strict=True)
        status = str(effective_state["effectiveStatus"]).upper()
        state_error = ""
    except Exception:
        status = "UNRESOLVED"
        state_error = "租户状态无法确定，已按安全策略拒绝"
    expired = status in ("EXPIRED", "SUSPENDED", "DISABLED", "ARCHIVED", "UNRESOLVED")
    readonly = status in ("READONLY", "EXPIRED", "SUSPENDED", "DISABLED", "ARCHIVED", "UNRESOLVED")

    ready = entitled and enabled and not state_error  # 详细 ready 由上线检查补充
    healthy = ready

    writable = entitled and enabled and not expired and not readonly and not state_error
    reason = state_error
    if state_error:
        reason = state_error
    elif not entitled:
        reason = f"模块未购买或未授权：{feature_key}"
    elif not enabled:
        reason = f"学校已停用模块：{school_key}（历史可查，恢复后可写）"
    elif expired:
        reason = "授权已到期，禁止新增修改"
    elif readonly:
        reason = "租户只读，仅允许查询与合规导出"

    return {
        "moduleKey": school_key,
        "featureKey": feature_key,
        "entitled": entitled,
        "enabled": enabled,
        "ready": ready,
        "healthy": healthy,
        "writable": writable,
        "readonly": readonly or (entitled and enabled and expired),
        "reason": reason,
    }


def assert_module_access(tenant_id: int, module_key: str, *, write: bool = False) -> dict:
    from app.core.exceptions import no_permission
    from app.services import audit_log

    state = module_access_state(tenant_id, module_key)
    if not state["entitled"] or not state["enabled"]:
        try:
            audit_log.record(
                "MODULE_DENIED",
                f"module:{state.get('featureKey') or module_key}",
                detail={"state": state, "write": write},
                result="DENIED",
            )
        except Exception:
            pass
        raise no_permission(state["reason"] or f"该模块不可用：{module_key}")
    if write and not state["writable"]:
        try:
            audit_log.record(
                "MODULE_DENIED",
                f"module:{state.get('featureKey') or module_key}",
                detail={"state": state, "write": True, "reason": "readonly"},
                result="DENIED",
            )
        except Exception:
            pass
        raise no_permission(state["reason"] or "模块当前禁止写入")
    return state
