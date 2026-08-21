"""Production guard for SYS-03 identity binding writes used by the P1 UI closure.

The legacy service already validates stable identities, but its write helpers read the
account/link without row locks and write audit after commit. This guard makes the two
browser-facing mutations serializable and atomically audited without changing legacy
read semantics or unrelated batch callers.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker


def _tenant_id() -> int:
    tenant_id = int(current_tenant_id() or 0)
    if tenant_id <= 0:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return tenant_id


def _actor_id(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or (user or {}).get("id") or "").strip()
    if raw.startswith("db-"):
        raw = raw[3:]
    return int(raw) if raw.isdigit() else None


def _account_for_update(db, tenant_id: int, user_id: int):
    from app.models import User

    row = db.scalars(select(User).where(
        User.id == int(user_id),
        User.tenant_id == int(tenant_id),
        User.is_deleted.is_(False),
    ).with_for_update()).first()
    if row is None:
        raise AppException("DATA_NOT_FOUND", "账号不存在或不在当前学校范围内", http_status=404)
    return row


def _active_link_for_update(db, tenant_id: int, *, user_id: int | None = None, student_id: int | None = None):
    from app.models import StudentAccountLink

    stmt = select(StudentAccountLink).where(
        StudentAccountLink.tenant_id == int(tenant_id),
        StudentAccountLink.link_status == "ACTIVE",
        StudentAccountLink.is_deleted.is_(False),
    )
    if user_id is not None:
        stmt = stmt.where(StudentAccountLink.user_id == int(user_id))
    if student_id is not None:
        stmt = stmt.where(StudentAccountLink.student_id == int(student_id))
    return db.scalars(stmt.with_for_update()).first()


def _require_expected_version(account, expected_version) -> int:
    if expected_version is None:
        raise AppException("VALIDATION_ERROR", "身份绑定写操作必须提供 expectedVersion")
    try:
        expected = int(expected_version)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "expectedVersion 必须是整数") from None
    current = int(account.version or 0)
    if current != expected:
        raise AppException(
            "DATA_CONFLICT", "账号已被其他人更新，请刷新后重试", http_status=409,
            details={"expectedVersion": expected, "currentVersion": current},
        )
    return current


def repair_binding(
    user_id: int,
    *,
    student_id: int,
    reason: str,
    expected_version,
    user: dict | None,
) -> dict:
    """Atomically replace/create the ACTIVE account→student link and critical audit."""
    from app.models import StudentAccountLink, StudentProfile
    from app.services import audit_log

    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "修复绑定的原因不少于 5 个字")
    tenant_id = _tenant_id()
    actor_id = _actor_id(user)
    db = get_sessionmaker()()
    try:
        account = _account_for_update(db, tenant_id, int(user_id))
        current_version = _require_expected_version(account, expected_version)

        # Lock the stable student subject first. This serializes two accounts racing to
        # claim a student even when no StudentAccountLink row exists yet.
        profile = db.scalars(select(StudentProfile).where(
            StudentProfile.id == int(student_id),
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.is_deleted.is_(False),
        ).with_for_update()).first()
        if profile is None:
            raise AppException("DATA_NOT_FOUND", "学籍主档不存在或不在当前学校范围内", http_status=404)

        occupied = _active_link_for_update(db, tenant_id, student_id=int(profile.id))
        if occupied is not None and int(occupied.user_id) != int(account.id):
            raise AppException(
                "DATA_CONFLICT", "该学籍已绑定其他账号，请先处理现有绑定", http_status=409,
                details={"occupiedUserId": str(occupied.user_id)},
            )

        before = _active_link_for_update(db, tenant_id, user_id=int(account.id))
        if before is not None and int(before.student_id) == int(profile.id):
            raise AppException("VALIDATION_ERROR", "该账号已绑定到此学籍，无需修复")
        previous_student_id = str(before.student_id) if before is not None else ""
        if before is not None:
            before.link_status = "REVOKED"
            before.updated_by = actor_id
            before.version = int(before.version or 0) + 1
            db.flush()

        link = StudentAccountLink(
            tenant_id=tenant_id,
            student_id=int(profile.id),
            user_id=int(account.id),
            link_status="ACTIVE",
            source="MANUAL",
            bound_login_name=account.login_name,
            bound_student_no=profile.student_no,
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(link)
        account.version = current_version + 1
        db.flush()

        audit_log.record_critical_in_session(
            db,
            "ACCOUNT_BINDING_REPAIR",
            f"user:{account.id}",
            detail={
                "reason": reason,
                "userId": str(account.id),
                "studentId": str(profile.id),
                "previousStudentId": previous_student_id,
                "moduleCode": "systemAdmin",
                "expectedVersion": current_version,
                "newVersion": int(account.version or 0),
            },
            tenant_id=tenant_id,
            resource_id=str(account.id),
        )
        db.commit()
        result_user_id = int(account.id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    try:
        from app.services.auth_service_db import invalidate_subject_cache
        invalidate_subject_cache(f"db-{result_user_id}", tenant_id)
    except Exception:
        pass
    from app.services import account_identity_resolution_service as identity
    return identity.effective_identity(result_user_id, tenant_id=tenant_id)


def unbind(
    user_id: int,
    *,
    reason: str,
    expected_version,
    user: dict | None,
) -> dict:
    """Atomically revoke the ACTIVE stable binding and write critical audit evidence."""
    from app.services import audit_log

    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "解绑原因不少于 5 个字")
    tenant_id = _tenant_id()
    actor_id = _actor_id(user)
    db = get_sessionmaker()()
    try:
        account = _account_for_update(db, tenant_id, int(user_id))
        current_version = _require_expected_version(account, expected_version)
        link = _active_link_for_update(db, tenant_id, user_id=int(account.id))
        if link is None:
            raise AppException("DATA_NOT_FOUND", "该账号当前没有有效绑定", http_status=404)

        student_id = int(link.student_id)
        link.link_status = "REVOKED"
        link.updated_by = actor_id
        link.version = int(link.version or 0) + 1
        account.version = current_version + 1
        db.flush()

        audit_log.record_critical_in_session(
            db,
            "ACCOUNT_BINDING_REVOKE",
            f"user:{account.id}",
            detail={
                "reason": reason,
                "userId": str(account.id),
                "studentId": str(student_id),
                "moduleCode": "systemAdmin",
                "expectedVersion": current_version,
                "newVersion": int(account.version or 0),
            },
            tenant_id=tenant_id,
            resource_id=str(account.id),
        )
        db.commit()
        result_user_id = int(account.id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    try:
        from app.services.auth_service_db import invalidate_subject_cache
        invalidate_subject_cache(f"db-{result_user_id}", tenant_id)
    except Exception:
        pass
    from app.services import account_identity_resolution_service as identity
    return identity.effective_identity(result_user_id, tenant_id=tenant_id)
