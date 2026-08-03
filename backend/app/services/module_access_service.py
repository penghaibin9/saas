"""模块四态：entitled / enabled / ready / allowed（healthy 保留为兼容别名）。

规则：
- entitled：平台套餐/订单是否授权（feature_enabled）
- enabled：学校是否在已购范围内启用（SYS-13 t_tenant_capability_setting）
- ready：依赖能力齐全且启用期限未过
- allowed：最终可用 = entitled ∧ enabled ∧ ready ∧ 租户状态正常

学校只能在已购买范围内启停；停用不删历史；到期默认禁止新增修改。
读取学校开关失败时必须向上抛 503——返回空 dict 会被解释成"全部启用"。
"""
from __future__ import annotations

from typing import Any

REASON_OK = "OK"
REASON_UNKNOWN_MODULE = "UNKNOWN_MODULE"
REASON_NOT_ENTITLED = "NOT_ENTITLED"
REASON_SCHOOL_DISABLED = "SCHOOL_DISABLED"
REASON_DEPENDENCY_UNMET = "DEPENDENCY_UNMET"
REASON_CAPABILITY_EXPIRED = "CAPABILITY_EXPIRED"
REASON_TENANT_UNRESOLVED = "TENANT_UNRESOLVED"
REASON_TENANT_EXPIRED = "TENANT_EXPIRED"
REASON_TENANT_READONLY = "TENANT_READONLY"


def _school_gate(tenant_id: int) -> dict[str, dict]:
    """学校侧开关表（含依赖传播）。读取失败由 get_module_features 抛 503，此处不吞。"""
    from app.services import system_governance_service as gov
    features = gov.get_module_features(int(tenant_id) or None)
    out: dict[str, dict] = {}
    for key, val in (features or {}).items():
        if not isinstance(val, dict):
            continue
        unmet = list(val.get("dependencyUnmet") or [])
        reason_code = str(val.get("reasonCode") or "")
        out[key] = {
            "enabled": bool(val.get("enabled", True)) and not unmet,
            "reasonCode": reason_code,
            "reason": str(val.get("reason") or ""),
            "dependencyUnmet": unmet,
        }
    return out


def _school_enabled_map(tenant_id: int) -> dict[str, bool]:
    return {key: bool(val["enabled"]) for key, val in _school_gate(tenant_id).items()}


def module_access_state(tenant_id: int, module_key: str) -> dict[str, Any]:
    from app.core.module_registry import resolve_feature_key, resolve_module
    from app.services.platform_service import feature_enabled

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
            "allowed": False,
            "writable": False,
            "reasonCode": REASON_UNKNOWN_MODULE,
            "reason": f"未知功能键：{module_key}",
        }

    entitled = True
    if mod is None or mod.get("entitlementRequired", True):
        entitled = bool(feature_enabled(int(tenant_id), feature_key))

    gate = _school_gate(int(tenant_id))
    # 学校开关键优先用 moduleKey / graduationDesign 等业务键
    school_key = (mod or {}).get("moduleKey") or module_key
    if school_key == "graduation":
        school_key = "graduationDesign"
    school = gate.get(school_key) or gate.get(feature_key) or {}
    school_enabled = bool(school.get("enabled", True))
    school_reason_code = str(school.get("reasonCode") or "")
    enabled = school_enabled if entitled else False

    try:
        from app.services.tenant_effective_state_service import get_effective_state

        # 存量租户可能尚未生成 TENANT_META。此时以关系表硬状态作为兼容权威，
        # 但未知状态、非法到期时间等解析错误仍必须 fail-closed。
        effective_state = get_effective_state(int(tenant_id), strict=False)
        status = str(effective_state["effectiveStatus"]).upper()
        state_errors = list(effective_state.get("errors") or [])
        state_error = "租户状态无法确定，已按安全策略拒绝" if state_errors else ""
    except Exception:
        status = "UNRESOLVED"
        state_error = "租户状态无法确定，已按安全策略拒绝"
    expired = status in ("EXPIRED", "SUSPENDED", "DISABLED", "ARCHIVED", "UNRESOLVED")
    readonly = status in ("READONLY", "EXPIRED", "SUSPENDED", "DISABLED", "ARCHIVED", "UNRESOLVED")

    ready = entitled and enabled and not state_error  # 详细 ready 由上线检查补充
    healthy = ready
    allowed = ready and not expired

    writable = entitled and enabled and not expired and not readonly and not state_error
    reason = state_error
    reason_code = REASON_OK
    if state_error:
        reason = state_error
        reason_code = REASON_TENANT_UNRESOLVED
    elif not entitled:
        reason = f"模块未购买或未授权：{feature_key}"
        reason_code = REASON_NOT_ENTITLED
    elif not enabled:
        # 学校侧的具体原因（停用 / 依赖不满足 / 启用期限到期）由能力服务给出，不在这里重新判断
        reason = school.get("reason") or f"学校已停用模块：{school_key}（历史可查，恢复后可写）"
        reason_code = school_reason_code or REASON_SCHOOL_DISABLED
    elif expired:
        reason = "授权已到期，禁止新增修改"
        reason_code = REASON_TENANT_EXPIRED
    elif readonly:
        reason = "租户只读，仅允许查询与合规导出"
        reason_code = REASON_TENANT_READONLY

    return {
        "moduleKey": school_key,
        "featureKey": feature_key,
        "entitled": entitled,
        "enabled": enabled,
        "ready": ready,
        "healthy": healthy,
        "allowed": allowed,
        "writable": writable,
        "readonly": readonly or (entitled and enabled and expired),
        "reasonCode": reason_code,
        "reason": reason,
        "dependencyUnmet": list(school.get("dependencyUnmet") or []),
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
