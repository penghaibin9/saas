"""SYS-10 访问解释、权限复核、职责分离与紧急访问。

解释器的唯一正确写法
────────────────────
``has_permission`` 只返回 True/False。想解释"为什么被拒"，最容易想到的是照着它的逻辑
再写一遍并打印每一步——**绝不能这么做**。两套逻辑必然漂移，等它们不一致时，解释会
理直气壮地给出与实际相反的结论，比没有解释更危险。

这里的做法：
1. 只调用真实函数（``is_super_admin`` / ``get_effective_permission_patterns`` /
   ``has_permission`` / ``scope_policy_service.decide``），把中间量展开成可读链路；
2. **最终结论一律取 ``has_permission`` 的返回**，链路只负责说明；
3. 链路推导若与它不一致，标记 ``EXPLAINER_DRIFT`` 如实报出来——这说明解释器该修了，
   而不是让两个答案各说各话。

另一条红线：无权查看目标对象时不得泄露它是否存在。资源标识一律以 SHA-256 摘要入库，
解释结果也不回显原始 id，否则这个接口就成了对象枚举器。
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.context import current_tenant_id, get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.db.session import get_sessionmaker
from app.models.access_governance import (DECISION_ALLOW, DECISION_DENY,
                                          REVIEW_CLOSED, REVIEW_DECISIONS,
                                          REVIEW_DRAFT, REVIEW_EXCEPTION,
                                          REVIEW_KEEP, REVIEW_RUNNING,
                                          AccessDecisionTrace,
                                          AccessReviewCampaign,
                                          AccessReviewItem,
                                          EmergencyAccessSession, SodRule,
                                          SodViolation)

REASON_SUPER_ADMIN = "SUPER_ADMIN_BYPASS"
REASON_PERMISSION_GRANTED = "PERMISSION_GRANTED"
REASON_PERMISSION_MISSING = "PERMISSION_NOT_GRANTED"
REASON_ROLE_DENY = "ROLE_EXPLICIT_DENY"
REASON_SCOPE_DENY = "DATA_SCOPE_DENIED"
REASON_EXPLAINER_DRIFT = "EXPLAINER_DRIFT"

TRACE_RETENTION_DAYS = 180


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


def _hash_resource(value: str | None) -> str | None:
    """资源标识只存摘要：解释接口不能变成"这个对象存不存在"的探测器。"""
    if not value:
        return None
    return "sha256:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _role_of(user: dict) -> str:
    """直接复用鉴权核心的取法，不另写一套。

    这里原本按 ``user["currentRole"]["roleCode"]`` 取，而 ``permissions._role_of`` 实际读的是
    顶层 ``currentRoleCode`` / ``userType``——字段对不上，解释里显示的角色与真正参与判定的
    角色就是两回事。本模块开头刚警告过"两套逻辑必然漂移"，这就是活例子：只要重写就会错。
    """
    from app.core.permissions import _role_of as core_role_of

    return core_role_of(user or {})


# ── 访问解释 ────────────────────────────────────────────────────────────────
def explain(
    user: dict,
    *,
    action_code: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    scope_target_type: str | None = None,
    scope_target_id: str | None = None,
    persist: bool = True,
    tenant_id: int | None = None,
) -> dict:
    """解释某人对某动作的最终判定，并逐层给出 PASS/FAIL。"""
    tid = _tenant_id(tenant_id)
    from app.core.permissions import (get_effective_permission_patterns,
                                      has_permission, is_super_admin)

    chain: list[dict] = []
    role_code = _role_of(user)

    # 第 1 层：超管直通
    super_admin = bool(is_super_admin(user))
    chain.append({"step": "SUPER_ADMIN", "pass": super_admin})

    # 第 2 层：当前激活角色
    chain.append({"step": "ACTIVE_ROLE", "pass": bool(role_code), "roleCode": role_code or None})

    # 第 3 层：实际生效的权限模式（直接取自鉴权核心，不自行推导）
    try:
        patterns = sorted(get_effective_permission_patterns(user) or [])
    except Exception:  # noqa: BLE001 - 解释失败不该把调用方打挂
        patterns = []
    chain.append(
        {
            "step": "PERMISSION_PATTERNS",
            "pass": bool(patterns),
            "patternCount": len(patterns),
            # 只回显少量样本，避免把整份权限清单当输出泄露出去
            "samples": patterns[:8],
        }
    )

    # 第 4 层：角色级显式 DENY
    role_denied = False
    try:
        from app.core.permissions import ROLE_PERMISSION_DENY

        role_denied = action_code in (ROLE_PERMISSION_DENY.get(role_code, ()) or ())
    except Exception:  # noqa: BLE001
        role_denied = False
    chain.append({"step": "ROLE_DENY", "pass": not role_denied})

    # 第 5 层：权限判定——**这一步是权威结论**
    granted = bool(has_permission(user, action_code))
    chain.append({"step": "PERMISSION_CHECK", "pass": granted, "actionCode": action_code})

    # 第 6 层：数据范围（有目标节点时才判）
    scope_decision = None
    if scope_target_type and scope_target_id and role_code:
        from app.services import scope_policy_service as sps

        try:
            scope_decision = sps.decide(
                role_code, target_type=scope_target_type, target_id=scope_target_id, tenant_id=tid
            )
        except AppException:
            scope_decision = None
    if scope_decision is not None:
        chain.append(
            {
                "step": "DATA_SCOPE",
                "pass": scope_decision["decision"] == DECISION_ALLOW,
                "reasonCode": scope_decision["reasonCode"],
            }
        )

    # 第 7 层：紧急访问（只影响解释，不改变判定本身）
    emergency = _active_emergency(tid, _subject_id(user))
    if emergency:
        chain.append({"step": "EMERGENCY_ACCESS", "pass": True, "expiresAt": emergency["expiresAt"]})

    # 汇总：结论取 has_permission，链路只负责说明
    decision = DECISION_ALLOW if granted else DECISION_DENY
    if granted and scope_decision is not None and scope_decision["decision"] == DECISION_DENY:
        decision = DECISION_DENY
        reason_code = REASON_SCOPE_DENY
    elif super_admin:
        reason_code = REASON_SUPER_ADMIN
    elif granted:
        reason_code = REASON_PERMISSION_GRANTED
    elif role_denied:
        reason_code = REASON_ROLE_DENY
    else:
        reason_code = REASON_PERMISSION_MISSING

    # 自检：链路推导出的结果必须与权威判定一致，不一致说明解释器该修了
    derived_allow = super_admin or (granted and not role_denied)
    if derived_allow != granted and not super_admin:
        reason_code = REASON_EXPLAINER_DRIFT
        chain.append(
            {
                "step": "SELF_CHECK",
                "pass": False,
                "note": "解释链推导与 has_permission 不一致，以 has_permission 为准；解释器需要修正",
            }
        )
    else:
        chain.append({"step": "SELF_CHECK", "pass": True})

    trace_id = uuid.uuid4().hex
    payload = {
        "decision": decision,
        "reasonCode": reason_code,
        "actionCode": action_code,
        "activeRole": role_code or None,
        "resourceType": resource_type,
        # 不回显 resource_id 原值，只给摘要
        "resourceIdHash": _hash_resource(resource_id),
        "chain": chain,
        "traceId": trace_id,
        "resolvedAt": _now().isoformat(),
    }

    if persist:
        _persist_trace(tid, trace_id, user, action_code, resource_type, resource_id, decision, reason_code, chain)
    return payload


def _subject_id(user: dict) -> int | None:
    raw = (user or {}).get("userId") or (user or {}).get("id")
    try:
        return int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _persist_trace(
    tenant_id: int, trace_id: str, user: dict, action_code: str,
    resource_type: str | None, resource_id: str | None,
    decision: str, reason_code: str, chain: list[dict],
) -> None:
    from datetime import timedelta

    try:
        revision = 0
        try:
            from app.services import security_change_service as scs

            revision = scs.current_revision(tenant_id=tenant_id)
        except Exception:  # noqa: BLE001 - 版本号拿不到不该阻断留痕
            revision = 0
        with _session() as db:
            db.add(
                AccessDecisionTrace(
                    tenant_id=tenant_id,
                    trace_id=trace_id,
                    subject_user_id=_subject_id(user),
                    active_role_code=_role_of(user) or None,
                    action_code=action_code,
                    resource_type=resource_type,
                    resource_id_hash=_hash_resource(resource_id),
                    decision=decision,
                    reason_code=reason_code,
                    security_revision=revision,
                    decision_json={"chain": chain},
                    expires_at=_now() + timedelta(days=TRACE_RETENTION_DAYS),
                    created_by=_actor_id(),
                )
            )
            db.commit()
    except Exception:  # noqa: BLE001 - 留痕失败不能把业务请求打挂
        pass


def get_trace(trace_id: str, *, tenant_id: int | None = None) -> dict:
    """按 traceId 复现当时的判定链。跨租户一律 404。"""
    tid = _tenant_id(tenant_id)
    with _session() as db:
        row = db.scalars(
            select(AccessDecisionTrace).where(
                AccessDecisionTrace.tenant_id == tid, AccessDecisionTrace.trace_id == trace_id
            )
        ).first()
        if not row:
            raise not_found("决策记录不存在")
        return {
            "traceId": row.trace_id,
            "decision": row.decision,
            "reasonCode": row.reason_code,
            "actionCode": row.action_code,
            "activeRole": row.active_role_code,
            "resourceType": row.resource_type,
            "resourceIdHash": row.resource_id_hash,
            "securityRevision": int(row.security_revision or 0),
            "chain": (row.decision_json or {}).get("chain") or [],
            "occurredAt": row.created_at.isoformat() if row.created_at else None,
        }


def list_denials(*, limit: int = 50, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        rows = db.scalars(
            select(AccessDecisionTrace)
            .where(AccessDecisionTrace.tenant_id == tid, AccessDecisionTrace.decision == DECISION_DENY)
            .order_by(AccessDecisionTrace.id.desc())
            .limit(limit)
        ).all()
        return {
            "items": [
                {
                    "traceId": r.trace_id,
                    "actionCode": r.action_code,
                    "reasonCode": r.reason_code,
                    "activeRole": r.active_role_code,
                    "occurredAt": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        }


# ── 职责分离 ────────────────────────────────────────────────────────────────
def add_sod_rule(
    *, rule_code: str, role_a: str, role_b: str, reason: str,
    severity: str = "HIGH", tenant_id: int | None = None,
) -> dict:
    tid = _tenant_id(tenant_id)
    if not rule_code or not role_a or not role_b:
        raise AppException("VALIDATION_ERROR", "规则编码与两个角色都不能为空")
    if role_a == role_b:
        raise AppException("VALIDATION_ERROR", "职责分离规则的两个角色不能相同")
    if len(str(reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "必须说明为什么这两个角色不能兼任")

    with _session() as db:
        exists = db.scalars(
            select(SodRule).where(
                SodRule.tenant_id == tid, SodRule.rule_code == rule_code, SodRule.is_deleted.is_(False)
            )
        ).first()
        if exists:
            raise AppException("SOD_RULE_EXISTS", f"规则已存在：{rule_code}", http_status=409)
        row = SodRule(
            tenant_id=tid, rule_code=rule_code, role_a=role_a, role_b=role_b,
            severity=str(severity or "HIGH").upper(), reason=reason.strip(), status="ACTIVE",
            created_by=_actor_id(), updated_by=_actor_id(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "ruleCode": row.rule_code, "roleA": row.role_a, "roleB": row.role_b,
            "severity": row.severity, "reason": row.reason, "status": row.status,
        }


def check_sod(subject_user_id: int, role_codes: list[str], *, tenant_id: int | None = None) -> dict:
    """检查一组角色是否触犯职责分离。**调用方必须真的拦住**，检出不等于放行。"""
    tid = _tenant_id(tenant_id)
    held = {str(r) for r in (role_codes or [])}
    violations: list[dict] = []
    with _session() as db:
        rules = db.scalars(
            select(SodRule).where(
                SodRule.tenant_id == tid, SodRule.status == "ACTIVE", SodRule.is_deleted.is_(False)
            )
        ).all()
        for rule in rules:
            if rule.role_a in held and rule.role_b in held:
                violations.append(
                    {
                        "ruleCode": rule.rule_code,
                        "roles": [rule.role_a, rule.role_b],
                        "severity": rule.severity,
                        "reason": rule.reason,
                    }
                )
                existing = db.scalars(
                    select(SodViolation).where(
                        SodViolation.tenant_id == tid,
                        SodViolation.rule_code == rule.rule_code,
                        SodViolation.subject_user_id == int(subject_user_id),
                        SodViolation.is_deleted.is_(False),
                    )
                ).first()
                if not existing:
                    db.add(
                        SodViolation(
                            tenant_id=tid, rule_code=rule.rule_code, subject_user_id=int(subject_user_id),
                            detected_roles_json={"items": sorted(held)}, status="OPEN",
                            created_by=_actor_id(), updated_by=_actor_id(),
                        )
                    )
        db.commit()
    return {"conflict": bool(violations), "violations": violations}


def assert_sod(subject_user_id: int, role_codes: list[str], *, tenant_id: int | None = None) -> None:
    """后端强制入口：有冲突直接抛 403，不给调用方"检出了但还是放行"的机会。"""
    result = check_sod(subject_user_id, role_codes, tenant_id=tenant_id)
    if result["conflict"]:
        raise AppException(
            "SOD_CONFLICT",
            "该组合触犯职责分离规则",
            http_status=403,
            details={"violations": result["violations"]},
        )


def list_sod(*, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        rules = db.scalars(
            select(SodRule).where(SodRule.tenant_id == tid, SodRule.is_deleted.is_(False))
        ).all()
        violations = db.scalars(
            select(SodViolation).where(
                SodViolation.tenant_id == tid, SodViolation.is_deleted.is_(False)
            )
        ).all()
        return {
            "rules": [
                {"ruleCode": r.rule_code, "roleA": r.role_a, "roleB": r.role_b,
                 "severity": r.severity, "reason": r.reason, "status": r.status}
                for r in rules
            ],
            "violations": [
                {"ruleCode": v.rule_code, "subjectUserId": str(v.subject_user_id),
                 "roles": (v.detected_roles_json or {}).get("items") or [], "status": v.status}
                for v in violations
            ],
        }


# ── 紧急访问 ────────────────────────────────────────────────────────────────
def grant_emergency(
    *, subject_user_id: int, granted_role_code: str, ticket_ref: str, reason: str,
    minutes: int = 60, tenant_id: int | None = None,
) -> dict:
    """开通紧急访问。必须有工单号、必须有到期时间，最长 8 小时。"""
    from datetime import timedelta

    tid = _tenant_id(tenant_id)
    if not str(ticket_ref or "").strip():
        raise AppException("VALIDATION_ERROR", "紧急访问必须关联工单或事件号，不允许空口开通")
    if len(str(reason or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "必须填写不少于 5 个字的开通理由")
    minutes = int(minutes or 0)
    if minutes <= 0 or minutes > 480:
        raise AppException(
            "VALIDATION_ERROR", "紧急访问时长必须在 1 分钟到 8 小时之间——不存在无限期的紧急访问"
        )

    started = _now()
    with _session() as db:
        row = EmergencyAccessSession(
            tenant_id=tid,
            session_code=f"EMG-{uuid.uuid4().hex[:10].upper()}",
            subject_user_id=int(subject_user_id),
            granted_role_code=granted_role_code,
            ticket_ref=ticket_ref.strip(),
            reason=reason.strip(),
            started_at=started,
            expires_at=started + timedelta(minutes=minutes),
            status="ACTIVE",
            created_by=_actor_id(),
            updated_by=_actor_id(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        _audit("EMERGENCY_ACCESS_GRANTED", row.session_code, reason)
        return _emergency_row(row)


def _emergency_row(row: EmergencyAccessSession, *, at: datetime | None = None) -> dict:
    moment = at or _now()
    active = row.status == "ACTIVE" and row.expires_at > moment and row.revoked_at is None
    return {
        "sessionCode": row.session_code,
        "subjectUserId": str(row.subject_user_id),
        "grantedRole": row.granted_role_code,
        "ticketRef": row.ticket_ref,
        "reason": row.reason,
        "startedAt": row.started_at.isoformat() if row.started_at else None,
        "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
        "revokedAt": row.revoked_at.isoformat() if row.revoked_at else None,
        "status": row.status,
        "activeNow": active,
        "version": int(row.version or 0),
    }


def _active_emergency(tenant_id: int, subject_user_id: int | None) -> dict | None:
    """读取时校验到期：定时任务没跑到也必须立刻失效。"""
    if not subject_user_id:
        return None
    now = _now()
    with _session() as db:
        rows = db.scalars(
            select(EmergencyAccessSession).where(
                EmergencyAccessSession.tenant_id == tenant_id,
                EmergencyAccessSession.subject_user_id == int(subject_user_id),
                EmergencyAccessSession.status == "ACTIVE",
                EmergencyAccessSession.is_deleted.is_(False),
            )
        ).all()
    live = [r for r in rows if r.expires_at > now and r.revoked_at is None]
    return _emergency_row(live[-1]) if live else None


def active_emergency(subject_user_id: int, *, tenant_id: int | None = None) -> dict | None:
    return _active_emergency(_tenant_id(tenant_id), subject_user_id)


def revoke_emergency(session_code: str, *, reason: str, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        row = db.scalars(
            select(EmergencyAccessSession).where(
                EmergencyAccessSession.tenant_id == tid,
                EmergencyAccessSession.session_code == session_code,
                EmergencyAccessSession.is_deleted.is_(False),
            )
        ).first()
        if not row:
            raise not_found("紧急访问会话不存在")
        row.status = "REVOKED"
        row.revoked_at = _now()
        row.updated_by = _actor_id()
        row.version = int(row.version or 0) + 1
        db.commit()
        db.refresh(row)
        _audit("EMERGENCY_ACCESS_REVOKED", session_code, reason)
        return _emergency_row(row)


def expire_emergency_sessions(*, now: datetime | None = None) -> dict:
    """定时把过期会话刷成 EXPIRED。与读取时校验构成双保险。"""
    moment = _floor_seconds(now) or _now()
    with _session() as db:
        rows = db.scalars(
            select(EmergencyAccessSession).where(
                EmergencyAccessSession.status == "ACTIVE",
                EmergencyAccessSession.expires_at <= moment,
                EmergencyAccessSession.is_deleted.is_(False),
            )
        ).all()
        for row in rows:
            row.status = "EXPIRED"
            row.version = int(row.version or 0) + 1
        db.commit()
        return {"expired": len(rows), "checkedAt": moment.isoformat()}


def list_emergency(*, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        rows = db.scalars(
            select(EmergencyAccessSession)
            .where(EmergencyAccessSession.tenant_id == tid, EmergencyAccessSession.is_deleted.is_(False))
            .order_by(EmergencyAccessSession.id.desc())
        ).all()
        return {"items": [_emergency_row(r) for r in rows]}


# ── 权限复核 ────────────────────────────────────────────────────────────────
def create_campaign(
    *, title: str, role_codes: list[str] | None = None, due_at: datetime | None = None,
    tenant_id: int | None = None,
) -> dict:
    tid = _tenant_id(tenant_id)
    if not str(title or "").strip():
        raise AppException("VALIDATION_ERROR", "复核活动必须有标题")
    with _session() as db:
        row = AccessReviewCampaign(
            tenant_id=tid,
            campaign_code=f"REV-{uuid.uuid4().hex[:10].upper()}",
            title=title.strip(),
            scope_json={"roleCodes": list(role_codes or [])},
            status=REVIEW_DRAFT,
            due_at=_floor_seconds(due_at),
            created_by=_actor_id(),
            updated_by=_actor_id(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _campaign_row(row, [])


def _campaign_row(row: AccessReviewCampaign, items: list[AccessReviewItem] | None = None) -> dict:
    payload = {
        "campaignId": str(row.id),
        "campaignCode": row.campaign_code,
        "title": row.title,
        "status": row.status,
        "roleCodes": (row.scope_json or {}).get("roleCodes") or [],
        "dueAt": row.due_at.isoformat() if row.due_at else None,
        "closedAt": row.closed_at.isoformat() if row.closed_at else None,
        "version": int(row.version or 0),
    }
    if items is not None:
        payload["items"] = [
            {
                "itemId": str(i.id),
                "subjectUserId": str(i.subject_user_id),
                "roleCode": i.role_code,
                "decision": i.decision,
                "note": i.note,
                "decidedAt": i.decided_at.isoformat() if i.decided_at else None,
                "followUpChangeSetId": str(i.follow_up_change_set_id) if i.follow_up_change_set_id else None,
            }
            for i in items
        ]
        payload["pendingCount"] = sum(1 for i in items if not i.decision)
    return payload


def add_review_item(
    campaign_id: int, *, subject_user_id: int, role_code: str, tenant_id: int | None = None
) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        campaign = _load_campaign(db, tid, campaign_id)
        if campaign.status == REVIEW_CLOSED:
            raise AppException("REVIEW_CLOSED", "复核已关闭，不能再追加条目", http_status=409)
        exists = db.scalars(
            select(AccessReviewItem).where(
                AccessReviewItem.tenant_id == tid,
                AccessReviewItem.campaign_id == int(campaign_id),
                AccessReviewItem.subject_user_id == int(subject_user_id),
                AccessReviewItem.role_code == role_code,
                AccessReviewItem.is_deleted.is_(False),
            )
        ).first()
        if exists:
            return {"itemId": str(exists.id), "duplicated": True}
        item = AccessReviewItem(
            tenant_id=tid, campaign_id=int(campaign_id), subject_user_id=int(subject_user_id),
            role_code=role_code, created_by=_actor_id(), updated_by=_actor_id(),
        )
        db.add(item)
        if campaign.status == REVIEW_DRAFT:
            campaign.status = REVIEW_RUNNING
        db.commit()
        db.refresh(item)
        return {"itemId": str(item.id), "duplicated": False}


def _load_campaign(db, tenant_id: int, campaign_id: int) -> AccessReviewCampaign:
    row = db.scalars(
        select(AccessReviewCampaign).where(
            AccessReviewCampaign.tenant_id == tenant_id,
            AccessReviewCampaign.id == int(campaign_id),
            AccessReviewCampaign.is_deleted.is_(False),
        )
    ).first()
    if not row:
        raise not_found("复核活动不存在")
    return row


def decide_review_item(
    item_id: int, *, decision: str, note: str = "", follow_up_change_set_id: int | None = None,
    tenant_id: int | None = None,
) -> dict:
    """给出复核结论。回收/调整必须关联一次安全变更——否则等于只在表里写了个结论。"""
    tid = _tenant_id(tenant_id)
    verdict = str(decision or "").upper()
    if verdict not in REVIEW_DECISIONS:
        raise AppException(
            "VALIDATION_ERROR", f"未知的复核结论：{verdict}", details={"allowed": list(REVIEW_DECISIONS)}
        )
    if verdict in ("ADJUST", "REVOKE") and not follow_up_change_set_id:
        raise AppException(
            "REVIEW_FOLLOW_UP_REQUIRED",
            "调整或回收权限必须关联一次安全变更，不能只在复核表里写个结论",
            http_status=422,
        )
    if verdict == REVIEW_EXCEPTION and len(str(note or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "例外必须说明理由")

    with _session() as db:
        item = db.scalars(
            select(AccessReviewItem).where(
                AccessReviewItem.tenant_id == tid,
                AccessReviewItem.id == int(item_id),
                AccessReviewItem.is_deleted.is_(False),
            )
        ).first()
        if not item:
            raise not_found("复核条目不存在")
        item.decision = verdict
        item.note = note
        item.decided_by = _actor_id()
        item.decided_at = _now()
        item.follow_up_change_set_id = follow_up_change_set_id
        item.version = int(item.version or 0) + 1
        db.commit()
        return {"itemId": str(item.id), "decision": item.decision}


def close_campaign(campaign_id: int, *, tenant_id: int | None = None) -> dict:
    """关闭复核。还有未处理条目时不允许关闭——复核不能"到期自动算过"。"""
    tid = _tenant_id(tenant_id)
    with _session() as db:
        campaign = _load_campaign(db, tid, campaign_id)
        items = db.scalars(
            select(AccessReviewItem).where(
                AccessReviewItem.tenant_id == tid,
                AccessReviewItem.campaign_id == int(campaign_id),
                AccessReviewItem.is_deleted.is_(False),
            )
        ).all()
        pending = [i for i in items if not i.decision]
        if pending:
            raise AppException(
                "REVIEW_ITEMS_PENDING",
                f"还有 {len(pending)} 条未给出结论，不能关闭复核",
                http_status=409,
                details={"pendingCount": len(pending)},
            )
        campaign.status = REVIEW_CLOSED
        campaign.closed_at = _now()
        campaign.version = int(campaign.version or 0) + 1
        db.commit()
        db.refresh(campaign)
        return _campaign_row(campaign, items)


def get_campaign(campaign_id: int, *, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        campaign = _load_campaign(db, tid, campaign_id)
        items = db.scalars(
            select(AccessReviewItem)
            .where(
                AccessReviewItem.tenant_id == tid,
                AccessReviewItem.campaign_id == int(campaign_id),
                AccessReviewItem.is_deleted.is_(False),
            )
            .order_by(AccessReviewItem.id)
        ).all()
        return _campaign_row(campaign, items)


def list_campaigns(*, tenant_id: int | None = None) -> dict:
    tid = _tenant_id(tenant_id)
    with _session() as db:
        rows = db.scalars(
            select(AccessReviewCampaign)
            .where(AccessReviewCampaign.tenant_id == tid, AccessReviewCampaign.is_deleted.is_(False))
            .order_by(AccessReviewCampaign.id.desc())
        ).all()
        return {"items": [_campaign_row(r) for r in rows]}


def _audit(action: str, resource: str, reason: str) -> None:
    try:
        from app.services import audit_log

        audit_log.record(action, f"accessGovernance:{resource}", detail={"reason": reason})
    except Exception:  # noqa: BLE001 - 审计失败不影响主流程
        pass
