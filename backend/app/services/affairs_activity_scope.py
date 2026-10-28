"""活动稳定范围与旧引用唯一解析，供管理、报名和分页过滤共用。"""
from sqlalchemy import String, and_, cast, func, literal, or_, select
from sqlalchemy.orm import aliased

from app.services.db_service import _tid


def _model(scope_type):
    from app.models import College, SchoolClass
    return {"COLLEGE": College, "CLASS": SchoolClass}[scope_type]


def _matches(entity, reference, scope_type):
    ref = (literal(reference.strip()) if isinstance(reference, str) else func.trim(reference)).collate("utf8mb4_unicode_ci")
    identifier = cast(entity.id, String).collate("utf8mb4_unicode_ci")
    aliases = [entity.college_name, entity.code, entity.short_name] if scope_type == "COLLEGE" else [entity.class_name, entity.class_code]
    alias_match = or_(*[column.collate("utf8mb4_unicode_ci") == ref for column in aliases])
    canonical = func.concat("id:", identifier).collate("utf8mb4_unicode_ci") == ref
    target = and_(ref != "", or_(canonical, and_(~ref.like("id:%"), or_(identifier == ref, alias_match))))
    # 历史上与新编号格式同字的名称也计入歧义，不能因启用新格式被转授给另一对象。
    return target, or_(target, alias_match)


def resolve_scope_id(db, scope_type, reference):
    if not str(reference or "").strip():
        return None
    entity = _model(scope_type)
    target, matches = _matches(entity, str(reference or ""), scope_type)
    rows = db.execute(select(entity.id, entity.is_deleted, target.label("target")).where(
        entity.tenant_id == _tid(), matches,
    ).limit(2)).all()
    if len(rows) != 1 or rows[0].is_deleted or not rows[0].target:
        return None
    return int(rows[0].id)


def scope_condition(activity_model, scope_type, allowed_ids):
    entity = aliased(_model(scope_type))
    target, matches = _matches(entity, activity_model.scope_ref, scope_type)
    # 软删对象参与计数，防止删后重建的同名对象继承旧活动范围。
    match_count = select(func.count(entity.id)).where(
        entity.tenant_id == _tid(), matches,
    ).correlate(activity_model).scalar_subquery()
    visible = select(entity.id).where(
        entity.tenant_id == _tid(), entity.id.in_(allowed_ids or {-1}),
        entity.is_deleted.is_(False), target,
    ).correlate(activity_model).exists()
    return and_(match_count == 1, visible)
