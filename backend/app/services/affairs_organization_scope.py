"""Shared object and member scope for student clubs and organizations."""
from sqlalchemy import and_, false, true

from app.core import affairs_security
from app.core.exceptions import not_found
from app.core.tenant_scoped import tenant_get


def organization_condition(db, user, model):
    ctx = affairs_security.build_affairs_context(user, db)
    if ctx.scope_type == "TENANT_ALL":
        return true()
    if ctx.scope_type != "COLLEGE" or not ctx.college_ids:
        return false()
    condition = model.college_id.in_(ctx.college_ids)
    if hasattr(model, "level"):
        condition = and_(condition, model.level == "COLLEGE")
    return condition


def require_organization(db, user, college_id, *, level=None):
    ctx = affairs_security.build_affairs_context(user, db)
    if college_id is not None:
        from app.models import College
        college = tenant_get(db, College, int(college_id))
        if not college or college.is_deleted:
            raise not_found("所属学院不存在")
    if ctx.scope_type == "TENANT_ALL":
        return
    if (ctx.scope_type != "COLLEGE" or college_id not in ctx.college_ids
            or level not in (None, "COLLEGE")):
        raise affairs_security.no_data_scope("该组织不在您的管理范围内")


def student_condition(user, model):
    class_ids, student_ids = affairs_security.student_directory_scope(user)
    if student_ids is not None:
        return model.id.in_(student_ids) if student_ids else false()
    if class_ids is not None:
        return model.class_id.in_(class_ids) if class_ids else false()
    return true()
