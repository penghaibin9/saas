"""SYS-07：角色成员的授予、有效期、到期回收与转交。

到期怎么才算"真的失效"
──────────────────────
真实鉴权的必经之路是 ``auth_service_db._role_contexts``，它只认
``t_user_role.status == "ACTIVE"`` 的行。所以到期回收**不是**在某个新表里写个
EXPIRED 就完事，必须把原表那一行翻成 EXPIRED 并清掉主体缓存——这样下一次请求就
失效，用户不需要重新登录。

双保险（本卡明确要求）：
1. ``sweep_expired()`` 给定时任务用，批量回收；
2. ``effective_assignments()`` 在**每次读取时**顺手回收本人已过期的行，
   即使定时任务没跑、或者刚好卡在两次执行之间，也不会放过一条。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.role_assignment import (SOURCE_MANUAL, SOURCE_TRANSFER,
                                        SOURCE_UNKNOWN, VALIDITY_ACTIVE,
                                        VALIDITY_EXPIRED, VALIDITY_REVOKED)

# 首屏结论用的分类
BUCKET_EXPIRING_SOON = "EXPIRING_SOON"        # 即将到期
BUCKET_EXPIRED_NOT_RECLAIMED = "EXPIRED_NOT_RECLAIMED"  # 过期未回收（异常，双保险漏了才会出现）
BUCKET_UNREVIEWED = "UNREVIEWED_ACROSS_TERM"  # 跨学期未复核
BUCKET_UNKNOWN_SOURCE = "UNKNOWN_SOURCE"      # 来源不明（历史长期授权）
BUCKET_HIGH_PRIV_MULTI = "HIGH_PRIV_MULTI"    # 多人持有高权角色

HIGH_PRIVILEGE_ROLES = {"SCHOOL_ADMIN", "SYS_ADMIN", "SECURITY_AUDITOR"}
EXPIRING_SOON_DAYS = 14


def _tid(tenant_id: int | None = None) -> int:
    return int(tenant_id if tenant_id is not None else (current_tenant_id() or 0))


def _now() -> datetime:
    # MySQL DATETIME 没有微秒位，会四舍五入进位。统一截断到秒，
    # 否则"刚设为 1 秒后到期"可能被读成已经到期。
    return datetime.now().replace(microsecond=0)


def _actor_id(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or "").replace("db-", "")
    return int(raw) if raw.isdigit() else None


def _parse_dt(value: Any, field: str) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).replace(microsecond=0)
        except ValueError:
            continue
    raise AppException("VALIDATION_ERROR", f"{field} 格式应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS")


def _invalidate(user_ids: set[int], tenant_id: int) -> None:
    """把主体缓存清掉——不清的话到期要等缓存 TTL 才生效。"""
    try:
        from app.services.auth_service_db import invalidate_subject_cache

        for uid in user_ids:
            invalidate_subject_cache(f"db-{uid}", tenant_id)
    except Exception:  # noqa: BLE001
        pass


def _expire_due(db, tenant_id: int, *, now: datetime | None = None,
                user_id: int | None = None) -> set[int]:
    """把已到期的授权真正回收掉：validity → EXPIRED，且 t_user_role → EXPIRED。"""
    from app.models import UserRole
    from app.models.role_assignment import RoleAssignmentValidity

    moment = now or _now()
    stmt = select(RoleAssignmentValidity).where(
        RoleAssignmentValidity.tenant_id == tenant_id,
        RoleAssignmentValidity.status == VALIDITY_ACTIVE,
        RoleAssignmentValidity.is_deleted.is_(False),
        RoleAssignmentValidity.expires_at.is_not(None),
        RoleAssignmentValidity.expires_at <= moment,
    )
    if user_id is not None:
        stmt = stmt.where(RoleAssignmentValidity.user_id == int(user_id))
    touched: set[int] = set()
    for row in db.scalars(stmt).all():
        row.status = VALIDITY_EXPIRED
        row.version = int(row.version or 0) + 1
        link = db.get(UserRole, int(row.user_role_id))
        if link is not None and str(link.status or "").upper() == "ACTIVE":
            link.status = VALIDITY_EXPIRED
            link.version = int(link.version or 0) + 1
        touched.add(int(row.user_id))
    return touched



def _audit_expiry_in_session(db, tenant_id: int, touched: set[int], *, source: str) -> None:
    if not touched:
        return
    from app.services import audit_log

    audit_log.record_critical_in_session(
        db,
        "ROLE_ASSIGNMENT_EXPIRE",
        f"tenant:{tenant_id}:role-assignments",
        detail={
            "count": len(touched),
            "userIds": sorted(touched)[:50],
            "source": source,
            "moduleCode": "systemAdmin",
        },
        tenant_id=tenant_id,
    )


def sweep_expired(*, tenant_id: int | None = None) -> dict:
    """定时任务入口：回收本校全部到期授权；业务事实与审计证据同事务提交。"""
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        touched = _expire_due(db, tid)
        if touched:
            from app.services import audit_log
            audit_log.record_critical_in_session(
                db,
                "ROLE_ASSIGNMENT_EXPIRE",
                f"tenant:{tid}:role-assignment-expiry",
                detail={
                    "count": len(touched),
                    "userIds": sorted(touched)[:50],
                    "source": "SCHEDULER_OR_MANUAL",
                    "moduleCode": "systemAdmin",
                },
                tenant_id=tid,
                operator_name_override="SYSTEM_SCHEDULER",
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    _invalidate(touched, tid)
    return {"expiredUsers": sorted(str(u) for u in touched), "count": len(touched)}


def _role_row(db, tenant_id: int, role_code: str):
    from app.models import Role

    role = db.scalars(select(Role).where(
        Role.tenant_id == tenant_id, Role.role_code == role_code,
        Role.is_deleted.is_(False))).first()
    if role is None:
        raise AppException("DATA_NOT_FOUND", f"角色不存在：{role_code}")
    return role


def _assert_role_delegation_allowed(db, *, actor: dict | None, role, tenant_id: int) -> None:
    """角色治理写链的最终授权边界：只允许固化 actor 的基础权限。"""
    from app.core.permissions import ROLE_PERMISSIONS, assert_delegable_permission_codes
    from app.models import Permission, RolePermission

    role_code = str(role.role_code or "").strip().upper()
    if role_code.startswith("PLATFORM_"):
        raise AppException("NO_PERMISSION", "学校角色治理不能授予平台角色")
    if str(role.role_type or "").upper() == "SYSTEM":
        permission_codes = set(ROLE_PERMISSIONS.get(role_code, set()))
    else:
        permission_codes = set(db.scalars(select(Permission.permission_code).join(
            RolePermission, RolePermission.permission_id == Permission.id
        ).where(
            RolePermission.tenant_id == tenant_id,
            RolePermission.role_id == role.id,
            RolePermission.status == "ACTIVE",
            RolePermission.is_deleted.is_(False),
        )).all())
    assert_delegable_permission_codes(actor, permission_codes)


def _grant_assignment_in_db(
    db,
    *,
    user_id: int,
    role_code: str,
    reason: str,
    start: datetime,
    end: datetime | None,
    source_type: str,
    source_id: str | None,
    tenant_id: int,
    actor: dict | None,
):
    """内部原子 mutation：不 commit、不关 session、不做 cache、不独立审计。"""
    from app.models import User, UserRole
    from app.models.role_assignment import RoleAssignmentValidity

    account = db.scalars(select(User).where(
        User.id == int(user_id), User.tenant_id == tenant_id,
        User.is_deleted.is_(False)).with_for_update()).first()
    if account is None:
        raise AppException("DATA_NOT_FOUND", "账号不存在或不在当前数据范围内")
    role = _role_row(db, tenant_id, str(role_code or "").strip().upper())
    _assert_role_delegation_allowed(db, actor=actor, role=role, tenant_id=tenant_id)

    link = db.scalars(select(UserRole).where(
        UserRole.tenant_id == tenant_id, UserRole.user_id == account.id,
        UserRole.role_id == role.id, UserRole.is_deleted.is_(False)).with_for_update()).first()
    if link is None:
        link = UserRole(tenant_id=tenant_id, user_id=account.id, role_id=role.id, status="ACTIVE")
        db.add(link)
        db.flush()
    else:
        link.status = "ACTIVE"
        link.is_deleted = False
        link.version = int(link.version or 0) + 1

    validity = db.scalars(select(RoleAssignmentValidity).where(
        RoleAssignmentValidity.tenant_id == tenant_id,
        RoleAssignmentValidity.user_role_id == link.id,
        RoleAssignmentValidity.is_deleted.is_(False)).with_for_update()).first()
    if validity is None:
        validity = RoleAssignmentValidity(
            tenant_id=tenant_id, user_role_id=int(link.id), user_id=int(account.id),
            role_code=role.role_code, effective_at=start, expires_at=end,
            source_type=source_type, source_id=source_id, reason=reason,
            granted_by=_actor_id(actor), status=VALIDITY_ACTIVE,
            created_by=_actor_id(actor), updated_by=_actor_id(actor))
        db.add(validity)
    else:
        validity.effective_at = start
        validity.expires_at = end
        validity.source_type = source_type
        validity.source_id = source_id
        validity.reason = reason
        validity.status = VALIDITY_ACTIVE
        validity.revoked_at = None
        validity.revoked_by = None
        validity.revoke_reason = None
        validity.transferred_to_user_id = None
        validity.updated_by = _actor_id(actor)
        validity.version = int(validity.version or 0) + 1
    db.flush()
    return validity, account, role


def grant_assignment(user_id: int, role_code: str, *, reason: str,
                     effective_at: Any = None, expires_at: Any = None,
                     source_type: str = SOURCE_MANUAL, source_id: str | None = None,
                     tenant_id: int | None = None, user: dict | None = None) -> dict:
    """授予角色并登记有效期；mutation + critical audit 一次提交。"""
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "授予原因不少于 5 个字")
    tid = _tid(tenant_id)
    start = _parse_dt(effective_at, "effectiveAt") or _now()
    end = _parse_dt(expires_at, "expiresAt")
    if end is not None and end <= start:
        raise AppException("VALIDATION_ERROR", "到期时间必须晚于生效时间")

    db = get_sessionmaker()()
    try:
        validity, account, role = _grant_assignment_in_db(
            db, user_id=int(user_id), role_code=role_code, reason=reason,
            start=start, end=end, source_type=source_type, source_id=source_id,
            tenant_id=tid, actor=user,
        )
        assignment_id = int(validity.id)
        from app.services import audit_log
        audit_log.record_critical_in_session(
            db,
            "ROLE_ASSIGNMENT_GRANT",
            f"role-assignment:{assignment_id}",
            detail={
                "userId": int(account.id),
                "roleCode": role.role_code,
                "reason": reason,
                "effectiveAt": str(start),
                "expiresAt": str(end or ""),
                "sourceType": source_type,
                "moduleCode": "systemAdmin",
            },
            tenant_id=tid,
            resource_id=str(assignment_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    _invalidate({int(user_id)}, tid)
    return get_assignment(assignment_id, tenant_id=tid)


def _require_expected_version(expected_version: int | None, *, operation: str) -> int:
    if expected_version is None:
        raise AppException(
            "VALIDATION_ERROR",
            f"{operation}必须提供 expectedVersion",
            http_status=422,
        )
    try:
        return int(expected_version)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{operation}的 expectedVersion 必须为整数", http_status=422) from None


def _revoke_assignment_in_db(
    db,
    *,
    row,
    reason: str,
    actor: dict | None,
    transferred_to_user_id: int | None = None,
):
    """内部回收 mutation：调用者负责锁、版本、审计与 commit。"""
    from app.models import UserRole

    if row.status != VALIDITY_ACTIVE:
        raise AppException("VALIDATION_ERROR", "该授权当前不是生效状态，不能重复回收")
    row.status = VALIDITY_REVOKED
    row.revoked_at = _now()
    row.revoked_by = _actor_id(actor)
    row.revoke_reason = reason
    row.transferred_to_user_id = transferred_to_user_id
    row.version = int(row.version or 0) + 1
    link = db.get(UserRole, int(row.user_role_id))
    if link is not None:
        link.status = VALIDITY_REVOKED
        link.version = int(link.version or 0) + 1
    db.flush()
    return int(row.user_id)


def revoke_assignment(assignment_id: int, *, reason: str, expected_version: int | None = None,
                      tenant_id: int | None = None, user: dict | None = None,
                      transferred_to_user_id: int | None = None) -> dict:
    """显式回收：行锁 + expectedVersion + critical audit + 单事务。"""
    from app.models.role_assignment import RoleAssignmentValidity

    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "回收原因不少于 5 个字")
    expected = _require_expected_version(expected_version, operation="角色回收")
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(RoleAssignmentValidity).where(
            RoleAssignmentValidity.id == int(assignment_id),
            RoleAssignmentValidity.tenant_id == tid,
            RoleAssignmentValidity.is_deleted.is_(False)).with_for_update()).first()
        if row is None:
            raise AppException("DATA_NOT_FOUND", "角色授权记录不存在")
        if expected != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "授权记录已被他人更新，请刷新后重试")
        user_id = _revoke_assignment_in_db(
            db, row=row, reason=reason, actor=user,
            transferred_to_user_id=transferred_to_user_id,
        )
        from app.services import audit_log
        audit_log.record_critical_in_session(
            db,
            "ROLE_ASSIGNMENT_REVOKE",
            f"role-assignment:{assignment_id}",
            detail={
                "userId": user_id,
                "roleCode": row.role_code,
                "reason": reason,
                "expectedVersion": expected,
                "moduleCode": "systemAdmin",
            },
            tenant_id=tid,
            resource_id=str(assignment_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    _invalidate({user_id}, tid)
    return get_assignment(int(assignment_id), tenant_id=tid)


def transfer_assignment(assignment_id: int, *, to_user_id: int, reason: str,
                        expires_at: Any = None, expected_version: int | None = None,
                        tenant_id: int | None = None, user: dict | None = None) -> dict:
    """工作转交：旧回收 + 新授予 + transfer audit 必须同一事务。"""
    from app.models import User
    from app.models.role_assignment import RoleAssignmentValidity

    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "转交原因不少于 5 个字")
    expected = _require_expected_version(expected_version, operation="角色转交")
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(RoleAssignmentValidity).where(
            RoleAssignmentValidity.id == int(assignment_id),
            RoleAssignmentValidity.tenant_id == tid,
            RoleAssignmentValidity.is_deleted.is_(False)).with_for_update()).first()
        if row is None:
            raise AppException("DATA_NOT_FOUND", "角色授权记录不存在")
        if expected != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "授权记录已被他人更新，请刷新后重试")
        if row.status != VALIDITY_ACTIVE:
            raise AppException("VALIDATION_ERROR", "只有生效中的授权可以转交")
        old_user_id = int(row.user_id)
        target_user_id = int(to_user_id)
        if old_user_id == target_user_id:
            raise AppException("VALIDATION_ERROR", "转交对象不能是本人")
        target = db.scalars(select(User).where(
            User.id == target_user_id,
            User.tenant_id == tid,
            User.is_deleted.is_(False)).with_for_update()).first()
        if target is None:
            raise AppException("DATA_NOT_FOUND", "转交目标账号不存在或不在当前学校")

        role_code = row.role_code
        role = _role_row(db, tid, role_code)
        _assert_role_delegation_allowed(db, actor=user, role=role, tenant_id=tid)
        keep_expires = row.expires_at

        _revoke_assignment_in_db(
            db, row=row, reason=reason, actor=user,
            transferred_to_user_id=target_user_id,
        )
        new_start = _now()
        new_end = _parse_dt(expires_at, "expiresAt") if expires_at is not None else keep_expires
        if new_end is not None and new_end <= new_start:
            raise AppException("VALIDATION_ERROR", "到期时间必须晚于转交生效时间")
        new_validity, _, _ = _grant_assignment_in_db(
            db,
            user_id=target_user_id,
            role_code=role_code,
            reason=reason,
            start=new_start,
            end=new_end,
            source_type=SOURCE_TRANSFER,
            source_id=str(assignment_id),
            tenant_id=tid,
            actor=user,
        )
        row.transferred_to_user_id = target_user_id
        new_assignment_id = int(new_validity.id)

        from app.services import audit_log
        audit_log.record_critical_in_session(
            db,
            "ROLE_ASSIGNMENT_TRANSFER",
            f"role-assignment:{assignment_id}",
            detail={
                "assignmentId": int(assignment_id),
                "fromUserId": old_user_id,
                "toUserId": target_user_id,
                "roleCode": role_code,
                "reason": reason,
                "expectedVersion": expected,
                "sourceType": SOURCE_TRANSFER,
                "expiresAt": str(new_end or ""),
                "newAssignmentId": new_assignment_id,
                "moduleCode": "systemAdmin",
            },
            tenant_id=tid,
            resource_id=str(assignment_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    _invalidate({old_user_id, target_user_id}, tid)
    return get_assignment(new_assignment_id, tenant_id=tid)


def review_assignment(assignment_id: int, *, term: str, reason: str,
                      tenant_id: int | None = None, user: dict | None = None) -> dict:
    """跨学期复核：复核事实与 critical audit 同事务。"""
    from app.models.role_assignment import RoleAssignmentValidity

    reason_text = str(reason or "").strip()
    if len(reason_text) < 5:
        raise AppException("VALIDATION_ERROR", "复核结论不少于 5 个字")
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(RoleAssignmentValidity).where(
            RoleAssignmentValidity.id == int(assignment_id),
            RoleAssignmentValidity.tenant_id == tid,
            RoleAssignmentValidity.is_deleted.is_(False)).with_for_update()).first()
        if row is None:
            raise AppException("DATA_NOT_FOUND", "角色授权记录不存在")
        row.last_reviewed_at = _now()
        row.last_reviewed_term = str(term or "").strip() or None
        row.version = int(row.version or 0) + 1
        from app.services import audit_log
        audit_log.record_critical_in_session(
            db,
            "ROLE_ASSIGNMENT_REVIEW",
            f"role-assignment:{assignment_id}",
            detail={
                "term": term,
                "reason": reason_text,
                "roleCode": row.role_code,
                "userId": int(row.user_id),
                "moduleCode": "systemAdmin",
            },
            tenant_id=tid,
            resource_id=str(assignment_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return get_assignment(int(assignment_id), tenant_id=tid)


def _row_dto(row, link_status: str, login_name: str, real_name: str, *,
             now: datetime) -> dict:
    expires = row.expires_at
    days_left = None
    if expires is not None:
        days_left = int((expires - now).total_seconds() // 86400)
    return {
        "assignmentId": str(row.id),
        "userRoleId": str(row.user_role_id),
        "userId": str(row.user_id),
        "loginName": login_name,
        "realName": real_name,
        "roleCode": row.role_code,
        "status": row.status,
        "linkStatus": link_status,
        "effectiveAt": str(row.effective_at or "")[:19],
        "expiresAt": str(expires or "")[:19],
        "daysLeft": days_left,
        "sourceType": row.source_type,
        "sourceId": row.source_id or "",
        "reason": row.reason or "",
        "grantedBy": str(row.granted_by or ""),
        "lastReviewedAt": str(row.last_reviewed_at or "")[:19],
        "lastReviewedTerm": row.last_reviewed_term or "",
        "transferredToUserId": str(row.transferred_to_user_id or ""),
        "version": int(row.version or 0),
    }


def get_assignment(assignment_id: int, *, tenant_id: int | None = None) -> dict:
    from app.models import User, UserRole
    from app.models.role_assignment import RoleAssignmentValidity

    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(RoleAssignmentValidity).where(
            RoleAssignmentValidity.id == int(assignment_id),
            RoleAssignmentValidity.tenant_id == tid,
            RoleAssignmentValidity.is_deleted.is_(False))).first()
        if row is None:
            raise AppException("DATA_NOT_FOUND", "角色授权记录不存在")
        link = db.get(UserRole, int(row.user_role_id))
        account = db.get(User, int(row.user_id))
        return _row_dto(row, str(getattr(link, "status", "") or ""),
                        getattr(account, "login_name", ""), getattr(account, "real_name", ""),
                        now=_now())
    finally:
        db.close()


def effective_assignments(user_id: int, *, tenant_id: int | None = None) -> list[dict]:
    """某人当前真正生效的角色授权。读取时顺手回收到期项（双保险的第二道）。"""
    from app.core.tenant_scoped import tenant_get
    from app.models import User, UserRole
    from app.models.role_assignment import RoleAssignmentValidity

    tid = _tid(tenant_id)
    now = _now()
    db = get_sessionmaker()()
    try:
        touched = _expire_due(db, tid, now=now, user_id=int(user_id))
        if touched:
            _audit_expiry_in_session(db, tid, touched, source="READ_EFFECTIVE_ASSIGNMENTS")
            db.commit()
        rows = db.scalars(select(RoleAssignmentValidity).where(
            RoleAssignmentValidity.tenant_id == tid,
            RoleAssignmentValidity.user_id == int(user_id),
            RoleAssignmentValidity.status == VALIDITY_ACTIVE,
            RoleAssignmentValidity.is_deleted.is_(False),
            RoleAssignmentValidity.effective_at <= now,
        )).all()
        account = tenant_get(db, User, int(user_id), tenant_id=tid)
        out = []
        for row in rows:
            link = tenant_get(db, UserRole, int(row.user_role_id), tenant_id=tid)
            out.append(_row_dto(row, str(getattr(link, "status", "") or ""),
                                getattr(account, "login_name", ""),
                                getattr(account, "real_name", ""), now=now))
    finally:
        db.close()
    if touched:
        _invalidate(touched, tid)
    return out


def list_assignments(*, tenant_id: int | None = None, role_code: str = "",
                     bucket: str = "", page: int = 1, page_size: int = 50) -> dict:
    """成员列表 + 首屏结论。进来先跑一次回收，页面看到的永远是回收后的真实状态。"""
    from app.models import User, UserRole
    from app.models.role_assignment import RoleAssignmentValidity

    tid = _tid(tenant_id)
    now = _now()
    db = get_sessionmaker()()
    try:
        touched = _expire_due(db, tid, now=now)
        if touched:
            _record_expiry_audit(db, tid, touched, source="READ_LIST_ASSIGNMENTS")
            db.commit()

        stmt = select(RoleAssignmentValidity).where(
            RoleAssignmentValidity.tenant_id == tid,
            RoleAssignmentValidity.is_deleted.is_(False))
        if role_code.strip():
            stmt = stmt.where(RoleAssignmentValidity.role_code == role_code.strip().upper())
        rows = db.scalars(stmt.order_by(RoleAssignmentValidity.id.desc())).all()

        accounts = {int(a.id): a for a in db.scalars(select(User).where(
            User.tenant_id == tid, User.is_deleted.is_(False))).all()}
        links = {int(link.id): link for link in db.scalars(select(UserRole).where(
            UserRole.tenant_id == tid, UserRole.is_deleted.is_(False))).all()}

        items = [
            _row_dto(row, str(getattr(links.get(int(row.user_role_id)), "status", "") or ""),
                     getattr(accounts.get(int(row.user_id)), "login_name", ""),
                     getattr(accounts.get(int(row.user_id)), "real_name", ""), now=now)
            for row in rows
        ]

        # 未登记有效期的历史授权：来源不明，必须让学校看见（在会话内取完值再出去）
        from app.models import Role

        role_by_id = {int(r.id): r.role_code for r in db.scalars(select(Role).where(
            Role.tenant_id == tid, Role.is_deleted.is_(False))).all()}
        registered = {int(r.user_role_id) for r in rows}
        legacy_items = [{
            "assignmentId": "", "userRoleId": str(link.id), "userId": str(link.user_id),
            "loginName": getattr(accounts.get(int(link.user_id)), "login_name", ""),
            "realName": getattr(accounts.get(int(link.user_id)), "real_name", ""),
            "roleCode": role_by_id.get(int(link.role_id), ""),
            "status": VALIDITY_ACTIVE, "linkStatus": str(link.status or ""),
            "effectiveAt": str(link.created_at or "")[:19], "expiresAt": "", "daysLeft": None,
            "sourceType": SOURCE_UNKNOWN, "sourceId": "", "reason": "",
            "grantedBy": "", "lastReviewedAt": "", "lastReviewedTerm": "",
            "transferredToUserId": "", "version": 0,
        } for link in links.values()
            if int(link.id) not in registered and str(link.status or "").upper() == "ACTIVE"]
    finally:
        db.close()
    if touched:
        _invalidate(touched, tid)

    all_items = items + legacy_items
    soon_line = now + timedelta(days=EXPIRING_SOON_DAYS)
    buckets: dict[str, list[dict]] = {
        BUCKET_EXPIRING_SOON: [i for i in all_items
                               if i["status"] == VALIDITY_ACTIVE and i["expiresAt"]
                               and datetime.strptime(i["expiresAt"], "%Y-%m-%d %H:%M:%S") <= soon_line],
        BUCKET_EXPIRED_NOT_RECLAIMED: [i for i in all_items
                                       if i["status"] == VALIDITY_EXPIRED
                                       and i["linkStatus"] == "ACTIVE"],
        BUCKET_UNREVIEWED: [i for i in all_items
                            if i["status"] == VALIDITY_ACTIVE and not i["expiresAt"]
                            and not i["lastReviewedAt"]],
        BUCKET_UNKNOWN_SOURCE: [i for i in all_items if i["sourceType"] == SOURCE_UNKNOWN],
    }
    holders: dict[str, set[str]] = {}
    for i in all_items:
        if i["roleCode"] in HIGH_PRIVILEGE_ROLES and i["status"] == VALIDITY_ACTIVE:
            holders.setdefault(i["roleCode"], set()).add(i["userId"])
    buckets[BUCKET_HIGH_PRIV_MULTI] = [
        {"roleCode": code, "holders": sorted(uids), "count": len(uids)}
        for code, uids in holders.items() if len(uids) > 1
    ]

    if bucket:
        if bucket not in buckets:
            raise AppException("VALIDATION_ERROR", f"未知的分类：{bucket}")
        all_items = buckets[bucket]

    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 50)))
    start = (page - 1) * page_size
    return {
        "list": all_items[start:start + page_size],
        "total": len(all_items),
        "page": page, "pageSize": page_size,
        "summary": {k: len(v) for k, v in buckets.items()},
        "reclaimedNow": len(touched),
    }
