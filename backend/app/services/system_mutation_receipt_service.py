"""System-management durable mutation receipts.

Critical school mutations commit the database and audit evidence in one
transaction. Auth-cache invalidation happens afterwards and may degrade, but a
cache failure must never make an already-committed mutation look rolled back.
The receipt mirrors Platform W3 and exposes cache-only recovery paths.
"""
from __future__ import annotations

import secrets
from typing import Any

from sqlalchemy import func, select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker


def _tenant_id() -> int:
    tid = int(current_tenant_id() or 0)
    if not tid:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文", http_status=400)
    return tid


def _actor_id(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or (user or {}).get("id") or "").removeprefix("db-")
    return int(raw) if raw.isdigit() else None


def _optional_version(value, *, current: int, label: str) -> tuple[int, bool]:
    """Explicit expectedVersion is strict; N-1 omission stays visible as compatibility."""
    if value in (None, ""):
        return int(current), False
    try:
        expected = int(value)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{label} expectedVersion 必须是整数", http_status=422) from None
    if expected != int(current):
        raise AppException(
            "DATA_CONFLICT", f"{label}已被其他管理员更新，请刷新后重试", http_status=409,
            details={"expectedVersion": expected, "currentVersion": int(current)},
        )
    return expected, True


def _required_reason(value, *, label: str, minimum: int = 5) -> str:
    text = str(value or "").strip()
    if len(text) < minimum:
        raise AppException("VALIDATION_ERROR", f"{label}原因不少于 {minimum} 个字", http_status=422)
    return text


def _subject_cache_receipt(user_id: int, tenant_id: int) -> dict:
    from app.services.auth_service_db import invalidate_subject_cache

    try:
        removed = int(invalidate_subject_cache(f"db-{int(user_id)}", int(tenant_id)) or 0)
        return {
            "cacheInvalidated": True,
            "cacheRecoveryRequired": False,
            "removedKeys": removed,
            "warning": "",
            "postCommitError": "",
        }
    except Exception as exc:
        return {
            "cacheInvalidated": False,
            "cacheRecoveryRequired": True,
            "removedKeys": 0,
            "warning": "数据库变更已生效，但该账号权限缓存刷新失败；请只执行缓存恢复，不要重放业务操作",
            "postCommitError": str(exc)[:500],
        }


def _tenant_cache_receipt(tenant_id: int) -> dict:
    from app.services.auth_service_db import invalidate_tenant_subject_caches

    try:
        removed = int(invalidate_tenant_subject_caches(int(tenant_id)) or 0)
        return {
            "cacheInvalidated": True,
            "cacheRecoveryRequired": False,
            "removedKeys": removed,
            "warning": "",
            "postCommitError": "",
        }
    except Exception as exc:
        return {
            "cacheInvalidated": False,
            "cacheRecoveryRequired": True,
            "removedKeys": 0,
            "warning": "数据库变更已生效，但学校权限缓存刷新失败；请只执行缓存恢复，不要重放业务操作",
            "postCommitError": str(exc)[:500],
        }


def _audit_cache_degraded(action: str, resource: str, tenant_id: int, receipt: dict, detail: dict) -> None:
    if receipt.get("cacheInvalidated"):
        return
    try:
        from app.services import audit_log

        audit_log.record(
            "SYSTEM_AUTH_CACHE_RECOVERY_REQUIRED",
            resource,
            detail={
                "sourceAction": action,
                **detail,
                "runtimeMaterialized": True,
                "cacheInvalidated": False,
                "postCommitError": receipt.get("postCommitError") or "",
                "moduleCode": "systemAdmin",
            },
            result="DEGRADED",
            tenant_id=int(tenant_id),
        )
    except Exception:
        pass


def set_user_status(
    user_id: int, *, action: str, reason: str = "", expected_version=None, user: dict | None = None,
) -> dict:
    from app.models import User
    from app.modules.system_admin.routers import system_bundle as bundle
    from app.services import audit_log

    tenant_id = _tenant_id()
    normalized = str(action or "").strip().upper()
    if normalized not in {"DISABLE", "ENABLE", "UNLOCK"}:
        raise AppException("VALIDATION_ERROR", "action 必须是 DISABLE / ENABLE / UNLOCK", http_status=422)
    reason_text = _required_reason(reason, label="停用") if normalized == "DISABLE" else str(reason or "").strip()
    actor_id = _actor_id(user)
    if normalized == "DISABLE" and actor_id == int(user_id):
        raise AppException("VALIDATION_ERROR", "不能停用当前登录的本人账号", http_status=422)

    db = get_sessionmaker()()
    try:
        account = db.scalars(select(User).where(
            User.id == int(user_id),
            User.tenant_id == tenant_id,
            User.is_deleted.is_(False),
        ).with_for_update()).first()
        if account is None:
            raise AppException("DATA_NOT_FOUND", "账号不存在", http_status=404)
        version_before = int(account.version or 0)
        _, occ = _optional_version(expected_version, current=version_before, label="账号")
        before = str(account.status or "").upper()
        if normalized == "DISABLE":
            if bundle._is_last_active_school_admin(db, tenant_id, int(account.id)):
                raise AppException("VALIDATION_ERROR", "不能停用本校最后一名启用中的学校管理员", http_status=422)
            target = "DISABLED"
        elif normalized == "UNLOCK":
            if before != "LOCKED":
                raise AppException("DATA_CONFLICT", "账号当前不是锁定状态，请刷新后重试", http_status=409)
            target = "ACTIVE"
        else:
            target = "ACTIVE"

        idempotent = before == target
        login_name = account.login_name
        if not idempotent:
            account.status = target
            account.version = version_before + 1
            action_code = {"DISABLE": "USER_DISABLE", "ENABLE": "USER_ENABLE", "UNLOCK": "USER_UNLOCK"}[normalized]
            audit_log.record_critical_in_session(
                db,
                action_code,
                f"user:{account.id}",
                detail={
                    "loginName": account.login_name,
                    "before": before,
                    "after": target,
                    "reason": reason_text,
                    "expectedVersion": expected_version,
                    "versionBefore": version_before,
                    "versionAfter": int(account.version),
                    "moduleCode": "systemAdmin",
                },
                tenant_id=tenant_id,
                resource_id=str(account.id),
            )
            db.commit()
            version_after = int(account.version)
        else:
            action_code = "USER_STATUS_IDEMPOTENT_CACHE_RECOVERY"
            version_after = version_before
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    cache = _subject_cache_receipt(int(user_id), tenant_id)
    _audit_cache_degraded(action_code, f"user:{user_id}", tenant_id, cache, {
        "userId": str(user_id), "loginName": login_name, "version": version_after,
        "idempotent": idempotent,
    })
    return {
        "id": str(user_id),
        "status": target,
        "statusLabel": "已停用" if target == "DISABLED" else "启用中",
        "version": version_after,
        "runtimeMaterialized": True,
        "idempotent": idempotent,
        "optimisticLockEnforced": occ,
        **cache,
    }


def reset_user_password(
    user_id: int, *, expected_version=None, reason: str = "管理员重置密码", user: dict | None = None,
) -> dict:
    """Commit password + audit first; cache failure must not swallow the one-time secret."""
    from app.core.security import hash_password
    from app.models import User
    from app.services import audit_log

    tenant_id = _tenant_id()
    db = get_sessionmaker()()
    try:
        account = db.scalars(select(User).where(
            User.id == int(user_id),
            User.tenant_id == tenant_id,
            User.is_deleted.is_(False),
        ).with_for_update()).first()
        if account is None:
            raise AppException("DATA_NOT_FOUND", "账号不存在", http_status=404)
        version_before = int(account.version or 0)
        _, occ = _optional_version(expected_version, current=version_before, label="账号")
        temp_password = "Tmp" + secrets.token_urlsafe(6)
        account.password_hash = hash_password(temp_password)
        account.must_change_password = True
        account.version = version_before + 1
        audit_log.record_critical_in_session(
            db,
            "RESET_PASSWORD",
            f"user:{account.id}",
            detail={
                "summary": "重置密码：已生成一次性临时密码，强制首登改密",
                "reason": str(reason or "管理员重置密码"),
                "userId": int(account.id),
                "loginName": account.login_name,
                "versionBefore": version_before,
                "versionAfter": int(account.version),
                "moduleCode": "systemAdmin",
            },
            result="SUCCESS",
            tenant_id=tenant_id,
            resource_id=str(account.id),
        )
        db.commit()
        version_after = int(account.version)
        login_name = account.login_name
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    cache = _subject_cache_receipt(int(user_id), tenant_id)
    _audit_cache_degraded("RESET_PASSWORD", f"user:{user_id}", tenant_id, cache, {
        "userId": str(user_id), "loginName": login_name, "version": version_after,
    })
    return {
        "id": str(user_id),
        "tempPassword": temp_password,
        "mustChangePassword": True,
        "version": version_after,
        "runtimeMaterialized": True,
        "optimisticLockEnforced": occ,
        "notice": "临时密码仅本次显示，请立即转交本人；该账号首次登录须强制改密",
        **cache,
    }


def set_role_status(
    role_id: int, *, action: str, reason: str = "", expected_version=None, user: dict | None = None,
) -> dict:
    from app.models import Role, UserRole
    from app.services import audit_log

    tenant_id = _tenant_id()
    normalized = str(action or "").strip().upper()
    if normalized not in {"DISABLE", "ENABLE"}:
        raise AppException("VALIDATION_ERROR", "action 必须是 DISABLE 或 ENABLE", http_status=422)
    reason_text = _required_reason(reason, label="停用角色") if normalized == "DISABLE" else str(reason or "").strip()

    db = get_sessionmaker()()
    try:
        role = db.scalars(select(Role).where(
            Role.id == int(role_id),
            Role.tenant_id == tenant_id,
            Role.is_deleted.is_(False),
        ).with_for_update()).first()
        if role is None:
            raise AppException("DATA_NOT_FOUND", "角色不存在", http_status=404)
        if str(role.role_type or "").upper() == "SYSTEM":
            raise AppException("VALIDATION_ERROR", "预设角色不可停用或启用", http_status=422)
        version_before = int(role.version or 0)
        _, occ = _optional_version(expected_version, current=version_before, label="角色")
        before = str(role.status or "").upper()
        target = "DISABLED" if normalized == "DISABLE" else "ACTIVE"
        if normalized == "DISABLE":
            members = int(db.scalar(select(func.count(UserRole.id)).where(
                UserRole.tenant_id == tenant_id,
                UserRole.role_id == int(role.id),
                UserRole.status == "ACTIVE",
                UserRole.is_deleted.is_(False),
            )) or 0)
            if members > 0:
                raise AppException("DATA_CONFLICT", f"该角色仍有 {members} 名成员，请先改派成员再停用", http_status=409)
        idempotent = before == target
        role_code = role.role_code
        if not idempotent:
            role.status = target
            role.version = version_before + 1
            action_code = "ROLE_DISABLE" if normalized == "DISABLE" else "ROLE_ENABLE"
            audit_log.record_critical_in_session(
                db,
                action_code,
                f"role:{role.id}",
                detail={
                    "roleCode": role.role_code,
                    "before": before,
                    "after": target,
                    "reason": reason_text,
                    "expectedVersion": expected_version,
                    "versionBefore": version_before,
                    "versionAfter": int(role.version),
                    "moduleCode": "systemAdmin",
                },
                tenant_id=tenant_id,
                resource_id=str(role.id),
            )
            db.commit()
            version_after = int(role.version)
        else:
            action_code = "ROLE_STATUS_IDEMPOTENT_CACHE_RECOVERY"
            version_after = version_before
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    cache = _tenant_cache_receipt(tenant_id)
    _audit_cache_degraded(action_code, f"role:{role_id}", tenant_id, cache, {
        "roleId": str(role_id), "roleCode": role_code, "version": version_after,
        "idempotent": idempotent,
    })
    return {
        "id": str(role_id), "status": target, "version": version_after,
        "runtimeMaterialized": True, "idempotent": idempotent,
        "optimisticLockEnforced": occ, **cache,
    }


def _student_scope_ids(db, tenant_id: int, scope: str, filters: dict) -> list[int]:
    from app.models import StudentAccountLink, StudentProfile, User
    from app.modules.system_admin.routers import system_bundle as bundle

    stmt = select(User.id).where(
        User.tenant_id == tenant_id,
        User.is_deleted.is_(False),
        User.status == "ACTIVE",
        bundle._account_type_condition(User, "STUDENT", tenant_id),
    )
    if scope != "SCHOOL":
        profile = select(StudentAccountLink.user_id).join(
            StudentProfile, StudentProfile.id == StudentAccountLink.student_id,
        ).where(
            StudentAccountLink.tenant_id == tenant_id,
            StudentAccountLink.link_status == "ACTIVE",
            StudentAccountLink.is_deleted.is_(False),
            StudentProfile.tenant_id == tenant_id,
            StudentProfile.is_deleted.is_(False),
        )
        if scope == "CLASS":
            raw = str(filters.get("classId") or "")
            if not raw.isdigit():
                raise AppException("VALIDATION_ERROR", "请选择具体班级", http_status=422)
            profile = profile.where(StudentProfile.class_id == int(raw))
        elif scope == "COLLEGE":
            raw = str(filters.get("collegeId") or "")
            if not raw.isdigit():
                raise AppException("VALIDATION_ERROR", "请选择具体学院", http_status=422)
            profile = profile.where(StudentProfile.college_id == int(raw))
        elif scope == "GRADE":
            raw = str(filters.get("grade") or "").strip()
            if not raw:
                raise AppException("VALIDATION_ERROR", "请选择具体年级", http_status=422)
            profile = profile.where(StudentProfile.grade == raw)
        else:
            raise AppException("VALIDATION_ERROR", "批量停用范围无效", http_status=422)
        stmt = stmt.where(User.id.in_(profile))
    return [int(value) for value in db.scalars(stmt.order_by(User.id)).all()]


def batch_set_user_status(body: dict, *, user: dict | None = None) -> dict:
    """Batch-disable with explicit per-subject cache outcome after durable writes."""
    from app.models import User
    from app.modules.system_admin.routers import system_bundle as bundle
    from app.services import audit_log

    tenant_id = _tenant_id()
    payload = dict(body or {})
    action = str(payload.get("action") or "DISABLE").strip().upper()
    scope = str(payload.get("scope") or "SELECTED").strip().upper()
    reason = _required_reason(payload.get("reason"), label="批量停用") if action == "DISABLE" else str(payload.get("reason") or "")
    if action not in {"DISABLE", "ENABLE"}:
        raise AppException("VALIDATION_ERROR", "批量操作只支持 DISABLE / ENABLE", http_status=422)
    if scope not in {"SELECTED", "CLASS", "GRADE", "COLLEGE", "SCHOOL"}:
        raise AppException("VALIDATION_ERROR", "批量停用范围无效", http_status=422)
    account_type = bundle._normalize_account_type(payload.get("accountType")) if payload.get("accountType") else ""
    if scope != "SELECTED" and (action != "DISABLE" or account_type != "STUDENT"):
        raise AppException("VALIDATION_ERROR", "班级、年级、学院和全校范围仅支持批量停用学生账号", http_status=422)
    if scope == "SCHOOL" and payload.get("confirmSchoolScope") is not True:
        raise AppException("VALIDATION_ERROR", "全校停用属于高风险操作，请完成全校范围二次确认", http_status=422)

    ids = [int(x) for x in (payload.get("ids") or []) if str(x).isdigit()]
    db = get_sessionmaker()()
    try:
        if scope != "SELECTED":
            ids = _student_scope_ids(db, tenant_id, scope, dict(payload.get("filters") or {}))
        if not ids:
            raise AppException("VALIDATION_ERROR", "没有可处理的账号", http_status=422)
        unique_ids = sorted(set(ids))
        if account_type:
            matched = int(db.scalar(select(func.count(User.id)).where(
                User.tenant_id == tenant_id,
                User.id.in_(unique_ids),
                User.is_deleted.is_(False),
                bundle._account_type_condition(User, account_type, tenant_id),
            )) or 0)
            if matched != len(unique_ids):
                raise AppException("VALIDATION_ERROR", "所选账号包含其他类型，已拒绝批量操作", http_status=422)

        actor_id = _actor_id(user)
        accounts = list(db.scalars(select(User).where(
            User.tenant_id == tenant_id,
            User.id.in_(unique_ids),
            User.is_deleted.is_(False),
        ).order_by(User.id).with_for_update()).all())
        by_id = {int(row.id): row for row in accounts}
        results: list[dict[str, Any]] = []
        changed_ids: list[int] = []
        for uid in unique_ids:
            account = by_id.get(uid)
            if account is None:
                results.append({"id": str(uid), "status": "FAILED", "message": "账号不存在"})
                continue
            if action == "DISABLE" and actor_id == uid:
                results.append({"id": str(uid), "status": "FAILED", "message": "不能停用本人"})
                continue
            if action == "DISABLE" and bundle._is_last_active_school_admin(db, tenant_id, uid):
                results.append({"id": str(uid), "status": "FAILED", "message": "不能停用本校最后一名启用中的学校管理员"})
                continue
            target = "DISABLED" if action == "DISABLE" else "ACTIVE"
            if str(account.status or "").upper() == target:
                results.append({"id": str(uid), "status": "OK", "message": "状态未变化", "idempotent": True})
                continue
            account.status = target
            account.version = int(account.version or 0) + 1
            changed_ids.append(uid)
            results.append({"id": str(uid), "status": "OK", "message": "已停用" if target == "DISABLED" else "已启用"})

        audit_log.record_critical_in_session(
            db,
            "USER_BATCH_DISABLE" if action == "DISABLE" else "USER_BATCH_ENABLE",
            f"tenant:{tenant_id}:accounts",
            detail={
                "scope": scope,
                "count": len(changed_ids),
                "requestedCount": len(unique_ids),
                "reason": reason,
                "changedUserIds": [str(uid) for uid in changed_ids[:500]],
                "moduleCode": "systemAdmin",
                "optimisticLockEnforced": False,
            },
            tenant_id=tenant_id,
            resource_id=str(tenant_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    cache_failed: list[str] = []
    removed_keys = 0
    successful_ids = [int(row["id"]) for row in results if row["status"] == "OK"]
    for uid in successful_ids:
        receipt = _subject_cache_receipt(uid, tenant_id)
        removed_keys += int(receipt.get("removedKeys") or 0)
        if not receipt.get("cacheInvalidated"):
            cache_failed.append(str(uid))
    cache_ok = not cache_failed
    summary = {
        "count": sum(1 for row in results if row["status"] == "OK"),
        "errors": [{"id": row["id"], "message": row["message"]} for row in results if row["status"] != "OK"],
        "results": results,
        "total": len(results),
        "succeeded": sum(1 for row in results if row["status"] == "OK"),
        "failed": sum(1 for row in results if row["status"] != "OK"),
        "scope": scope,
        "runtimeMaterialized": True,
        "cacheInvalidated": cache_ok,
        "cacheRecoveryRequired": not cache_ok,
        "cacheFailedUserIds": cache_failed,
        "removedKeys": removed_keys,
        "optimisticLockEnforced": False,
        "warning": "" if cache_ok else "批量账号状态已提交，但部分账号缓存刷新失败；请只执行缓存恢复",
    }
    if not cache_ok:
        _audit_cache_degraded(
            "USER_BATCH_STATUS", f"tenant:{tenant_id}:accounts", tenant_id,
            {"cacheInvalidated": False, "postCommitError": f"failed subjects: {','.join(cache_failed[:50])}"},
            {"scope": scope, "cacheFailedUserIds": cache_failed[:100]},
        )
    return summary


def recover_subject_cache(user_id: int) -> dict:
    """Cache-only recovery for one school account; no user mutation is replayed."""
    from app.models import User
    from app.services import audit_log

    tenant_id = _tenant_id()
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(User).where(
            User.id == int(user_id), User.tenant_id == tenant_id, User.is_deleted.is_(False),
        )).first()
        if row is None:
            raise AppException("DATA_NOT_FOUND", "账号不存在", http_status=404)
        version_before = int(row.version or 0)
        status = str(row.status or "")
    finally:
        db.close()
    receipt = _subject_cache_receipt(int(user_id), tenant_id)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(User).where(
            User.id == int(user_id), User.tenant_id == tenant_id, User.is_deleted.is_(False),
        )).first()
        version_after = int(row.version or 0) if row is not None else -1
    finally:
        db.close()
    if version_after != version_before:
        raise AppException(
            "CACHE_RECOVERY_MUTATED_RUNTIME",
            "缓存恢复期间账号版本发生变化，请刷新后重试",
            http_status=409,
            details={"beforeVersion": version_before, "afterVersion": version_after},
        )
    try:
        audit_log.record(
            "SYSTEM_USER_AUTH_CACHE_RECOVERY",
            f"user:{user_id}",
            detail={"version": version_after, "cacheInvalidated": receipt["cacheInvalidated"], "moduleCode": "systemAdmin"},
            result="SUCCESS" if receipt["cacheInvalidated"] else "DEGRADED",
            tenant_id=tenant_id,
        )
    except Exception:
        pass
    return {
        "id": str(user_id), "status": status, "version": version_after,
        "runtimeMaterialized": True, **receipt,
    }


def recover_tenant_auth_cache() -> dict:
    """Cache-only recovery for role/permission changes in the current school."""
    from app.services import audit_log

    tenant_id = _tenant_id()
    receipt = _tenant_cache_receipt(tenant_id)
    try:
        audit_log.record(
            "SYSTEM_TENANT_AUTH_CACHE_RECOVERY",
            f"tenant:{tenant_id}",
            detail={"cacheInvalidated": receipt["cacheInvalidated"], "moduleCode": "systemAdmin"},
            result="SUCCESS" if receipt["cacheInvalidated"] else "DEGRADED",
            tenant_id=tenant_id,
        )
    except Exception:
        pass
    return {"tenantId": str(tenant_id), "runtimeMaterialized": True, **receipt}