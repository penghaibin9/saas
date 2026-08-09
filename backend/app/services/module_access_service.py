"""模块四态：entitled / enabled / ready / allowed（healthy 保留为兼容别名）。

规则：
- entitled：平台套餐/订单是否授权（feature_enabled）
- enabled：学校是否在已购范围内启用（SYS-13 t_tenant_capability_setting）
- ready：依赖能力齐全且启用期限未过
- allowed：最终可用 = entitled ∧ enabled ∧ ready ∧ 租户状态正常

学校只能在已购买范围内启停；停用不删历史；到期默认禁止新增修改。
读取学校开关失败时必须向上抛 503——返回空 dict 会被解释成"全部启用"。

性能约束：current-context 会在一次请求内遍历全部模块。套餐功能、学校开关、租户有效状态
属于同一 tenant + 同一 request 的稳定快照，只允许各读取一次；快照以 traceId + tenantId 隔离，
跨请求绝不复用，避免权限/授权变更后的陈旧状态。
"""
from __future__ import annotations

from contextvars import ContextVar
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

# 仅请求上下文内复用。traceId="-"（脚本/单测/非 HTTP）时不缓存，避免跨调用陈旧。
_request_snapshot: ContextVar[dict[str, Any] | None] = ContextVar(
    "module_access_request_snapshot", default=None)


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


def _load_effective_state(tenant_id: int) -> tuple[str, str]:
    try:
        from app.services.tenant_effective_state_service import get_effective_state

        # 存量租户可能尚未生成 TENANT_META。此时以关系表硬状态作为兼容权威，
        # 但未知状态、非法到期时间等解析错误仍必须 fail-closed。
        effective_state = get_effective_state(int(tenant_id), strict=False)
        status = str(effective_state["effectiveStatus"]).upper()
        state_errors = list(effective_state.get("errors") or [])
        state_error = "租户状态无法确定，已按安全策略拒绝" if state_errors else ""
        return status, state_error
    except Exception:
        return "UNRESOLVED", "租户状态无法确定，已按安全策略拒绝"


def _load_request_snapshot(tenant_id: int) -> dict[str, Any]:
    """读取本次请求的模块授权输入快照；同 traceId+tenantId 只做一次 DB/配置读取。"""
    from app.core.context import get_trace_id
    from app.services.platform_service import effective_features

    tid = int(tenant_id)
    trace_id = str(get_trace_id() or "-")
    cached = _request_snapshot.get()
    if trace_id != "-" and cached and cached.get("traceId") == trace_id and cached.get("tenantId") == tid:
        return cached

    # feature_enabled 的既有安全语义是：功能配置读取异常时 fail-closed 为未授权。
    try:
        entitled_features = effective_features(tid)
    except Exception:
        entitled_features = {}

    # 学校开关读取失败必须向上抛出，不能伪装成“全部启用”。
    school_gate = _school_gate(tid)
    status, state_error = _load_effective_state(tid)
    snapshot = {
        "traceId": trace_id,
        "tenantId": tid,
        "entitledFeatures": entitled_features,
        "schoolGate": school_gate,
        "tenantStatus": status,
        "tenantStateError": state_error,
    }
    if trace_id != "-":
        _request_snapshot.set(snapshot)
    return snapshot


def _state_from_snapshot(tenant_id: int, module_key: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    from app.core.module_registry import resolve_feature_key, resolve_module

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
        entitled = bool((snapshot.get("entitledFeatures") or {}).get(feature_key, False))

    gate = snapshot.get("schoolGate") or {}
    # 学校开关键优先用 moduleKey / graduationDesign 等业务键
    school_key = (mod or {}).get("moduleKey") or module_key
    if school_key == "graduation":
        school_key = "graduationDesign"
    school = gate.get(school_key) or gate.get(feature_key) or {}
    school_enabled = bool(school.get("enabled", True))
    school_reason_code = str(school.get("reasonCode") or "")
    enabled = school_enabled if entitled else False

    status = str(snapshot.get("tenantStatus") or "UNRESOLVED").upper()
    state_error = str(snapshot.get("tenantStateError") or "")
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


def module_access_state(tenant_id: int, module_key: str) -> dict[str, Any]:
    """计算单模块四态；同一 HTTP 请求的底层授权输入自动复用。"""
    snapshot = _load_request_snapshot(int(tenant_id))
    return _state_from_snapshot(int(tenant_id), module_key, snapshot)


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
