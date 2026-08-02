"""SYS-08 组织安全树：显式 DENY、继承与判定解释。

唯一判定顺序
────────────
    DENY > 敏感专项 > 业务关系 > 直接 ALLOW > 继承 ALLOW > 默认拒绝

DENY 最先命中且**不可被任何 ALLOW 覆盖**。把"某个节点谁都不许看"表达成"少给一个
ALLOW"是不可靠的：只要有人给这个角色加了个更大的范围，限制就被击穿了。

与既有实现的边界
────────────────
``t_data_scope_rule`` 和 ``data_scope_service`` 里的 provider 继续负责"业务关系"这一层
（辅导员带哪些班、导师带哪些学生），本服务不复制那套逻辑，只在它之上加显式 DENY、
敏感专项和未来生效，并把整条判定链解释出来。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.scope_policy import (EFFECT_ALLOW, EFFECT_DENY, EFFECTS,
                                     TARGET_CLASS, TARGET_COLLEGE,
                                     TARGET_DOMAIN, TARGET_MAJOR, TARGET_TYPES,
                                     ScopePolicyDecisionLog, ScopePolicyTarget)

# 判定原因码，前端直接展示，不要在页面里另造一套文案逻辑
REASON_EXPLICIT_DENY = "EXPLICIT_DENY"
REASON_INHERITED_DENY = "INHERITED_DENY"
REASON_SENSITIVE_DENY = "SENSITIVE_DOMAIN_RESTRICTED"
REASON_BUSINESS_RELATION = "BUSINESS_RELATION_ALLOW"
REASON_DIRECT_ALLOW = "DIRECT_ALLOW"
REASON_INHERITED_ALLOW = "INHERITED_ALLOW"
REASON_DEFAULT_DENY = "DEFAULT_DENY"

# 组织层级：子 → 父
_PARENT_OF = {TARGET_CLASS: TARGET_MAJOR, TARGET_MAJOR: TARGET_COLLEGE}


def _floor_seconds(value: datetime | None) -> datetime | None:
    """截断到秒；理由同 SYS-11/SYS-04：MySQL DATETIME 会把微秒四舍五入进位，
    导致刚写入的策略被判为"尚未生效"。"""
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


def _ancestors(db, tenant_id: int, target_type: str, target_id: str) -> list[tuple[str, str]]:
    """返回目标的祖先链 [(type, id), ...]，从直接父级向上。跨租户节点一律当作不存在。"""
    from app.models import Major, SchoolClass

    chain: list[tuple[str, str]] = []
    current_type, current_id = target_type, str(target_id)

    while current_type in _PARENT_OF:
        parent_type = _PARENT_OF[current_type]
        parent_id = None
        try:
            numeric = int(current_id)
        except (TypeError, ValueError):
            break
        if current_type == TARGET_CLASS:
            row = db.scalars(
                select(SchoolClass).where(
                    SchoolClass.tenant_id == tenant_id,
                    SchoolClass.id == numeric,
                    SchoolClass.is_deleted.is_(False),
                )
            ).first()
            parent_id = str(row.major_id) if row and row.major_id else None
        elif current_type == TARGET_MAJOR:
            row = db.scalars(
                select(Major).where(
                    Major.tenant_id == tenant_id, Major.id == numeric, Major.is_deleted.is_(False)
                )
            ).first()
            parent_id = str(row.college_id) if row and row.college_id else None
        if not parent_id:
            break
        chain.append((parent_type, parent_id))
        current_type, current_id = parent_type, parent_id
    return chain


def _live_policies(db, tenant_id: int, role_code: str, at: datetime) -> list[ScopePolicyTarget]:
    rows = db.scalars(
        select(ScopePolicyTarget).where(
            ScopePolicyTarget.tenant_id == tenant_id,
            ScopePolicyTarget.role_code == role_code,
            ScopePolicyTarget.status == "ACTIVE",
            ScopePolicyTarget.effective_at <= at,
            ScopePolicyTarget.is_deleted.is_(False),
        )
    ).all()
    # 过期在读取时就要失效，不依赖定时任务
    return [r for r in rows if r.expires_at is None or r.expires_at > at]


def decide(
    role_code: str,
    *,
    target_type: str,
    target_id: str,
    at: datetime | None = None,
    business_relation_allows: bool | None = None,
    tenant_id: int | None = None,
) -> dict:
    """按唯一顺序判定并返回完整解释。

    ``business_relation_allows`` 由调用方（既有 data_scope_service provider）传入，
    本服务不复制业务关系判定逻辑。传 None 表示该层不参与。
    """
    tid = _tenant_id(tenant_id)
    ttype = str(target_type or "").upper()
    if ttype not in TARGET_TYPES:
        raise AppException("VALIDATION_ERROR", f"未知的范围目标类型：{ttype}", details={"allowed": list(TARGET_TYPES)})
    moment = at or _now()
    tid_str = str(target_id)

    with _session() as db:
        policies = _live_policies(db, tid, role_code, moment)
        ancestors = _ancestors(db, tid, ttype, tid_str) if ttype != TARGET_DOMAIN else []
        chain: list[dict] = []

        def _record(step: str, hit: bool, detail: dict | None = None) -> None:
            chain.append({"step": step, "hit": hit, **(detail or {})})

        # 1) 显式 DENY（目标自身）
        for p in policies:
            if p.effect == EFFECT_DENY and p.target_type == ttype and str(p.target_id) == tid_str:
                _record("DENY", True, {"targetId": tid_str, "reason": p.reason})
                return _finish(db, tid, role_code, ttype, tid_str, EFFECT_DENY, REASON_EXPLICIT_DENY, chain)
        _record("DENY", False)

        # 1b) 继承 DENY（祖先节点上的 DENY，且允许向下继承）
        for anc_type, anc_id in ancestors:
            for p in policies:
                if (
                    p.effect == EFFECT_DENY
                    and p.include_children
                    and p.target_type == anc_type
                    and str(p.target_id) == anc_id
                ):
                    _record("INHERITED_DENY", True, {"from": f"{anc_type}:{anc_id}", "reason": p.reason})
                    return _finish(
                        db, tid, role_code, ttype, tid_str, EFFECT_DENY, REASON_INHERITED_DENY, chain
                    )
        _record("INHERITED_DENY", False)

        # 2) 敏感专项：命中即拒绝，优先级仅次于显式 DENY
        for p in policies:
            if p.sensitive_domain and p.effect == EFFECT_DENY:
                if p.target_type == TARGET_DOMAIN and str(p.target_id) == tid_str:
                    _record("SENSITIVE", True, {"domain": p.sensitive_domain})
                    return _finish(
                        db, tid, role_code, ttype, tid_str, EFFECT_DENY, REASON_SENSITIVE_DENY, chain
                    )
        _record("SENSITIVE", False)

        # 3) 业务关系（由既有 provider 判定，本服务不复制）
        if business_relation_allows is True:
            _record("BUSINESS_RELATION", True)
            return _finish(db, tid, role_code, ttype, tid_str, EFFECT_ALLOW, REASON_BUSINESS_RELATION, chain)
        _record("BUSINESS_RELATION", bool(business_relation_allows))

        # 4) 直接 ALLOW
        for p in policies:
            if p.effect == EFFECT_ALLOW and p.target_type == ttype and str(p.target_id) == tid_str:
                _record("DIRECT_ALLOW", True, {"targetId": tid_str})
                return _finish(db, tid, role_code, ttype, tid_str, EFFECT_ALLOW, REASON_DIRECT_ALLOW, chain)
        _record("DIRECT_ALLOW", False)

        # 5) 继承 ALLOW
        for anc_type, anc_id in ancestors:
            for p in policies:
                if (
                    p.effect == EFFECT_ALLOW
                    and p.include_children
                    and p.target_type == anc_type
                    and str(p.target_id) == anc_id
                ):
                    _record("INHERITED_ALLOW", True, {"from": f"{anc_type}:{anc_id}"})
                    return _finish(
                        db, tid, role_code, ttype, tid_str, EFFECT_ALLOW, REASON_INHERITED_ALLOW, chain
                    )
        _record("INHERITED_ALLOW", False)

        # 6) 默认拒绝
        _record("DEFAULT_DENY", True)
        return _finish(db, tid, role_code, ttype, tid_str, EFFECT_DENY, REASON_DEFAULT_DENY, chain)


def _finish(
    db, tenant_id: int, role_code: str, target_type: str, target_id: str,
    decision: str, reason_code: str, chain: list[dict],
) -> dict:
    trace_id = uuid.uuid4().hex
    db.add(
        ScopePolicyDecisionLog(
            tenant_id=tenant_id,
            role_code=role_code,
            target_type=target_type,
            target_id=target_id,
            decision=decision,
            reason_code=reason_code,
            detail_json={"chain": chain},
            trace_id=trace_id,
            created_by=_actor_id(),
            updated_by=_actor_id(),
        )
    )
    db.commit()
    return {
        "decision": decision,
        "reasonCode": reason_code,
        "roleCode": role_code,
        "targetType": target_type,
        "targetId": target_id,
        "chain": chain,
        "traceId": trace_id,
    }


def set_policy(
    role_code: str,
    *,
    effect: str,
    target_type: str,
    target_id: str,
    include_children: bool = True,
    sensitive_domain: str | None = None,
    effective_at: datetime | None = None,
    expires_at: datetime | None = None,
    reason: str = "",
    expected_version: int | None = None,
    tenant_id: int | None = None,
) -> dict:
    tid = _tenant_id(tenant_id)
    eff = str(effect or "").upper()
    ttype = str(target_type or "").upper()
    if eff not in EFFECTS:
        raise AppException("VALIDATION_ERROR", f"未知的效果：{eff}", details={"allowed": list(EFFECTS)})
    if ttype not in TARGET_TYPES:
        raise AppException("VALIDATION_ERROR", f"未知的目标类型：{ttype}")
    if not str(reason or "").strip():
        raise AppException("VALIDATION_ERROR", "范围策略变更必须填写原因")

    start = _floor_seconds(effective_at) or _now()
    expires_at = _floor_seconds(expires_at)
    if expires_at and expires_at <= start:
        raise AppException("VALIDATION_ERROR", "失效时间必须晚于生效时间")

    with _session() as db:
        if ttype != TARGET_DOMAIN:
            _assert_target_exists(db, tid, ttype, target_id)
        existing = db.scalars(
            select(ScopePolicyTarget).where(
                ScopePolicyTarget.tenant_id == tid,
                ScopePolicyTarget.role_code == role_code,
                ScopePolicyTarget.effect == eff,
                ScopePolicyTarget.target_type == ttype,
                ScopePolicyTarget.target_id == str(target_id),
                ScopePolicyTarget.effective_at == start,
                ScopePolicyTarget.is_deleted.is_(False),
            )
        ).first()
        if existing:
            if expected_version is not None and int(existing.version or 0) != int(expected_version):
                raise AppException("VERSION_CONFLICT", "该范围策略已被其他人修改，请刷新后重试", http_status=409)
            existing.include_children = bool(include_children)
            existing.sensitive_domain = sensitive_domain
            existing.expires_at = expires_at
            existing.status = "ACTIVE"
            existing.reason = reason
            existing.updated_by = _actor_id()
            existing.version = int(existing.version or 0) + 1
            row = existing
        else:
            row = ScopePolicyTarget(
                tenant_id=tid,
                role_code=role_code,
                effect=eff,
                target_type=ttype,
                target_id=str(target_id),
                include_children=bool(include_children),
                sensitive_domain=sensitive_domain,
                effective_at=start,
                expires_at=expires_at,
                status="ACTIVE",
                reason=reason,
                created_by=_actor_id(),
                updated_by=_actor_id(),
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        return _policy_row(row)


def _assert_target_exists(db, tenant_id: int, target_type: str, target_id: str) -> None:
    """跨租户组织节点一律 404，不泄露其他学校的节点是否存在。"""
    from app.models import College, Major, SchoolClass

    model = {TARGET_COLLEGE: College, TARGET_MAJOR: Major, TARGET_CLASS: SchoolClass}[target_type]
    try:
        numeric = int(target_id)
    except (TypeError, ValueError) as exc:
        raise AppException("VALIDATION_ERROR", "组织节点 id 必须是数字") from exc
    row = db.scalars(
        select(model).where(model.tenant_id == tenant_id, model.id == numeric, model.is_deleted.is_(False))
    ).first()
    if not row:
        raise not_found(f"组织节点不存在（{target_type}:{target_id}）")


def _policy_row(row: ScopePolicyTarget) -> dict:
    return {
        "policyId": str(row.id),
        "roleCode": row.role_code,
        "effect": row.effect,
        "targetType": row.target_type,
        "targetId": row.target_id,
        "includeChildren": bool(row.include_children),
        "sensitiveDomain": row.sensitive_domain,
        "effectiveAt": row.effective_at.isoformat() if row.effective_at else None,
        "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
        "status": row.status,
        "reason": row.reason,
        "version": int(row.version or 0),
    }


def list_policies(*, role_code: str | None = None, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        stmt = select(ScopePolicyTarget).where(
            ScopePolicyTarget.tenant_id == tid, ScopePolicyTarget.is_deleted.is_(False)
        )
        if role_code:
            stmt = stmt.where(ScopePolicyTarget.role_code == role_code)
        rows = db.scalars(
            stmt.order_by(ScopePolicyTarget.effect.desc(), ScopePolicyTarget.id.desc())
        ).all()
        return {"items": [_policy_row(r) for r in rows]}


def revoke_policy(policy_id: int, *, reason: str, expected_version: int, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        row = db.scalars(
            select(ScopePolicyTarget).where(
                ScopePolicyTarget.tenant_id == tid,
                ScopePolicyTarget.id == int(policy_id),
                ScopePolicyTarget.is_deleted.is_(False),
            )
        ).first()
        if not row:
            raise not_found("范围策略不存在")
        if int(row.version or 0) != int(expected_version):
            raise AppException("VERSION_CONFLICT", "该范围策略已被其他人修改，请刷新后重试", http_status=409)
        row.status = "REVOKED"
        row.reason = reason or row.reason
        row.updated_by = _actor_id()
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        return _policy_row(row)


def references(role_code: str, *, tenant_id: int | None = None) -> dict:
    """某角色的范围引用统计。

    只统计结构化的 ``t_scope_policy_target``，**不搜索 Role.remark**——remark 是自由文本，
    拿它当权限事实源会在改文案时静默改变鉴权。
    """
    tid = _tenant_id(tenant_id)
    with _session() as db:
        rows = db.scalars(
            select(ScopePolicyTarget).where(
                ScopePolicyTarget.tenant_id == tid,
                ScopePolicyTarget.role_code == role_code,
                ScopePolicyTarget.status == "ACTIVE",
                ScopePolicyTarget.is_deleted.is_(False),
            )
        ).all()
        return {
            "roleCode": role_code,
            "denyCount": sum(1 for r in rows if r.effect == EFFECT_DENY),
            "allowCount": sum(1 for r in rows if r.effect == EFFECT_ALLOW),
            "sensitiveCount": sum(1 for r in rows if r.sensitive_domain),
            "source": "t_scope_policy_target",
        }
