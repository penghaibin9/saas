"""活动管理权限安全门：非全域角色只能管理本院/本班活动，PC编辑强制原始version。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from app.core.exceptions import AppException
from app.services.db_service import _tid, session

_INSTALLED = False


def _tokens(db, context):
    from app.models import College, SchoolClass
    class_rows = db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == _tid(),
        SchoolClass.id.in_(context.allowed_class_ids(db) or {-1}),
        SchoolClass.is_deleted.is_(False),
    )).all()
    class_tokens = set()
    for row in class_rows:
        class_tokens.update(filter(None, {
            str(row.id), str(row.class_code or "").strip(), str(row.class_name or "").strip(),
        }))
    college_rows = db.scalars(select(College).where(
        College.tenant_id == _tid(),
        College.id.in_(context.college_ids or {-1}),
        College.is_deleted.is_(False),
    )).all()
    college_tokens = set()
    for row in college_rows:
        college_tokens.update(filter(None, {
            str(row.id), str(row.code or "").strip(),
            str(row.college_name or "").strip(), str(row.short_name or "").strip(),
        }))
    return class_tokens, college_tokens


def _normalize_create_scope(body, user) -> None:
    from app.core.affairs_security import build_affairs_context
    with session() as db:
        context = build_affairs_context(user, db)
        requested_type = str(getattr(body, "scopeType", None) or "").upper()
        requested_ref = str(getattr(body, "scopeRef", None) or "").strip()
        if context.scope_type == "TENANT_ALL":
            if not requested_type:
                body.scopeType, body.scopeRef = "SCHOOL", None
                return
            if requested_type == "SCHOOL":
                body.scopeRef = None
                return
            class_tokens, college_tokens = _tokens(db, context)
            if requested_type == "CLASS":
                from app.models import SchoolClass
                exists = db.scalars(select(SchoolClass.id).where(
                    SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False),
                    (SchoolClass.id == int(requested_ref)) if requested_ref.isdigit()
                    else (SchoolClass.class_code == requested_ref) | (SchoolClass.class_name == requested_ref),
                )).first()
                if not exists:
                    raise AppException("VALIDATION_ERROR", "活动班级范围不存在")
                return
            if requested_type == "COLLEGE":
                from app.models import College
                exists = db.scalars(select(College.id).where(
                    College.tenant_id == _tid(), College.is_deleted.is_(False),
                    (College.id == int(requested_ref)) if requested_ref.isdigit()
                    else (College.code == requested_ref) | (College.college_name == requested_ref),
                )).first()
                if not exists:
                    raise AppException("VALIDATION_ERROR", "活动学院范围不存在")
                return
            raise AppException("VALIDATION_ERROR", "活动范围类型仅支持SCHOOL/COLLEGE/CLASS")

        class_tokens, college_tokens = _tokens(db, context)
        if context.scope_type == "COLLEGE":
            if not requested_type and len(context.college_ids) == 1:
                body.scopeType, body.scopeRef = "COLLEGE", str(next(iter(context.college_ids)))
                return
            if requested_type != "COLLEGE" or requested_ref not in college_tokens:
                raise AppException("NO_DATA_SCOPE", "学院角色只能创建本院活动")
            return
        if context.scope_type == "CLASS":
            class_ids = context.allowed_class_ids(db) or set()
            if not requested_type and len(class_ids) == 1:
                body.scopeType, body.scopeRef = "CLASS", str(next(iter(class_ids)))
                return
            if requested_type != "CLASS" or requested_ref not in class_tokens:
                raise AppException("NO_DATA_SCOPE", "辅导员只能创建本人负责班级的活动")
            return
        raise AppException("NO_PERMISSION", "当前数据范围不允许管理活动")


def _require_manage_scope(db, activity_row, user) -> None:
    from app.core.affairs_security import build_affairs_context
    context = build_affairs_context(user, db)
    if context.scope_type == "TENANT_ALL":
        return
    scope_type = str(activity_row.scope_type or "SCHOOL").upper()
    scope_ref = str(activity_row.scope_ref or "").strip()
    class_tokens, college_tokens = _tokens(db, context)
    if context.scope_type == "COLLEGE" and scope_type == "COLLEGE" and scope_ref in college_tokens:
        return
    if context.scope_type == "CLASS" and scope_type == "CLASS" and scope_ref in class_tokens:
        return
    raise AppException("NO_DATA_SCOPE", "该活动不在您的管理范围内")


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.services import affairs_activity_service as activity
    from app.services import affairs_four_end_contract as contract

    old_path_predicate = contract._is_affairs_mobile_path
    old_create = activity.create_activity
    old_update = activity.update_activity
    old_publish = activity.publish_activity
    old_transition = activity.transition_activity
    old_confirm = activity.confirm_activity
    old_unconfirm = activity.unconfirm_activity
    old_archive = activity.archive_activity
    old_category = activity.create_category

    def versioned_activity_path(path: str) -> bool:
        # 精确扩展到“已有活动记录”的PC写路径；/activities 创建和扫描任务不受影响。
        return old_path_predicate(path) or path.startswith("/api/v1/student-affairs/activities/")

    def create_activity(body, user):
        _normalize_create_scope(body, user)
        return old_create(body, user)

    def update_activity(activity_id, body, user):
        with session() as db:
            row = activity._load(db, activity_id)
            _require_manage_scope(db, row, user)
        return old_update(activity_id, body, user)

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
    activity.create_activity = create_activity
    activity.update_activity = update_activity
    activity.publish_activity = publish_activity
    activity.transition_activity = transition_activity
    activity.confirm_activity = confirm_activity
    activity.unconfirm_activity = unconfirm_activity
    activity.archive_activity = archive_activity
    activity.create_category = create_category
    _INSTALLED = True
