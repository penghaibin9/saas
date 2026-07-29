"""学生 SELF 数据范围安全门。

统一安全上下文原本把 SELF 的 allowed_class_ids 返回空集，却没有在 require_student
中单独处理，导致学生本人调用复用管理服务时也被 403。这里由服务端解析账号绑定，
只允许本人主档 ID，既恢复本人业务，又不信任请求体里的 studentId。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import not_found
from app.services.db_service import session

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.core import affairs_security as security

    old_build = security.build_affairs_context
    old_require = security.StudentAffairsSecurityContext.require_student

    def build_affairs_context(user: dict, db=None):
        context = old_build(user, db)
        if context.scope_type != "SELF" or context.self_student_id:
            return context
        from app.services.mobile_student_service import resolve_student
        if db is not None:
            student = resolve_student(db, user or {})
        else:
            with session() as own_db:
                student = resolve_student(own_db, user or {})
        if student:
            context.self_student_id = int(student.id)
            context.is_scope_configured = True
            context.scope_source = "ACCOUNT_LINK_SELF"
        return context

    def require_student(self, db, student_id):
        if self.scope_type != "SELF":
            return old_require(self, db, student_id)
        from app.models import StudentProfile
        try:
            target_id = int(student_id)
        except (TypeError, ValueError):
            raise not_found("学生不存在")
        student = db.scalars(select(StudentProfile).where(
            StudentProfile.id == target_id,
            StudentProfile.tenant_id == self.tenant_id,
            StudentProfile.is_deleted.is_(False),
        )).first()
        if not student:
            raise not_found("学生不存在")
        if not self.self_student_id or int(self.self_student_id) != target_id:
            raise security.no_data_scope("学生只能访问本人数据")
        return student

    security.build_affairs_context = build_affairs_context
    security.StudentAffairsSecurityContext.require_student = require_student
    _INSTALLED = True
