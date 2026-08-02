"""SYS-11 有效配置解析：一个 Resolver、一条来源链、一处平台底线校验。

继承链（后者覆盖前者）
──────────────────────
``PLATFORM_FLOOR`` → ``PACKAGE_DEFAULT`` → ``TENANT_LEGACY``(t_sys_config) →
``TENANT`` → ``ORG_UNIT`` → ``TERM``

其中 ``PLATFORM_FLOOR`` 不提供值，只提供**学校不得突破的区间**：越界在保存时直接拒绝，
不做静默夹逼——静默改小一个登录锁定阈值，比报错危险得多。

``TENANT_LEGACY`` 是既有 ``t_sys_config``。它今天就被 ``auth_service_db`` 真实读取，
所以升级后必须继续参与解析，否则学校已配置的登录锁定策略会在上线瞬间回到默认值。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.config_governance import (OVERRIDE_SCOPES,
                                          OVERRIDE_STATUS_ACTIVE,
                                          OVERRIDE_STATUS_REVOKED,
                                          SCOPE_ORG_UNIT, SCOPE_TENANT,
                                          SCOPE_TERM, SOURCE_PACKAGE_DEFAULT,
                                          SOURCE_PLATFORM_FLOOR,
                                          SOURCE_TENANT_LEGACY,
                                          ConfigActivation, ConfigDefinition,
                                          ConfigOverride)

# 覆盖层优先级：数字大的赢
_SCOPE_PRIORITY = {SCOPE_TENANT: 1, SCOPE_ORG_UNIT: 2, SCOPE_TERM: 3}

# 初始配置定义。consumer 是**代码里真实存在的读取点**，不是设想；
# 没有 consumer 的配置在页面上必须标注"暂无消费者"，不能声称即刻生效。
SEED_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "config_key": "SEC_LOCK_MAX_FAIL",
        "domain_code": "SECURITY",
        "config_name": "登录失败锁定阈值（次）",
        "value_type": "INT",
        "default_json": {"value": 5},
        "platform_floor_json": {"min": 3, "max": 10},
        "school_editable": True,
        "risk_level": "HIGH",
        "consumer_json": {"items": ["auth_service_db.record_login_failure"]},
    },
    {
        "config_key": "SEC_LOCK_MINUTES",
        "domain_code": "SECURITY",
        "config_name": "登录锁定时长（分钟）",
        "value_type": "INT",
        "default_json": {"value": 15},
        "platform_floor_json": {"min": 5, "max": 120},
        "school_editable": True,
        "risk_level": "HIGH",
        "consumer_json": {"items": ["auth_service_db.login lock_minutes"]},
    },
    {
        "config_key": "SEC_PASSWORD_MIN_LEN",
        "domain_code": "SECURITY",
        "config_name": "密码最小长度",
        "value_type": "INT",
        "default_json": {"value": 8},
        "platform_floor_json": {"min": 6, "max": 32},
        "school_editable": True,
        "risk_level": "HIGH",
        "consumer_json": {"items": ["auth_service_db.change_password"]},
    },
)


def _floor_seconds(value: datetime | None) -> datetime | None:
    """把时间截断到秒。

    MySQL ``DATETIME`` 精度为秒，写入时对微秒**四舍五入**：``18:31:13.900`` 会被存成
    ``18:31:14``。于是刚写入的覆盖，其 ``effective_at`` 反而比当前时间晚，读取时被判为
    "尚未生效"——管理员保存后要等一秒才生效，且是否踩中取决于当时的微秒数。
    统一截断到秒即可消除这个竞态；秒级精度对配置生效时间完全够用。
    """
    return value.replace(microsecond=0) if value else value


def _now() -> datetime:
    return _floor_seconds(datetime.utcnow())


def _tenant_id(value: int | None = None) -> int:
    tenant_id = int(value or current_tenant_id() or 0)
    if not tenant_id:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return tenant_id


def _actor_id() -> int | None:
    user = get_current_user_ctx() or {}
    raw = user.get("userId") or user.get("id")
    try:
        return int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _session():
    return get_sessionmaker()()


def _coerce(value: Any, value_type: str) -> Any:
    if value is None:
        return None
    if value_type == "INT":
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", f"该配置必须是整数：{value}") from exc
    if value_type == "BOOL":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if value_type == "JSON":
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except ValueError as exc:
            raise AppException("VALIDATION_ERROR", "该配置必须是合法 JSON") from exc
    return str(value)


def ensure_definitions() -> dict:
    """幂等写入初始配置定义。已存在的定义不覆盖学校已调整过的元数据。"""
    created = 0
    with _session() as db:
        for seed in SEED_DEFINITIONS:
            exists = db.scalars(
                select(ConfigDefinition).where(ConfigDefinition.config_key == seed["config_key"])
            ).first()
            if exists:
                continue
            db.add(ConfigDefinition(**seed, owner_code="SYSTEM", status="ACTIVE"))
            created += 1
        db.commit()
    return {"created": created, "total": len(SEED_DEFINITIONS)}


def _load_definition(db, config_key: str) -> ConfigDefinition:
    definition = db.scalars(
        select(ConfigDefinition).where(
            ConfigDefinition.config_key == config_key, ConfigDefinition.is_deleted.is_(False)
        )
    ).first()
    if not definition:
        raise not_found(f"未登记的配置项：{config_key}")
    return definition


def _legacy_value(db, tenant_id: int, config_key: str) -> Any:
    """既有 t_sys_config 的值。它今天就在生效，解析必须带上它。"""
    from app.models import SysConfig

    row = db.scalars(
        select(SysConfig).where(
            SysConfig.tenant_id == tenant_id,
            SysConfig.config_key == config_key,
            SysConfig.is_deleted.is_(False),
        )
    ).first()
    return row.value_text if row else None


def _active_overrides(
    db, tenant_id: int, config_key: str, *, at: datetime, org_unit_id: str | None, term_id: str | None
) -> list[ConfigOverride]:
    rows = db.scalars(
        select(ConfigOverride).where(
            ConfigOverride.tenant_id == tenant_id,
            ConfigOverride.config_key == config_key,
            ConfigOverride.status == OVERRIDE_STATUS_ACTIVE,
            ConfigOverride.effective_at <= at,
            ConfigOverride.is_deleted.is_(False),
        )
    ).all()
    picked: list[ConfigOverride] = []
    for row in rows:
        if row.expires_at is not None and row.expires_at <= at:
            continue  # 已过期：读取时校验，不依赖定时任务
        if row.scope_type == SCOPE_TENANT:
            picked.append(row)
        elif row.scope_type == SCOPE_ORG_UNIT and org_unit_id and str(row.scope_id) == str(org_unit_id):
            picked.append(row)
        elif row.scope_type == SCOPE_TERM and term_id and str(row.scope_id) == str(term_id):
            picked.append(row)
    # 同层多条时后生效的赢
    picked.sort(key=lambda r: (_SCOPE_PRIORITY.get(r.scope_type, 0), r.effective_at))
    return picked


def resolve(
    config_key: str,
    *,
    org_unit_id: str | None = None,
    term_id: str | None = None,
    at: datetime | None = None,
    tenant_id: int | None = None,
) -> dict:
    """解析一个配置的最终值，并返回完整来源链。"""
    tid = _tenant_id(tenant_id)
    moment = at or _now()
    with _session() as db:
        definition = _load_definition(db, config_key)
        vtype = definition.value_type
        chain: list[dict] = []

        floor = definition.platform_floor_json or {}
        if floor:
            chain.append({"layer": SOURCE_PLATFORM_FLOOR, "constraint": floor, "value": None})

        value = None
        source = None
        default = (definition.default_json or {}).get("value")
        if default is not None:
            value = _coerce(default, vtype)
            source = SOURCE_PACKAGE_DEFAULT
            chain.append({"layer": SOURCE_PACKAGE_DEFAULT, "value": value})

        legacy = _legacy_value(db, tid, config_key)
        if legacy is not None:
            value = _coerce(legacy, vtype)
            source = SOURCE_TENANT_LEGACY
            chain.append({"layer": SOURCE_TENANT_LEGACY, "value": value})

        for row in _active_overrides(
            db, tid, config_key, at=moment, org_unit_id=org_unit_id, term_id=term_id
        ):
            value = _coerce((row.value_json or {}).get("value"), vtype)
            source = row.scope_type
            chain.append(
                {
                    "layer": row.scope_type,
                    "scopeId": row.scope_id or None,
                    "value": value,
                    "effectiveAt": row.effective_at.isoformat(),
                    "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
                }
            )

        consumers = (definition.consumer_json or {}).get("items") or []
        return {
            "configKey": config_key,
            "configName": definition.config_name,
            "domain": definition.domain_code,
            "valueType": vtype,
            "value": value,
            "sourceLayer": source,
            "chain": chain,
            "platformFloor": floor or None,
            "schoolEditable": bool(definition.school_editable),
            "riskLevel": definition.risk_level,
            "consumers": consumers,
            # 没有消费者的配置改了也不会有任何行为变化，页面必须如实说明
            "takesEffectImmediately": bool(consumers),
            "resolvedAt": moment.isoformat(),
        }


def resolve_all(*, domain: str | None = None, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        stmt = select(ConfigDefinition).where(ConfigDefinition.is_deleted.is_(False))
        if domain:
            stmt = stmt.where(ConfigDefinition.domain_code == domain)
        keys = [d.config_key for d in db.scalars(stmt.order_by(ConfigDefinition.config_key)).all()]
    return {"items": [resolve(k, tenant_id=tid) for k in keys]}


def _assert_within_floor(definition: ConfigDefinition, value: Any) -> None:
    floor = definition.platform_floor_json or {}
    if not floor:
        return
    if definition.value_type == "INT":
        number = int(value)
        low, high = floor.get("min"), floor.get("max")
        if low is not None and number < int(low):
            raise AppException(
                "CONFIG_BELOW_PLATFORM_FLOOR",
                f"该配置不得低于平台底线 {low}",
                http_status=422,
                details={"platformFloor": floor, "requested": number},
            )
        if high is not None and number > int(high):
            raise AppException(
                "CONFIG_ABOVE_PLATFORM_CEILING",
                f"该配置不得高于平台上限 {high}",
                http_status=422,
                details={"platformFloor": floor, "requested": number},
            )
    enum = floor.get("enum")
    if enum and value not in enum:
        raise AppException(
            "CONFIG_NOT_IN_PLATFORM_ENUM", "该配置取值不在平台允许范围内", http_status=422,
            details={"allowed": enum},
        )


def set_override(
    config_key: str,
    *,
    value: Any,
    scope_type: str = SCOPE_TENANT,
    scope_id: str = "",
    effective_at: datetime | None = None,
    expires_at: datetime | None = None,
    reason: str = "",
    expected_version: int | None = None,
    tenant_id: int | None = None,
) -> dict:
    """新增或更新一层覆盖。越过平台底线一律拒绝，不静默夹逼。"""
    tid = _tenant_id(tenant_id)
    stype = str(scope_type or SCOPE_TENANT).upper()
    if stype not in OVERRIDE_SCOPES:
        raise AppException("VALIDATION_ERROR", f"未知配置层级：{stype}", details={"allowed": list(OVERRIDE_SCOPES)})
    if stype in (SCOPE_ORG_UNIT, SCOPE_TERM) and not str(scope_id or "").strip():
        raise AppException("VALIDATION_ERROR", "该层级必须指定作用对象")
    if not str(reason or "").strip():
        raise AppException("VALIDATION_ERROR", "配置变更必须填写原因")

    # 外部传入的时间同样截断：否则带微秒的 effective_at 存库后会被四舍五入，
    # 后续用原值去匹配同一行会找不到，变成新插一行而不是更新（乐观锁因此失效）。
    start = _floor_seconds(effective_at) or _now()
    expires_at = _floor_seconds(expires_at)
    if expires_at and expires_at <= start:
        raise AppException("VALIDATION_ERROR", "失效时间必须晚于生效时间")

    with _session() as db:
        definition = _load_definition(db, config_key)
        if not definition.school_editable:
            raise AppException("CONFIG_NOT_SCHOOL_EDITABLE", "该配置不允许学校修改", http_status=403)
        typed = _coerce(value, definition.value_type)
        _assert_within_floor(definition, typed)

        before = resolve(config_key, tenant_id=tid)

        existing = db.scalars(
            select(ConfigOverride).where(
                ConfigOverride.tenant_id == tid,
                ConfigOverride.config_key == config_key,
                ConfigOverride.scope_type == stype,
                ConfigOverride.scope_id == str(scope_id or ""),
                ConfigOverride.effective_at == start,
                ConfigOverride.is_deleted.is_(False),
            )
        ).first()
        if existing:
            if expected_version is not None and int(existing.version or 0) != int(expected_version):
                raise AppException("VERSION_CONFLICT", "该配置已被其他人修改，请刷新后重试", http_status=409)
            existing.value_json = {"value": typed}
            existing.expires_at = expires_at
            existing.status = OVERRIDE_STATUS_ACTIVE
            existing.reason = reason
            existing.updated_by = _actor_id()
            existing.version = int(existing.version or 0) + 1
            row = existing
        else:
            row = ConfigOverride(
                tenant_id=tid,
                config_key=config_key,
                scope_type=stype,
                scope_id=str(scope_id or ""),
                value_json={"value": typed},
                effective_at=start,
                expires_at=expires_at,
                status=OVERRIDE_STATUS_ACTIVE,
                reason=reason,
                created_by=_actor_id(),
                updated_by=_actor_id(),
            )
            db.add(row)

        trace_id = uuid.uuid4().hex
        db.add(
            ConfigActivation(
                tenant_id=tid,
                config_key=config_key,
                scope_type=stype,
                scope_id=str(scope_id or ""),
                before_json={"value": before.get("value"), "sourceLayer": before.get("sourceLayer")},
                after_json={"value": typed, "scopeType": stype, "effectiveAt": start.isoformat()},
                actor_user_id=_actor_id(),
                reason=reason,
                trace_id=trace_id,
                created_by=_actor_id(),
            )
        )
        db.commit()
        db.refresh(row)

    _audit(config_key, stype, reason, trace_id)
    return {
        "overrideId": str(row.id),
        "configKey": config_key,
        "scopeType": stype,
        "scopeId": row.scope_id or None,
        "value": typed,
        "effectiveAt": row.effective_at.isoformat(),
        "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
        "version": int(row.version or 0),
        "traceId": trace_id,
        "effective": resolve(config_key, tenant_id=tid),
    }


def revoke_override(override_id: int, *, reason: str, expected_version: int, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        row = db.scalars(
            select(ConfigOverride).where(
                ConfigOverride.tenant_id == tid,
                ConfigOverride.id == int(override_id),
                ConfigOverride.is_deleted.is_(False),
            )
        ).first()
        if not row:
            raise not_found("配置覆盖不存在")
        if int(row.version or 0) != int(expected_version):
            raise AppException("VERSION_CONFLICT", "该配置已被其他人修改，请刷新后重试", http_status=409)
        row.status = OVERRIDE_STATUS_REVOKED
        row.reason = reason or row.reason
        row.updated_by = _actor_id()
        row.version = int(row.version or 0) + 1
        config_key = row.config_key
        db.commit()
    return {"configKey": config_key, "effective": resolve(config_key, tenant_id=tid)}


def history(config_key: str, *, limit: int = 50, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        rows = db.scalars(
            select(ConfigActivation)
            .where(ConfigActivation.tenant_id == tid, ConfigActivation.config_key == config_key)
            .order_by(ConfigActivation.id.desc())
            .limit(limit)
        ).all()
        return {
            "items": [
                {
                    "scopeType": r.scope_type,
                    "scopeId": r.scope_id or None,
                    "before": r.before_json or {},
                    "after": r.after_json or {},
                    "actorUserId": str(r.actor_user_id) if r.actor_user_id else None,
                    "reason": r.reason,
                    "traceId": r.trace_id,
                    "occurredAt": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        }


def _audit(config_key: str, scope_type: str, reason: str, trace_id: str) -> None:
    try:
        from app.services import audit_log

        audit_log.record(
            "CONFIG_OVERRIDE_SET",
            f"config:{config_key}",
            detail={"scopeType": scope_type, "reason": reason, "traceId": trace_id},
        )
    except Exception:  # noqa: BLE001 - 审计失败不影响主流程
        pass
