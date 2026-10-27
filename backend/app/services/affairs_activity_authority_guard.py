"""活动管理权限安全门：非全域角色只能管理本院/本班活动，PC编辑强制原始version。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

_INSTALLED = False


def _normalize_create_scope(db, body, user, current=None) -> None:
    from app.core.affairs_security import build_affairs_context
    from app.services.affairs_activity_scope import resolve_scope_id
    context = build_affairs_context(user, db)
    requested_type = str(getattr(body, "scopeType", None) or (current.scope_type if current else "") or "").upper()
    requested_ref = getattr(body, "scopeRef", None)
    if requested_ref is None and current is not None:
        requested_ref = current.scope_ref
    if not requested_type:
        if context.scope_type == "TENANT_ALL":
            requested_type = "SCHOOL"
        elif context.scope_type in {"CLASS", "COLLEGE"}:
            ids = context.college_ids if context.scope_type == "COLLEGE" else context.allowed_class_ids(db)
            if len(ids or ()) == 1:
                requested_type, requested_ref = context.scope_type, f"id:{next(iter(ids))}"
    if requested_type == "SCHOOL":
        if context.scope_type != "TENANT_ALL":
            raise AppException("NO_DATA_SCOPE", "当前职责不能创建或改为全校活动")
        body.scopeType, body.scopeRef = "SCHOOL", ""
        return
    if requested_type not in {"CLASS", "COLLEGE"}:
        raise AppException("VALIDATION_ERROR", "请选择明确的活动学院或班级范围")
    scope_id = resolve_scope_id(db, requested_type, requested_ref)
    if scope_id is None:
        raise AppException("VALIDATION_ERROR", "活动范围不存在或存在同名歧义，请重新核验范围")
    if context.scope_type != "TENANT_ALL":
        ids = context.college_ids if requested_type == "COLLEGE" else context.allowed_class_ids(db)
        if context.scope_type != requested_type or scope_id not in (ids or set()):
            raise AppException("NO_DATA_SCOPE", "活动范围超出当前职责")
    body.scopeType, body.scopeRef = requested_type, f"id:{scope_id}"


def _require_manage_scope(db, activity_row, user) -> None:
    from app.core.affairs_security import build_affairs_context
    from app.services.affairs_activity_scope import resolve_scope_id
    context = build_affairs_context(user, db)
    if context.scope_type == "TENANT_ALL":
        return
    scope_type = str(activity_row.scope_type or "SCHOOL").upper()
    if scope_type in {"CLASS", "COLLEGE"} and context.scope_type == scope_type:
        ids = context.college_ids if scope_type == "COLLEGE" else context.allowed_class_ids(db)
        if resolve_scope_id(db, scope_type, activity_row.scope_ref) in (ids or set()):
            return
    raise AppException("NO_DATA_SCOPE", "该活动不在您的管理范围内，或历史范围待核验")


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import affairs_activity_service as activity
    from app.services import affairs_four_end_contract as contract

    old_path_predicate = contract._is_affairs_mobile_path
    old_publish = activity.publish_activity
    old_transition = activity.transition_activity
    old_confirm = activity.confirm_activity
    old_unconfirm = activity.unconfirm_activity
    old_archive = activity.archive_activity
    old_category = activity.create_category

    def versioned_activity_path(path: str) -> bool:
        # 精确扩展到“已有活动记录”的PC写路径；/activities 创建和扫描任务不受影响。
        return old_path_predicate(path) or path.startswith("/api/v1/student-affairs/activities/")

    def publish_activity(activity_id, user, action="PUBLISH", reason="", expected_version=None):
        with session() as db:
            _require_manage_scope(db, activity._load(db, activity_id), user)
        return old_publish(activity_id, user, action, reason, expected_version)

    def transition_activity(activity_id, user, action, expected_version=None):
        with session() as db:
            _require_manage_scope(db, activity._load(db, activity_id), user)
        return old_transition(activity_id, user, action, expected_version)

    def confirm_activity(activity_id, user, expected_version=None):
        with session() as db:
            _require_manage_scope(db, activity._load(db, activity_id), user)
        return old_confirm(activity_id, user, expected_version)

    def unconfirm_activity(activity_id, user, reason="", expected_version=None):
        with session() as db:
            _require_manage_scope(db, activity._load(db, activity_id), user)
        return old_unconfirm(activity_id, user, reason, expected_version)

    def archive_activity(activity_id, user, expected_version=None):
        with session() as db:
            _require_manage_scope(db, activity._load(db, activity_id), user)
        return old_archive(activity_id, user, expected_version)

    def create_category(body, user):
        try:
            weight = Decimal(str(getattr(body, "weight", 1) or 1))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise AppException("VALIDATION_ERROR", "类目权重格式非法") from exc
        if not weight.is_finite():
            raise AppException("VALIDATION_ERROR", "类目权重格式非法")
        body.weight = weight
        return old_category(body, user)

    contract._is_affairs_mobile_path = versioned_activity_path
    activity.publish_activity = publish_activity
    activity.transition_activity = transition_activity
    activity.confirm_activity = confirm_activity
    activity.unconfirm_activity = unconfirm_activity
    activity.archive_activity = archive_activity
    activity.create_category = create_category
    _INSTALLED = True
