"""Hardened SecurityChange command service.

Non-runtime state transitions delegate to the frozen legacy implementation.
ACTIVATE/ROLLBACK are canonical here because they must atomically materialize
RolePermission and persist critical audit in the same DB transaction.
"""
from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError

from app.modules.system_admin.services import security_change_legacy as _legacy
from app.modules.system_admin.services.role_permission_service import materialize_custom_role_source


def _materialize_custom_role_items(db, tenant_id: int, items) -> list[dict]:
    out = []
    for item in items:
        if item.target_type == _legacy.TARGET_CUSTOM_ROLE:
            out.append(materialize_custom_role_source(db, tenant_id, item.target_id))
    return out


def _invalidate_after_commit(tenant_id: int) -> tuple[bool, str]:
    try:
        from app.services.auth_service_db import invalidate_tenant_subject_caches
        invalidate_tenant_subject_caches(tenant_id)
        return True, ""
    except Exception as exc:  # runtime truth committed; surface cache recovery explicitly
        return False, str(exc)[:200]


def transition(
    change_set_id: int,
    target_status: str,
    *,
    reason: str = "",
    expected_version: int,
    scheduled_at=None,
    self_review_ack: str | None = None,
    tenant_id: int | None = None,
) -> dict:
    target = str(target_status or "").upper()
    if target not in {_legacy.CHANGE_ACTIVATED, _legacy.CHANGE_ROLLED_BACK}:
        return _legacy.transition(
            change_set_id,
            target,
            reason=reason,
            expected_version=expected_version,
            scheduled_at=scheduled_at,
            self_review_ack=self_review_ack,
            tenant_id=tenant_id,
        )

    tid = _legacy._tenant_id(tenant_id)
    trace_id = uuid.uuid4().hex
    with _legacy._session() as db:
        change = _legacy._load(db, tid, change_set_id, lock=True)
        if int(change.version or 0) != int(expected_version):
            raise _legacy.AppException(
                "VERSION_CONFLICT", "该安全变更已被其他人修改，请刷新后重试", http_status=409,
                details={"currentVersion": int(change.version or 0)},
            )
        current = change.status
        if target == current:
            return _legacy._row(change, _legacy._load_items(db, tid, change_set_id))
        if target not in _legacy.ALLOWED_TRANSITIONS.get(current, frozenset()):
            raise _legacy.AppException(
                "STATE_TRANSITION_DENIED", f"不允许从 {current} 变更为 {target}", http_status=409,
                details={"allowed": sorted(_legacy.ALLOWED_TRANSITIONS.get(current, frozenset()))},
            )

        items = _legacy._load_items(db, tid, change_set_id)
        now = _legacy._now()
        if not items:
            raise _legacy.AppException("VALIDATION_ERROR", "空变更集不能激活或回滚")

        if target == _legacy.CHANGE_ACTIVATED:
            _legacy._apply_items(db, tid, items)
            materialized = _materialize_custom_role_items(db, tid, items)
            action = "ACTIVATE"
            audit_action = "SECURITY_CHANGE_ACTIVATE"
        else:
            _legacy._revert_items(db, tid, items)
            materialized = _materialize_custom_role_items(db, tid, items)
            action = "ROLLBACK"
            audit_action = "SECURITY_CHANGE_ROLLBACK"

        revision = _legacy._next_revision(db, tid)
        db.add(_legacy.SecurityActivation(
            tenant_id=tid,
            revision=revision,
            change_set_id=int(change.id),
            action=action,
            snapshot_json={"items": [_legacy._item_snapshot(item) for item in items]},
            actor_user_id=_legacy._actor_id(),
            trace_id=trace_id,
            created_by=_legacy._actor_id(),
            updated_by=_legacy._actor_id(),
        ))

        if target == _legacy.CHANGE_ACTIVATED:
            change.activated_at = now
            change.activated_by_user = _legacy._actor_id()
        else:
            change.rolled_back_at = now
        change.activated_revision = revision
        change.status = target
        change.updated_by = _legacy._actor_id()
        change.version = int(change.version or 0) + 1

        from app.services import audit_log
        audit_log.record_critical_in_session(
            db,
            audit_action,
            f"security-change:{change.id}",
            detail={
                "reason": str(reason or "").strip(),
                "traceId": trace_id,
                "revision": revision,
                "targetStatus": target,
                "materializedRoles": materialized,
            },
            tenant_id=tid,
            resource_id=str(change.id),
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise _legacy.AppException(
                "SECURITY_ACTIVATION_CONFLICT",
                "另一个安全变更正在激活，请刷新后重试",
                http_status=409,
            ) from exc

        cache_ok, cache_error = _invalidate_after_commit(tid)
        db.refresh(change)
        row = _legacy._row(change, _legacy._load_items(db, tid, change_set_id))
        row["runtimeMaterialized"] = True
        row["cacheInvalidated"] = cache_ok
        if not cache_ok:
            row["warning"] = f"权限事实已提交，但缓存失效失败：{cache_error}"
        return row


# Preserve the rest of the existing service surface.
for _name in dir(_legacy):
    if _name.startswith("_") or _name == "transition":
        continue
    globals().setdefault(_name, getattr(_legacy, _name))


def __getattr__(name: str):
    return getattr(_legacy, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy)))
