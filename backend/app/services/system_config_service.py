"""系统配置服务（真实可编辑 + 真实生效）。

只暴露"改了确实影响系统行为"的配置项，杜绝 inert 假配置：
- SEC_LOCK_MAX_FAIL  登录失败锁定阈值 —— 被 auth 登录失败逻辑真实读取（record_login_failure）
- SEC_LOCK_MINUTES   锁定时长（分钟） —— 同上
- SEC_PASSWORD_MIN_LEN 密码最小长度   —— 被改密/重置校验真实读取

缺表/无对应行时回落到 DEFAULTS，保证平滑上线。值域受 _RANGES 约束，越界拒绝。
"""
from __future__ import annotations

from app.core.context import current_tenant_id
from app.core.exceptions import AppException

# key → (分组, 展示名, 默认值, 值单位说明)
DEFAULTS = [
    {"key": "SEC_LOCK_MAX_FAIL", "group": "安全策略", "name": "登录失败锁定阈值（次）", "value": "5"},
    {"key": "SEC_LOCK_MINUTES", "group": "安全策略", "name": "锁定时长（分钟）", "value": "15"},
    {"key": "SEC_PASSWORD_MIN_LEN", "group": "安全策略", "name": "密码最小长度（位）", "value": "8"},
]
_DEFAULT_MAP = {d["key"]: d for d in DEFAULTS}
# 值域校验：越界拒绝，防止把阈值配成 0 之类导致锁死/失效
_RANGES = {"SEC_LOCK_MAX_FAIL": (3, 10), "SEC_LOCK_MINUTES": (5, 120), "SEC_PASSWORD_MIN_LEN": (6, 32)}


def _tid() -> int:
    return int(current_tenant_id() or 1000000000000000001)


def get_int(key: str, fallback: int | None = None) -> int:
    """当前租户某配置的生效整数值：优先 t_sys_config，缺失回落 DEFAULTS/传入 fallback。
    供强制层（登录锁定/密码校验）真实读取。任何异常都回落默认，绝不因配置读取失败阻断登录。"""
    default = fallback if fallback is not None else int(_DEFAULT_MAP.get(key, {}).get("value", 0))
    try:
        from app.db.session import db_enabled, get_sessionmaker
        if not db_enabled():
            return default
        from sqlalchemy import select
        from app.models import SysConfig
        db = get_sessionmaker()()
        try:
            row = db.scalars(select(SysConfig).where(SysConfig.tenant_id == _tid(),
                             SysConfig.config_key == key, SysConfig.is_deleted.is_(False))).first()
            if row is None or row.value_text is None:
                return default
            return int(str(row.value_text).strip())
        finally:
            db.close()
    except Exception:
        return default


def list_configs() -> list[dict]:
    """配置列表：DEFAULTS 基线叠加本租户已保存值（真实生效值）。"""
    from app.db.session import db_enabled, get_sessionmaker
    saved: dict[str, object] = {}
    if db_enabled():
        from sqlalchemy import select
        from app.models import SysConfig
        db = get_sessionmaker()()
        try:
            for row in db.scalars(select(SysConfig).where(SysConfig.tenant_id == _tid(),
                                  SysConfig.is_deleted.is_(False))).all():
                saved[row.config_key] = row
        finally:
            db.close()
    items = []
    for d in DEFAULTS:
        row = saved.get(d["key"])
        items.append({
            "key": d["key"], "group": d["group"], "name": d["name"],
            "valueText": (row.value_text if row is not None else d["value"]),
            "defaultValue": d["value"], "effective": True, "sensitive": False,
            "updatedAt": str(getattr(row, "updated_at", "") or "")[:19] if row is not None else "",
            "updatedBy": str(getattr(row, "updated_by", "") or "") if row is not None else "",
        })
    return items


def save_config(user: dict, key: str, value_text: str, reason: str = "") -> dict:
    from app.db.session import get_sessionmaker
    from sqlalchemy import select
    from app.models import SysConfig
    key = str(key or "").strip().upper()
    if key not in _DEFAULT_MAP:
        raise AppException("VALIDATION_ERROR", "未知或不可编辑的配置项")
    raw = str(value_text if value_text is not None else "").strip()
    lo, hi = _RANGES[key]
    try:
        num = int(raw)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{_DEFAULT_MAP[key]['name']}必须是整数")
    if not (lo <= num <= hi):
        raise AppException("VALIDATION_ERROR", f"{_DEFAULT_MAP[key]['name']}取值须在 {lo}–{hi} 之间")
    tid = _tid()
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(SysConfig).where(SysConfig.tenant_id == tid,
                         SysConfig.config_key == key, SysConfig.is_deleted.is_(False))).first()
        before = row.value_text if row is not None else _DEFAULT_MAP[key]["value"]
        if row is None:
            row = SysConfig(tenant_id=tid, config_key=key, config_group=_DEFAULT_MAP[key]["group"],
                            config_name=_DEFAULT_MAP[key]["name"], value_text=str(num), sensitive=False)
            db.add(row)
        else:
            row.value_text = str(num)
            row.version = int(row.version or 0) + 1
        db.commit()
        from app.services import audit_log
        audit_log.record("CONFIG_CHANGE", f"系统配置「{_DEFAULT_MAP[key]['name']}」",
                         detail={"key": key, "before": str(before), "after": str(num), "reason": reason,
                                 "summary": "系统配置变更（真实生效）"})
        return {"key": key, "valueText": str(num)}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
