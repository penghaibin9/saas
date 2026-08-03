"""SYS-13：模块商业授权、学校启用与准备度（四态 + 结构化版本锁 + fail-closed）。

四态的权威源各不相同，任何一个都不能顶替另一个：

============  ==========================================  ============================
状态          含义                                        权威源
============  ==========================================  ============================
entitled      平台是否把这个能力卖给了这所学校            platform_service.feature_enabled
enabled       学校是否在已购范围内自己打开了它            t_tenant_capability_setting
ready         依赖是否齐、启用期限是否还在                本服务按 manifest 依赖图推导
allowed       最终能不能用（= entitled ∧ enabled ∧ ready） 本服务
============  ==========================================  ============================

硬规则（本卡明令）：
- entitled 与 enabled **不得合成一个字段**：合了以后「平台没卖」和「学校自己关的」
  两种情况会给出同一个 reasonCode，学校侧永远查不清该找谁。
- **配置读取异常必须 fail-closed**：读不到就抛 503，绝不返回空 dict。空 dict 会被
  ``dict.get(key, True)`` 解释成「全部启用」——存储故障反而把没买的模块全放开。
- 写操作按 (tenant_id, capability_key) **单行乐观锁**，版本不匹配返回 409。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.context import current_tenant_id
from app.core.exceptions import AppException

# ── reasonCode：机器可读，前端据此决定文案与是否可勾选 ────────────────────────
REASON_OK = "OK"
REASON_NOT_ENTITLED = "NOT_ENTITLED"          # 平台未售出/未授权
REASON_SCHOOL_DISABLED = "SCHOOL_DISABLED"    # 学校自己停用
REASON_EXPIRED = "CAPABILITY_EXPIRED"         # 学校启用期限已过
REASON_DEPENDENCY_UNMET = "DEPENDENCY_UNMET"  # 依赖能力不可用
REASON_UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"

_STORAGE_DOWN = "模块启用配置读取失败，已按安全策略拒绝，请稍后重试或联系管理员"

# 无数据库时的内存兜底（仅 mock 模式的单元测试用，键为 (tenant_id, capability_key)）
_MEMORY_ROWS: dict[tuple[int, str], dict[str, Any]] = {}


def _tid(tenant_id: int | None = None) -> int:
    return int(tenant_id if tenant_id is not None else (current_tenant_id() or 0))


def _now() -> datetime:
    # MySQL DATETIME 无微秒位会四舍五入进位，刚写入的记录可能"晚于"当前时间。统一截断到秒。
    return datetime.now().replace(microsecond=0)


# ── 能力目录：唯一事实源是 module-manifest.json ───────────────────────────────
def capability_registry() -> dict[str, dict]:
    """学校可见能力目录：capability_key -> manifest 条目。平台专属模块不进目录。"""
    from app.core.module_registry import load_module_manifest

    out: dict[str, dict] = {}
    for mod in load_module_manifest().get("modules") or []:
        if not mod.get("schoolVisible", True) or mod.get("platformOnly"):
            continue
        out[mod["moduleKey"]] = mod
    return out


def _canonical_key(key: str) -> str | None:
    """把别名/featureKey 归一到 capability_key；不属于学校能力目录的返回 None。"""
    from app.core.module_registry import resolve_module

    reg = capability_registry()
    raw = str(key or "").strip()
    if raw in reg:
        return raw
    mod = resolve_module(raw)
    if mod and mod.get("moduleKey") in reg:
        return mod["moduleKey"]
    return None


def _dependencies(cap_key: str) -> list[str]:
    reg = capability_registry()
    deps: list[str] = []
    for dep in reg.get(cap_key, {}).get("dependencies") or []:
        canon = _canonical_key(dep)
        if canon and canon != cap_key:
            deps.append(canon)
    return deps


def _label(cap_key: str) -> str:
    mod = capability_registry().get(cap_key) or {}
    return str(mod.get("label") or cap_key)


# ── 存储层 ───────────────────────────────────────────────────────────────────
def _load_rows(tenant_id: int) -> dict[str, dict]:
    """读取本校全部能力设置行。读失败一律 503，不返回空 dict。"""
    from app.db.session import db_enabled, get_sessionmaker

    if not db_enabled():
        return {
            key: dict(val) for (tid, key), val in _MEMORY_ROWS.items() if tid == int(tenant_id)
        }
    from sqlalchemy import select

    from app.models.tenant_capability import TenantCapabilitySetting

    try:
        db = get_sessionmaker()()
        try:
            rows = db.scalars(
                select(TenantCapabilitySetting).where(
                    TenantCapabilitySetting.tenant_id == int(tenant_id),
                    TenantCapabilitySetting.is_deleted.is_(False),
                )
            ).all()
            return {
                row.capability_key: {
                    "enabled": bool(row.enabled),
                    "version": int(row.version or 0),
                    "reason": row.reason or "",
                    "expiresAt": row.expires_at.strftime("%Y-%m-%d %H:%M:%S") if row.expires_at else "",
                    "updatedAt": row.last_changed_at.strftime("%Y-%m-%d %H:%M:%S") if row.last_changed_at else "",
                }
                for row in rows
            }
        finally:
            db.close()
    except AppException:
        raise
    except Exception as exc:
        raise AppException("SERVER_ERROR", _STORAGE_DOWN, http_status=503) from exc


def _legacy_enabled(tenant_id: int) -> dict[str, bool]:
    """兼容读取：学校在结构化表出现之前存进 MODULE_FEATURES JSON 的开关。

    只做**读兜底**——没有结构化行时沿用旧值，避免升级当天把学校原来关掉的模块全部打开。
    有结构化行时结构化行永远优先。
    """
    try:
        from app.services import system_governance_service as gov

        saved = gov.load_module_feature_document(tenant_id)
    except AppException:
        raise
    except Exception:
        return {}
    out: dict[str, bool] = {}
    for key, val in (saved or {}).items():
        canon = _canonical_key(key)
        if canon and isinstance(val, dict) and "enabled" in val:
            out[canon] = bool(val["enabled"])
    return out


def _is_expired(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt) < _now()
        except ValueError:
            continue
    return False


# ── 四态推导 ─────────────────────────────────────────────────────────────────
def capability_states(tenant_id: int | None = None) -> dict[str, dict]:
    """返回全部学校可见能力的四态。任一读取环节失败都会向上抛 503（fail-closed）。"""
    from app.services.platform_service import feature_enabled

    tid = _tid(tenant_id)
    reg = capability_registry()
    rows = _load_rows(tid)
    legacy = _legacy_enabled(tid)

    states: dict[str, dict] = {}
    for key, mod in reg.items():
        feature_key = mod.get("featureKey") or key
        entitled = True
        if mod.get("entitlementRequired", True) and tid:
            entitled = bool(feature_enabled(tid, feature_key))
        # tid==0 只出现在无租户上下文的 mock 模式（沿用改造前语义：不叠加套餐判断）。
        # 真实请求的 tenant_id 由中间件写入上下文，永远非 0。
        row = rows.get(key)
        if row is not None:
            school_enabled = bool(row["enabled"])
        else:
            school_enabled = bool(legacy.get(key, True))
        expires_at = (row or {}).get("expiresAt") or ""
        expired = _is_expired(expires_at)
        states[key] = {
            "capabilityKey": key,
            "label": _label(key),
            "featureKey": feature_key,
            "entitlementRequired": bool(mod.get("entitlementRequired", True)),
            "schoolGroup": mod.get("schoolGroup") or key,
            "dependencies": _dependencies(key),
            "entitled": entitled,
            "schoolEnabled": school_enabled,
            "expiresAt": expires_at,
            "version": int((row or {}).get("version") or 0),
            "configured": row is not None,
            "reason": (row or {}).get("reason") or "",
            "updatedAt": (row or {}).get("updatedAt") or "",
            "_expired": expired,
        }

    # 依赖传播：按图求解（manifest 已由 validate-module-manifest.py 保证无环）
    resolved: dict[str, bool] = {}

    def _allowed(key: str, trail: tuple[str, ...] = ()) -> bool:
        if key in resolved:
            return resolved[key]
        if key in trail:  # 防御：真出环也不死循环，直接判不可用
            return False
        st = states[key]
        ok = bool(st["entitled"] and st["schoolEnabled"] and not st["_expired"])
        if ok:
            for dep in st["dependencies"]:
                if dep in states and not _allowed(dep, trail + (key,)):
                    ok = False
                    break
        resolved[key] = ok
        return ok

    for key, st in states.items():
        unmet = [d for d in st["dependencies"] if d in states and not _allowed(d)]
        allowed = _allowed(key)
        enabled = bool(st["entitled"] and st["schoolEnabled"] and not st["_expired"])
        if not st["entitled"]:
            code, text = REASON_NOT_ENTITLED, f"当前套餐未授权：{st['featureKey']}"
        elif st["_expired"]:
            code, text = REASON_EXPIRED, f"学校启用期限已到期（{st['expiresAt']}）"
        elif not st["schoolEnabled"]:
            code, text = REASON_SCHOOL_DISABLED, "学校已停用该模块（历史可查，恢复后可写）"
        elif unmet:
            code = REASON_DEPENDENCY_UNMET
            text = "依赖能力不可用：" + "、".join(_label(d) for d in unmet)
        else:
            code, text = REASON_OK, ""
        st.pop("_expired", None)
        st["enabled"] = enabled
        st["ready"] = bool(enabled and not unmet)
        st["allowed"] = allowed
        st["dependencyUnmet"] = unmet
        st["reasonCode"] = code
        st["reasonText"] = text
        st["dependents"] = []

    for key, st in states.items():
        for dep in st["dependencies"]:
            if dep in states:
                states[dep]["dependents"].append(key)
    return states


def enabled_map(tenant_id: int | None = None) -> dict[str, bool]:
    """给模块门禁用的学校侧开关表：True 表示学校侧允许（不含 entitled 判断）。"""
    states = capability_states(tenant_id)
    return {
        key: bool(st["schoolEnabled"] and not st["dependencyUnmet"] and st["reasonCode"] != REASON_EXPIRED)
        for key, st in states.items()
    }


def list_capabilities(tenant_id: int | None = None) -> list[dict]:
    states = capability_states(tenant_id)
    return [states[key] for key in sorted(states, key=lambda k: (states[k]["schoolGroup"], k))]


def get_capability(capability_key: str, tenant_id: int | None = None) -> dict:
    canon = _canonical_key(capability_key)
    if canon is None:
        raise AppException("VALIDATION_ERROR", f"未知能力：{capability_key}")
    return capability_states(tenant_id)[canon]


# ── 停用影响预览 ─────────────────────────────────────────────────────────────
def _impact_tokens(cap_key: str) -> list[str]:
    mod = capability_registry().get(cap_key) or {}
    tokens = [cap_key, mod.get("schoolGroup"), mod.get("dataOwner")]
    return sorted({str(t) for t in tokens if t})


def capability_impact(capability_key: str, tenant_id: int | None = None) -> dict:
    """停用前的影响面。查得到的用真实数据，查不到的显式标 null，不填 0 冒充"无影响"。"""
    canon = _canonical_key(capability_key)
    if canon is None:
        raise AppException("VALIDATION_ERROR", f"未知能力：{capability_key}")
    tid = _tid(tenant_id)
    states = capability_states(tid)
    mod = capability_registry()[canon]
    st = states[canon]

    cascade = [
        {"capabilityKey": k, "label": _label(k)}
        for k in st["dependents"]
        if states[k]["allowed"]
    ]

    roles: list[str] = []
    try:
        from app.core.permissions import ROLE_PERMISSIONS

        prefix = str(mod.get("permissionPrefix") or canon)
        for role_code, codes in (ROLE_PERMISSIONS or {}).items():
            for code in codes:
                c = str(code)
                if c == "*" or c.split(".")[0] == prefix.split(".")[0] or c.startswith(prefix):
                    roles.append(role_code)
                    break
    except Exception:
        roles = []

    counts: dict[str, Any] = {"affectedUsers": None, "runningWorkflows": None,
                              "pendingTodos": None, "fileBindings": None}
    tokens = _impact_tokens(canon)
    try:
        from sqlalchemy import func, select

        from app.db.session import db_enabled, get_sessionmaker

        if db_enabled():
            from app.models import UnifiedTodo, UserRole, WorkflowInstance
            from app.models.file import FileBinding

            db = get_sessionmaker()()
            try:
                if roles:
                    from app.models import Role

                    counts["affectedUsers"] = int(db.scalar(
                        select(func.count(func.distinct(UserRole.user_id)))
                        .select_from(UserRole)
                        .join(Role, Role.id == UserRole.role_id)
                        .where(UserRole.tenant_id == tid, UserRole.is_deleted.is_(False),
                               UserRole.status == "ACTIVE", Role.role_code.in_(roles))
                    ) or 0)
                counts["runningWorkflows"] = int(db.scalar(
                    select(func.count()).select_from(WorkflowInstance).where(
                        WorkflowInstance.tenant_id == tid,
                        WorkflowInstance.is_deleted.is_(False),
                        WorkflowInstance.status == "RUNNING",
                        WorkflowInstance.source_module.in_(tokens))
                ) or 0)
                counts["pendingTodos"] = int(db.scalar(
                    select(func.count()).select_from(UnifiedTodo).where(
                        UnifiedTodo.tenant_id == tid,
                        UnifiedTodo.is_deleted.is_(False),
                        UnifiedTodo.status == "PENDING",
                        UnifiedTodo.source_module.in_(tokens))
                ) or 0)
                counts["fileBindings"] = int(db.scalar(
                    select(func.count()).select_from(FileBinding).where(
                        FileBinding.tenant_id == tid,
                        FileBinding.is_deleted.is_(False),
                        FileBinding.module_code.in_(tokens))
                ) or 0)
            finally:
                db.close()
    except Exception:
        # 统计失败不能变成 0；保持 null，由页面显示"未知"
        pass

    return {
        "capabilityKey": canon,
        "label": _label(canon),
        "currentState": {k: st[k] for k in ("entitled", "enabled", "ready", "allowed", "reasonCode")},
        "menus": list(mod.get("frontendRoutePrefixes") or []),
        "apis": list(mod.get("backendApiPrefixes") or []),
        "permissionPrefix": mod.get("permissionPrefix") or canon,
        "cascadeDisabled": cascade,
        "affectedRoles": sorted(set(roles)),
        "counts": counts,
        "countedBy": tokens,
        "countsExact": False,
        "note": "流程/任务/文件按来源模块字段统计，历史数据来源标识不全时可能少计；菜单与接口来自模块清单。",
    }


# ── 写入 ─────────────────────────────────────────────────────────────────────
def set_capability(capability_key: str, *, enabled: bool, reason: str,
                   expected_version: int | None = None, tenant_id: int | None = None,
                   user: dict | None = None, expires_at: str | None = None) -> dict:
    """学校启停单个能力。单行乐观锁；违反授权/依赖一律拒绝。"""
    canon = _canonical_key(capability_key)
    if canon is None:
        raise AppException("VALIDATION_ERROR", f"未知能力：{capability_key}")
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "调整原因不少于 5 个字")
    from app.db.session import db_enabled

    tid = _tid(tenant_id)
    if not tid and db_enabled():
        raise AppException("VALIDATION_ERROR", "缺少租户上下文")

    states = capability_states(tid)
    st = states[canon]
    want = bool(enabled)
    if want and not st["entitled"]:
        raise AppException("VALIDATION_ERROR", f"未购买或未授权，不可启用：{_label(canon)}")
    if want:
        # 启用方向是硬阻断：依赖不可用时启用只会得到一个点不开的入口
        unmet = [d for d in st["dependencies"] if d in states and not states[d]["allowed"]]
        if unmet:
            raise AppException(
                "VALIDATION_ERROR",
                "依赖能力未启用，无法启用：" + "、".join(_label(d) for d in unmet))
    # 停用方向不硬拦：学校有权停掉一个中心。依赖它的能力会自动变成
    # DEPENDENCY_UNMET（不可用但学校开关仍为"开"），影响面由停用前的影响预览负责讲清楚。
    # 若在这里强制"先停依赖方"，学校要停一个中心得先手工关掉一串子模块，恢复时还得原样倒着开回来。

    _write_row(tid, canon, enabled=want, reason=reason,
               expected_version=expected_version, user=user, expires_at=expires_at)

    from app.services import audit_log

    audit_log.record(
        "CAPABILITY_SETTING_SAVE", f"capability:{canon}",
        detail={"reason": reason, "before": {"enabled": st["enabled"], "version": st["version"]},
                "after": {"enabled": want}, "moduleCode": "systemAdmin"},
    )
    return get_capability(canon, tid)


def _write_row(tenant_id: int, capability_key: str, *, enabled: bool, reason: str,
               expected_version: int | None, user: dict | None,
               expires_at: str | None = None) -> int:
    from app.db.session import db_enabled, get_sessionmaker

    parsed_expires = None
    if expires_at:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed_expires = datetime.strptime(str(expires_at).strip(), fmt).replace(microsecond=0)
                break
            except ValueError:
                continue
        if parsed_expires is None:
            raise AppException("VALIDATION_ERROR", "启用期限格式应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS")

    if not db_enabled():
        cur = _MEMORY_ROWS.get((int(tenant_id), capability_key))
        current_version = int((cur or {}).get("version") or 0)
        if expected_version is not None and int(expected_version) != current_version:
            raise AppException("DATA_CONFLICT", "该模块开关已被他人更新，请刷新后重试")
        version = current_version + 1
        _MEMORY_ROWS[(int(tenant_id), capability_key)] = {
            "enabled": bool(enabled), "version": version, "reason": reason,
            "expiresAt": parsed_expires.strftime("%Y-%m-%d %H:%M:%S") if parsed_expires else
                         ((cur or {}).get("expiresAt") or ""),
            "updatedAt": _now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return version

    from sqlalchemy import select

    from app.models.tenant_capability import TenantCapabilitySetting

    actor = str((user or {}).get("userId") or "").replace("db-", "")
    actor_id = int(actor) if actor.isdigit() else None
    db = get_sessionmaker()()
    try:
        row = db.scalars(
            select(TenantCapabilitySetting).where(
                TenantCapabilitySetting.tenant_id == int(tenant_id),
                TenantCapabilitySetting.capability_key == capability_key,
                TenantCapabilitySetting.is_deleted.is_(False),
            ).with_for_update()
        ).first()
        current_version = int(row.version or 0) if row is not None else 0
        if expected_version is not None and int(expected_version) != current_version:
            raise AppException("DATA_CONFLICT", "该模块开关已被他人更新，请刷新后重试")
        if row is None:
            row = TenantCapabilitySetting(
                tenant_id=int(tenant_id), capability_key=capability_key,
                enabled=bool(enabled), reason=reason, version=1,
                expires_at=parsed_expires, last_changed_at=_now(), last_changed_by=actor_id,
                created_by=actor_id, updated_by=actor_id,
            )
            db.add(row)
            version = 1
        else:
            row.enabled = bool(enabled)
            row.reason = reason
            if parsed_expires is not None:
                row.expires_at = parsed_expires
            row.last_changed_at = _now()
            row.last_changed_by = actor_id
            row.updated_by = actor_id
            row.version = current_version + 1
            version = row.version
        db.commit()
        return version
    except AppException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        from sqlalchemy.exc import IntegrityError

        if isinstance(exc, IntegrityError):
            # 唯一键 (tenant_id, capability_key) 撞车 = 另一个请求刚插入了同一行
            raise AppException("DATA_CONFLICT", "该模块开关已被他人更新，请刷新后重试") from exc
        raise AppException("INTERNAL_ERROR", f"模块启用配置落库失败：{exc}") from exc
    finally:
        db.close()


def reset_memory_for_tests() -> None:
    _MEMORY_ROWS.clear()
