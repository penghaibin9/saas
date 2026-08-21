"""Production guards for SYS-07 formal role assignments.

The legacy service owns persistence/audit mechanics. This layer closes the authorization
holes that matter to runtime: disabled-role grants, student/staff role mixing, duplicate
overwrite, future grants becoming active too early, and removal of the final active
SCHOOL_ADMIN. All protected mutations keep the guard and business write in one DB
transaction by reusing the legacy service's in-session primitives.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models import Role, StudentAccountLink, User, UserRole
from app.models.role_assignment import (
    SOURCE_MANUAL,
    SOURCE_TRANSFER,
    VALIDITY_ACTIVE,
    RoleAssignmentValidity,
)
from app.services import role_assignment_service as ras


def _tid(value: int | None = None) -> int:
    return int(value if value is not None else ras._tid(None))


def _lock_role(db, tenant_id: int, role_code: str) -> Role:
    code = str(role_code or "").strip().upper()
    role = db.scalars(select(Role).where(
        Role.tenant_id == tenant_id,
        Role.role_code == code,
        Role.is_deleted.is_(False),
    ).with_for_update()).first()
    if role is None:
        raise AppException("DATA_NOT_FOUND", f"角色不存在：{code}")
    if str(role.status or "").upper() not in {"ACTIVE", "ENABLED"}:
        raise AppException("STATE_TRANSITION_DENIED", "已停用角色不能新增、恢复或转交授权", http_status=409)
    return role


def _lock_account(db, tenant_id: int, user_id: int) -> User:
    account = db.scalars(select(User).where(
        User.id == int(user_id),
        User.tenant_id == tenant_id,
        User.is_deleted.is_(False),
    ).with_for_update()).first()
    if account is None:
        raise AppException("DATA_NOT_FOUND", "账号不存在或不在当前学校范围内")
    return account


def _is_student_account(db, tenant_id: int, account: User) -> bool:
    if str(account.user_type or "").upper() == "STUDENT":
        return True
    link = db.scalars(select(StudentAccountLink.id).where(
        StudentAccountLink.tenant_id == tenant_id,
        StudentAccountLink.user_id == int(account.id),
        StudentAccountLink.link_status == "ACTIVE",
        StudentAccountLink.is_deleted.is_(False),
    ).limit(1)).first()
    if link is not None:
        return True
    student_role = db.scalars(select(UserRole.id).join(
        Role, Role.id == UserRole.role_id,
    ).where(
        UserRole.tenant_id == tenant_id,
        UserRole.user_id == int(account.id),
        UserRole.status == "ACTIVE",
        UserRole.is_deleted.is_(False),
        Role.role_code == "STUDENT",
        Role.is_deleted.is_(False),
    ).limit(1)).first()
    return student_role is not None


def _assert_account_role_compatibility(db, tenant_id: int, account: User, role_code: str) -> None:
    student = _is_student_account(db, tenant_id, account)
    target_is_student = str(role_code or "").strip().upper() == "STUDENT"
    if student and not target_is_student:
        raise AppException("NO_PERMISSION", "学生账号固定绑定 STUDENT，禁止授予教职工或管理员角色")
    if not student and target_is_student:
        raise AppException("VALIDATION_ERROR", "教职工账号不能授予 STUDENT 角色")


def _active_assignment_for(db, tenant_id: int, user_id: int, role_id: int):
    return db.scalars(select(RoleAssignmentValidity).join(
        UserRole, UserRole.id == RoleAssignmentValidity.user_role_id,
    ).where(
        RoleAssignmentValidity.tenant_id == tenant_id,
        RoleAssignmentValidity.user_id == int(user_id),
        RoleAssignmentValidity.status == VALIDITY_ACTIVE,
        RoleAssignmentValidity.is_deleted.is_(False),
        UserRole.tenant_id == tenant_id,
        UserRole.user_id == int(user_id),
        UserRole.role_id == int(role_id),
        UserRole.status == "ACTIVE",
        UserRole.is_deleted.is_(False),
    ).with_for_update()).first()


def _assert_not_last_school_admin(db, tenant_id: int, user_id: int, role: Role) -> None:
    if str(role.role_code or "").upper() != "SCHOOL_ADMIN":
        return
    # Lock the role first (caller does this) and then every current holder so two
    # concurrent revocations serialize instead of both observing "2 admins".
    links = list(db.scalars(select(UserRole).where(
        UserRole.tenant_id == tenant_id,
        UserRole.role_id == int(role.id),
        UserRole.status == "ACTIVE",
        UserRole.is_deleted.is_(False),
    ).with_for_update()).all())
    active_holders = 0
    target_is_holder = False
    for link in links:
        account = db.get(User, int(link.user_id))
        if account is None or account.is_deleted or str(account.status or "").upper() != "ACTIVE":
            continue
        active_holders += 1
        if int(link.user_id) == int(user_id):
            target_is_holder = True
    if target_is_holder and active_holders <= 1:
        raise AppException("VALIDATION_ERROR", "不能回收本校最后一名启用中的学校管理员")


def grant_assignment(
    user_id: int,
    role_code: str,
    *,
    reason: str,
    effective_at: Any = None,
    expires_at: Any = None,
    tenant_id: int | None = None,
    user: dict | None = None,
) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "授予原因不少于 5 个字")
    tid = _tid(tenant_id)
    now = ras._now()
    start = ras._parse_dt(effective_at, "effectiveAt") or now
    # The runtime authority is t_user_role and there is no future-activation worker.
    # Accepting a future date would grant the role immediately, which is privilege
    # escalation disguised as scheduling. Fail closed until a real activation worker exists.
    if start > now:
        raise AppException("VALIDATION_ERROR", "正式角色暂不支持未来排期；请在需要生效时再授权")
    end = ras._parse_dt(expires_at, "expiresAt")
    if end is not None and end <= now:
        raise AppException("VALIDATION_ERROR", "到期时间必须晚于当前时间")

    db = get_sessionmaker()()
    try:
        role = _lock_role(db, tid, role_code)
        account = _lock_account(db, tid, int(user_id))
        _assert_account_role_compatibility(db, tid, account, role.role_code)
        ras._assert_role_delegation_allowed(db, actor=user, role=role, tenant_id=tid)
        if _active_assignment_for(db, tid, int(user_id), int(role.id)) is not None:
            raise AppException("DATA_CONFLICT", "该账号已持有此角色；请在现有授权记录上复核、转交或回收", http_status=409)

        validity, account, role = ras._grant_assignment_in_db(
            db,
            user_id=int(user_id),
            role_code=role.role_code,
            reason=reason,
            start=now,
            end=end,
            source_type=SOURCE_MANUAL,
            source_id=None,
            tenant_id=tid,
            actor=user,
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
                "effectiveAt": str(now),
                "expiresAt": str(end or ""),
                "sourceType": SOURCE_MANUAL,
                "moduleCode": "systemAdmin",
                "productionGuard": True,
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
    ras._invalidate({int(user_id)}, tid)
    return ras.get_assignment(assignment_id, tenant_id=tid)


def revoke_assignment(
    assignment_id: int,
    *,
    reason: str,
    expected_version: int | None,
    tenant_id: int | None = None,
    user: dict | None = None,
) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "回收原因不少于 5 个字")
    expected = ras._require_expected_version(expected_version, operation="角色回收")
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(RoleAssignmentValidity).where(
            RoleAssignmentValidity.id == int(assignment_id),
            RoleAssignmentValidity.tenant_id == tid,
            RoleAssignmentValidity.is_deleted.is_(False),
        ).with_for_update()).first()
        if row is None:
            raise AppException("DATA_NOT_FOUND", "角色授权记录不存在")
        if expected != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "授权记录已被他人更新，请刷新后重试", http_status=409)
        role = _lock_role(db, tid, row.role_code)
        ras._assert_role_delegation_allowed(db, actor=user, role=role, tenant_id=tid)
        _assert_not_last_school_admin(db, tid, int(row.user_id), role)
        old_user_id = ras._revoke_assignment_in_db(db, row=row, reason=reason, actor=user)
        from app.services import audit_log
        audit_log.record_critical_in_session(
            db,
            "ROLE_ASSIGNMENT_REVOKE",
            f"role-assignment:{assignment_id}",
            detail={
                "userId": old_user_id,
                "roleCode": row.role_code,
                "reason": reason,
                "expectedVersion": expected,
                "moduleCode": "systemAdmin",
                "productionGuard": True,
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
    ras._invalidate({old_user_id}, tid)
    return ras.get_assignment(int(assignment_id), tenant_id=tid)


def transfer_assignment(
    assignment_id: int,
    *,
    to_user_id: int,
    reason: str,
    expires_at: Any = None,
    expected_version: int | None,
    tenant_id: int | None = None,
    user: dict | None = None,
) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "转交原因不少于 5 个字")
    expected = ras._require_expected_version(expected_version, operation="角色转交")
    tid = _tid(tenant_id)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(RoleAssignmentValidity).where(
            RoleAssignmentValidity.id == int(assignment_id),
            RoleAssignmentValidity.tenant_id == tid,
            RoleAssignmentValidity.is_deleted.is_(False),
        ).with_for_update()).first()
        if row is None:
            raise AppException("DATA_NOT_FOUND", "角色授权记录不存在")
        if expected != int(row.version or 0):
            raise AppException("DATA_CONFLICT", "授权记录已被他人更新，请刷新后重试", http_status=409)
        if row.status != VALIDITY_ACTIVE:
            raise AppException("STATE_TRANSITION_DENIED", "只有生效中的授权可以转交", http_status=409)
        old_user_id = int(row.user_id)
        target_user_id = int(to_user_id)
        if old_user_id == target_user_id:
            raise AppException("VALIDATION_ERROR", "转交对象不能是本人")

        role = _lock_role(db, tid, row.role_code)
        target = _lock_account(db, tid, target_user_id)
        _assert_account_role_compatibility(db, tid, target, role.role_code)
        ras._assert_role_delegation_allowed(db, actor=user, role=role, tenant_id=tid)
        if _active_assignment_for(db, tid, target_user_id, int(role.id)) is not None:
            raise AppException("DATA_CONFLICT", "转交目标已经持有该角色", http_status=409)

        keep_expires = row.expires_at
        new_end = ras._parse_dt(expires_at, "expiresAt") if expires_at is not None else keep_expires
        now = ras._now()
        if new_end is not None and new_end <= now:
            raise AppException("VALIDATION_ERROR", "到期时间必须晚于转交生效时间")

        ras._revoke_assignment_in_db(
            db,
            row=row,
            reason=reason,
            actor=user,
            transferred_to_user_id=target_user_id,
        )
        new_validity, _, _ = ras._grant_assignment_in_db(
            db,
            user_id=target_user_id,
            role_code=role.role_code,
            reason=reason,
            start=now,
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
                "roleCode": role.role_code,
                "reason": reason,
                "expectedVersion": expected,
                "newAssignmentId": new_assignment_id,
                "moduleCode": "systemAdmin",
                "productionGuard": True,
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
    ras._invalidate({old_user_id, target_user_id}, tid)
    return ras.get_assignment(new_assignment_id, tenant_id=tid)
