"""SYS-09 安全变更：草稿、审核、排期、激活、回滚。

核心保证
────────
1. **草稿/审核/排期期间不写目标表**。不是靠代码自觉——变更只存在 ``t_security_change_item``
   的 ``after_json`` 里，目标表根本没被碰过。
2. **激活是单事务**。应用改动、写 before 快照、分配 revision、记录流水在同一个事务里；
   任何一步失败整体回滚，不存在"改了一半"。
3. **并发激活由数据库兜底**。``uk_security_revision`` 保证同一租户同一版本号只有一行，
   两个人同时点激活，必然只有一个成功，不依赖应用层先查后写。
4. **回滚用 before 快照还原**，并产生新的 revision（而不是把版本号退回去）——
   安全历史必须只进不退，否则无法解释"当时到底是什么状态"。

一人阶段的自复核
────────────────
学校往往只有一个管理员，硬要求"发起人 ≠ 复核人"会让流程无法推进。这里的折中是：
同一个人可以自复核，但必须逐字输入确认文本、必须填写复核意见，且全程写审计。
这挡不住蓄意绕过，但能挡住误点——后者才是实际最常发生的事故。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.security_change import (CHANGE_ACTIVATED, CHANGE_APPROVED,
                                        CHANGE_DRAFT, CHANGE_PENDING_REVIEW,
                                        CHANGE_REJECTED, CHANGE_ROLLED_BACK,
                                        CHANGE_SCHEDULED, CHANGE_STATUSES,
                                        RISK_CRITICAL, RISK_HIGH,
                                        TARGET_CUSTOM_ROLE,
                                        TARGET_SCOPE_POLICY, TARGET_TYPES,
                                        SecurityActivation, SecurityChangeItem,
                                        SecurityChangeSet)

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    CHANGE_DRAFT: frozenset({CHANGE_PENDING_REVIEW}),
    CHANGE_PENDING_REVIEW: frozenset({CHANGE_APPROVED, CHANGE_REJECTED, CHANGE_DRAFT}),
    CHANGE_APPROVED: frozenset({CHANGE_SCHEDULED, CHANGE_ACTIVATED, CHANGE_DRAFT}),
    CHANGE_SCHEDULED: frozenset({CHANGE_ACTIVATED, CHANGE_APPROVED}),
    CHANGE_ACTIVATED: frozenset({CHANGE_ROLLED_BACK}),
    CHANGE_REJECTED: frozenset({CHANGE_DRAFT}),
    CHANGE_ROLLED_BACK: frozenset(),
}

# 一人自复核必须逐字输入的确认文本
SELF_REVIEW_TEXT = "我已确认本次安全变更的影响并愿意承担责任"


def _floor_seconds(value: datetime | None) -> datetime | None:
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


# ── 安全版本号 ──────────────────────────────────────────────────────────────
def current_revision(*, tenant_id: int | None = None) -> int:
    """当前生效的安全版本号。客户端可用它判断本地权限快照是否过期。"""
    tid = _tenant_id(tenant_id)
    with _session() as db:
        value = db.scalar(
            select(func.max(SecurityActivation.revision)).where(SecurityActivation.tenant_id == tid)
        )
        return int(value or 0)


def _next_revision(db, tenant_id: int) -> int:
    value = db.scalar(
        select(func.max(SecurityActivation.revision)).where(SecurityActivation.tenant_id == tenant_id)
    )
    return int(value or 0) + 1


# ── 变更集 ──────────────────────────────────────────────────────────────────
def _row(change: SecurityChangeSet, items: list[SecurityChangeItem] | None = None) -> dict:
    payload = {
        "changeSetId": str(change.id),
        "changeCode": change.change_code,
        "title": change.title,
        "status": change.status,
        "riskLevel": change.risk_level,
        "reason": change.reason,
        "impact": change.impact_json or {},
        "scheduledAt": change.scheduled_at.isoformat() if change.scheduled_at else None,
        "submittedAt": change.submitted_at.isoformat() if change.submitted_at else None,
        "reviewedAt": change.reviewed_at.isoformat() if change.reviewed_at else None,
        "activatedAt": change.activated_at.isoformat() if change.activated_at else None,
        "rolledBackAt": change.rolled_back_at.isoformat() if change.rolled_back_at else None,
        "createdByUser": str(change.created_by_user) if change.created_by_user else None,
        "reviewedByUser": str(change.reviewed_by_user) if change.reviewed_by_user else None,
        "activatedByUser": str(change.activated_by_user) if change.activated_by_user else None,
        "reviewNote": change.review_note,
        "activatedRevision": change.activated_revision,
        # 以"是否走过自复核确认"为准，而不是比对两个 user_id：
        # 取不到操作人身份时两边都是 None，比对会算成"他人复核"，与事实相反。
        "selfReviewed": bool(change.self_review_ack),
        "version": int(change.version or 0),
        "allowedTransitions": sorted(ALLOWED_TRANSITIONS.get(change.status, frozenset())),
    }
    if items is not None:
        payload["items"] = [
            {
                "itemId": str(i.id),
                "targetType": i.target_type,
                "targetId": i.target_id,
                "before": i.before_json or {},
                "after": i.after_json or {},
                "appliedAt": i.applied_at.isoformat() if i.applied_at else None,
            }
            for i in items
        ]
    return payload


def create_change_set(
    *, title: str, reason: str, risk_level: str = "NORMAL", tenant_id: int | None = None
) -> dict:
    tid = _tenant_id(tenant_id)
    if not str(title or "").strip():
        raise AppException("VALIDATION_ERROR", "变更标题不能为空")
    if len(str(reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "变更原因不少于 5 个字")
    with _session() as db:
        change = SecurityChangeSet(
            tenant_id=tid,
            change_code=f"SEC-{uuid.uuid4().hex[:10].upper()}",
            title=title.strip(),
            reason=reason.strip(),
            risk_level=str(risk_level or "NORMAL").upper(),
            status=CHANGE_DRAFT,
            created_by_user=_actor_id(),
            created_by=_actor_id(),
            updated_by=_actor_id(),
        )
        db.add(change)
        db.commit()
        db.refresh(change)
        return _row(change, [])


def add_item(
    change_set_id: int,
    *,
    target_type: str,
    target_id: str,
    after: dict,
    tenant_id: int | None = None,
) -> dict:
    """向草稿追加一条改动。只记录"要改成什么"，不碰目标表。"""
    tid = _tenant_id(tenant_id)
    ttype = str(target_type or "").upper()
    if ttype not in TARGET_TYPES:
        raise AppException("VALIDATION_ERROR", f"不支持的变更目标：{ttype}", details={"allowed": list(TARGET_TYPES)})
    if not isinstance(after, dict) or not after:
        raise AppException("VALIDATION_ERROR", "变更内容不能为空")

    with _session() as db:
        change = _load(db, tid, change_set_id)
        if change.status != CHANGE_DRAFT:
            raise AppException("SECURITY_CHANGE_LOCKED", "只有草稿状态可以调整变更项", http_status=409)
        _validate_target(db, tid, ttype, str(target_id), after)
        item = SecurityChangeItem(
            tenant_id=tid,
            change_set_id=int(change.id),
            target_type=ttype,
            target_id=str(target_id),
            after_json=after,
            created_by=_actor_id(),
            updated_by=_actor_id(),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return {
            "itemId": str(item.id),
            "targetType": item.target_type,
            "targetId": item.target_id,
            "after": item.after_json,
        }


def _validate_target(db, tenant_id: int, target_type: str, target_id: str, after: dict) -> None:
    """提交前就把目标存在性和越界问题拦掉，别等到激活时才炸。"""
    if target_type == TARGET_CUSTOM_ROLE:
        from app.models.permission_governance import CustomRoleSource

        row = db.scalars(
            select(CustomRoleSource).where(
                CustomRoleSource.tenant_id == tenant_id,
                CustomRoleSource.role_code == target_id,
                CustomRoleSource.is_deleted.is_(False),
            )
        ).first()
        if not row:
            raise not_found(f"自定义角色不存在：{target_id}")
        codes = after.get("permissionCodes")
        if not isinstance(codes, list):
            raise AppException("VALIDATION_ERROR", "自定义角色变更必须提供 permissionCodes 列表")
        # 复用 SYS-06 的模板上限校验，避免安全变更成为绕过上限的后门
        from app.services import permission_bundle_service as pbs

        template = pbs.get_template(row.source_template_code, tenant_id=tenant_id)
        over = sorted(set(codes) - set(template["permissionCeiling"]))
        if over:
            raise AppException(
                "PERMISSION_EXCEEDS_TEMPLATE",
                "变更后的权限超出交付模板上限",
                http_status=403,
                details={"exceeded": over[:20], "exceededCount": len(over)},
            )
    elif target_type == TARGET_SCOPE_POLICY:
        from app.models.scope_policy import ScopePolicyTarget

        try:
            numeric = int(target_id)
        except (TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "范围策略 id 必须是数字") from exc
        row = db.scalars(
            select(ScopePolicyTarget).where(
                ScopePolicyTarget.tenant_id == tenant_id,
                ScopePolicyTarget.id == numeric,
                ScopePolicyTarget.is_deleted.is_(False),
            )
        ).first()
        if not row:
            raise not_found(f"范围策略不存在：{target_id}")
        if "status" not in after and "effect" not in after:
            raise AppException("VALIDATION_ERROR", "范围策略变更必须提供 status 或 effect")


def _load(db, tenant_id: int, change_set_id: int, *, lock: bool = False) -> SecurityChangeSet:
    stmt = select(SecurityChangeSet).where(
        SecurityChangeSet.tenant_id == tenant_id,
        SecurityChangeSet.id == int(change_set_id),
        SecurityChangeSet.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    change = db.scalars(stmt).first()
    if not change:
        raise not_found("安全变更不存在")
    return change


def _load_items(db, tenant_id: int, change_set_id: int) -> list[SecurityChangeItem]:
    return list(
        db.scalars(
            select(SecurityChangeItem)
            .where(
                SecurityChangeItem.tenant_id == tenant_id,
                SecurityChangeItem.change_set_id == int(change_set_id),
                SecurityChangeItem.is_deleted.is_(False),
            )
            .order_by(SecurityChangeItem.id)
        ).all()
    )


def get_change_set(change_set_id: int, *, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        change = _load(db, tid, change_set_id)
        return _row(change, _load_items(db, tid, change_set_id))


def list_change_sets(*, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        rows = db.scalars(
            select(SecurityChangeSet)
            .where(SecurityChangeSet.tenant_id == tid, SecurityChangeSet.is_deleted.is_(False))
            .order_by(SecurityChangeSet.id.desc())
        ).all()
        return {"items": [_row(r) for r in rows], "currentRevision": current_revision(tenant_id=tid)}


# ── 状态流转 ────────────────────────────────────────────────────────────────
def transition(
    change_set_id: int,
    target_status: str,
    *,
    reason: str = "",
    expected_version: int,
    scheduled_at: datetime | None = None,
    self_review_ack: str | None = None,
    tenant_id: int | None = None,
) -> dict:
    tid = _tenant_id(tenant_id)
    target = str(target_status or "").upper()
    if target not in CHANGE_STATUSES:
        raise AppException("VALIDATION_ERROR", f"未知的变更状态：{target}")

    with _session() as db:
        change = _load(db, tid, change_set_id, lock=True)
        if int(change.version or 0) != int(expected_version):
            raise AppException(
                "VERSION_CONFLICT", "该安全变更已被其他人修改，请刷新后重试", http_status=409,
                details={"currentVersion": int(change.version or 0)},
            )
        current = change.status
        if target == current:
            return _row(change, _load_items(db, tid, change_set_id))
        if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
            raise AppException(
                "STATE_TRANSITION_DENIED", f"不允许从 {current} 变更为 {target}", http_status=409,
                details={"allowed": sorted(ALLOWED_TRANSITIONS.get(current, frozenset()))},
            )

        items = _load_items(db, tid, change_set_id)
        now = _now()

        if target == CHANGE_PENDING_REVIEW:
            if not items:
                raise AppException("VALIDATION_ERROR", "空变更集没有可审核的内容")
            change.impact_json = {"items": _impact(db, tid, items)}
            change.submitted_at = now

        if target == CHANGE_APPROVED:
            actor = _actor_id()
            # fail-closed：只有能**确证**复核人与发起人是不同的两个人时，才免除自复核门槛。
            # 取不到操作人身份（无用户上下文、后台任务等）时一律按自复核处理——
            # 早期写成 `actor is not None and ...`，结果拿不到身份就整段跳过，
            # 等于给了一条"没有身份就免检"的绕行路径，方向反了。
            is_self_review = (
                actor is None
                or change.created_by_user is None
                or change.created_by_user == actor
            )
            if is_self_review:
                # 一人自复核：必须逐字输入确认文本 + 写复核意见
                if str(self_review_ack or "").strip() != SELF_REVIEW_TEXT:
                    raise AppException(
                        "SELF_REVIEW_ACK_REQUIRED",
                        "发起人自行复核时必须逐字输入确认文本",
                        http_status=403,
                        details={"requiredText": SELF_REVIEW_TEXT},
                    )
                if len(str(reason or "").strip()) < 5:
                    raise AppException("VALIDATION_ERROR", "自复核必须填写不少于 5 个字的复核意见")
                change.self_review_ack = SELF_REVIEW_TEXT
            change.reviewed_by_user = actor
            change.reviewed_at = now
            change.review_note = reason or change.review_note

        if target == CHANGE_REJECTED:
            if len(str(reason or "").strip()) < 5:
                raise AppException("VALIDATION_ERROR", "驳回必须填写不少于 5 个字的理由")
            change.reviewed_by_user = _actor_id()
            change.reviewed_at = now
            change.review_note = reason

        if target == CHANGE_SCHEDULED:
            scheduled_at = _floor_seconds(scheduled_at)
            if not scheduled_at:
                raise AppException("VALIDATION_ERROR", "排期必须提供计划时间")
            if scheduled_at <= now:
                raise AppException("VALIDATION_ERROR", "计划时间必须晚于当前时间")
            change.scheduled_at = scheduled_at

        trace_id = uuid.uuid4().hex
        if target == CHANGE_ACTIVATED:
            _apply_items(db, tid, items)
            revision = _next_revision(db, tid)
            db.add(
                SecurityActivation(
                    tenant_id=tid,
                    revision=revision,
                    change_set_id=int(change.id),
                    action="ACTIVATE",
                    snapshot_json={"items": [_item_snapshot(i) for i in items]},
                    actor_user_id=_actor_id(),
                    trace_id=trace_id,
                    created_by=_actor_id(),
                    updated_by=_actor_id(),
                )
            )
            change.activated_at = now
            change.activated_by_user = _actor_id()
            change.activated_revision = revision

        if target == CHANGE_ROLLED_BACK:
            _revert_items(db, tid, items)
            revision = _next_revision(db, tid)
            db.add(
                SecurityActivation(
                    tenant_id=tid,
                    revision=revision,
                    change_set_id=int(change.id),
                    action="ROLLBACK",
                    snapshot_json={"items": [_item_snapshot(i) for i in items]},
                    actor_user_id=_actor_id(),
                    trace_id=trace_id,
                    created_by=_actor_id(),
                    updated_by=_actor_id(),
                )
            )
            change.rolled_back_at = now
            # 回滚同样前进版本号：安全历史只进不退，否则无法解释当时的真实状态
            change.activated_revision = revision

        change.status = target
        change.updated_by = _actor_id()
        change.version = int(change.version or 0) + 1

        try:
            db.commit()
        except IntegrityError as exc:
            # 并发激活时 uk_security_revision 会挡住后到的那个
            db.rollback()
            raise AppException(
                "SECURITY_ACTIVATION_CONFLICT",
                "另一个安全变更正在激活，请刷新后重试",
                http_status=409,
            ) from exc

        _audit(target, change.id, reason, trace_id)
        db.refresh(change)
        return _row(change, _load_items(db, tid, change_set_id))


def _item_snapshot(item: SecurityChangeItem) -> dict:
    return {
        "targetType": item.target_type,
        "targetId": item.target_id,
        "before": item.before_json or {},
        "after": item.after_json or {},
    }


def _impact(db, tenant_id: int, items: list[SecurityChangeItem]) -> list[dict]:
    """提交审核时算影响面，让复核人看到这次到底动了谁。"""
    out: list[dict] = []
    for item in items:
        if item.target_type == TARGET_CUSTOM_ROLE:
            from app.models.permission_governance import CustomRoleSource

            row = db.scalars(
                select(CustomRoleSource).where(
                    CustomRoleSource.tenant_id == tenant_id,
                    CustomRoleSource.role_code == item.target_id,
                )
            ).first()
            before = set((row.permission_codes_json or {}).get("items") or []) if row else set()
            after = set((item.after_json or {}).get("permissionCodes") or [])
            out.append(
                {
                    "targetType": item.target_type,
                    "targetId": item.target_id,
                    "added": sorted(after - before),
                    "removed": sorted(before - after),
                }
            )
        else:
            out.append(
                {
                    "targetType": item.target_type,
                    "targetId": item.target_id,
                    "change": item.after_json or {},
                }
            )
    return out


def _apply_items(db, tenant_id: int, items: list[SecurityChangeItem]) -> None:
    """把改动真正写入目标表，同时抓 before 快照。全程在调用方的事务里。"""
    from app.models.permission_governance import CustomRoleSource
    from app.models.scope_policy import ScopePolicyTarget

    now = _now()
    for item in items:
        after = item.after_json or {}
        if item.target_type == TARGET_CUSTOM_ROLE:
            row = db.scalars(
                select(CustomRoleSource).where(
                    CustomRoleSource.tenant_id == tenant_id,
                    CustomRoleSource.role_code == item.target_id,
                    CustomRoleSource.is_deleted.is_(False),
                )
            ).first()
            if not row:
                raise not_found(f"自定义角色不存在：{item.target_id}")
            item.before_json = {
                "permissionCodes": (row.permission_codes_json or {}).get("items") or [],
                "status": row.status,
            }
            row.permission_codes_json = {"items": sorted(set(after.get("permissionCodes") or []))}
            row.status = "ACTIVE"
            row.version = int(row.version or 0) + 1
        elif item.target_type == TARGET_SCOPE_POLICY:
            row = db.scalars(
                select(ScopePolicyTarget).where(
                    ScopePolicyTarget.tenant_id == tenant_id,
                    ScopePolicyTarget.id == int(item.target_id),
                    ScopePolicyTarget.is_deleted.is_(False),
                )
            ).first()
            if not row:
                raise not_found(f"范围策略不存在：{item.target_id}")
            item.before_json = {"status": row.status, "effect": row.effect}
            if after.get("status"):
                row.status = str(after["status"]).upper()
            if after.get("effect"):
                row.effect = str(after["effect"]).upper()
            row.version = int(row.version or 0) + 1
        item.applied_at = now


def _revert_items(db, tenant_id: int, items: list[SecurityChangeItem]) -> None:
    from app.models.permission_governance import CustomRoleSource
    from app.models.scope_policy import ScopePolicyTarget

    for item in reversed(items):
        before = item.before_json or {}
        if not before:
            continue
        if item.target_type == TARGET_CUSTOM_ROLE:
            row = db.scalars(
                select(CustomRoleSource).where(
                    CustomRoleSource.tenant_id == tenant_id,
                    CustomRoleSource.role_code == item.target_id,
                )
            ).first()
            if row:
                row.permission_codes_json = {"items": before.get("permissionCodes") or []}
                row.status = before.get("status") or row.status
                row.version = int(row.version or 0) + 1
        elif item.target_type == TARGET_SCOPE_POLICY:
            row = db.scalars(
                select(ScopePolicyTarget).where(
                    ScopePolicyTarget.tenant_id == tenant_id,
                    ScopePolicyTarget.id == int(item.target_id),
                )
            ).first()
            if row:
                row.status = before.get("status") or row.status
                row.effect = before.get("effect") or row.effect
                row.version = int(row.version or 0) + 1
        item.applied_at = None


def activate_due_change_sets(*, now: datetime | None = None) -> dict:
    """激活到期的排期变更。幂等：已激活的不会再次应用。"""
    moment = now or _now()
    activated: list[dict] = []
    skipped: list[dict] = []
    with _session() as db:
        due = db.scalars(
            select(SecurityChangeSet).where(
                SecurityChangeSet.status == CHANGE_SCHEDULED,
                SecurityChangeSet.scheduled_at.is_not(None),
                SecurityChangeSet.scheduled_at <= moment,
                SecurityChangeSet.is_deleted.is_(False),
            )
        ).all()
        targets = [(c.tenant_id, c.id, int(c.version or 0)) for c in due]

    for tenant_id, change_id, ver in targets:
        try:
            transition(
                change_id, CHANGE_ACTIVATED, reason="排期到点自动激活",
                expected_version=ver, tenant_id=tenant_id,
            )
            activated.append({"tenantId": str(tenant_id), "changeSetId": str(change_id)})
        except AppException as exc:
            skipped.append({"tenantId": str(tenant_id), "changeSetId": str(change_id), "reason": exc.code})
    return {"activated": activated, "skipped": skipped, "checkedAt": moment.isoformat()}


def activation_history(*, limit: int = 50, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        rows = db.scalars(
            select(SecurityActivation)
            .where(SecurityActivation.tenant_id == tid)
            .order_by(SecurityActivation.revision.desc())
            .limit(limit)
        ).all()
        return {
            "items": [
                {
                    "revision": int(r.revision),
                    "action": r.action,
                    "changeSetId": str(r.change_set_id),
                    "actorUserId": str(r.actor_user_id) if r.actor_user_id else None,
                    "traceId": r.trace_id,
                    "occurredAt": r.created_at.isoformat() if r.created_at else None,
                    "itemCount": len((r.snapshot_json or {}).get("items") or []),
                }
                for r in rows
            ],
            "currentRevision": current_revision(tenant_id=tid),
        }


def _audit(action: str, change_id: int, reason: str, trace_id: str) -> None:
    try:
        from app.services import audit_log

        audit_log.record(
            "SECURITY_CHANGE_TRANSITION",
            f"securityChange:{change_id}",
            detail={"toStatus": action, "reason": reason, "traceId": trace_id},
        )
    except Exception:  # noqa: BLE001 - 审计失败不影响主流程
        pass
