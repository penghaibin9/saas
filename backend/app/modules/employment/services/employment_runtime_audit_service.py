"""就业中心正式审计列表的 dataScope 投影。

全校范围可查看就业域全量审计；班级/学院/点名范围只返回能够安全映射到本人可见就业学生的
RECORD 审计。材料/跟进历史中存在旧版 biz_id 语义不一致，受限角色宁可少展示，也不跨范围泄漏。
材料详情自身的 auditLogs 已由 employment_runtime_service 在目标 scope 校验后返回。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.affairs_security import build_affairs_context
from app.models import EmpAuditTrail, EmpStudent
from app.modules.employment.services import employment_service as base
from app.modules.employment.services.employment_runtime_service import _scope_condition
from app.services.db_service import _tid, session


def list_audit(page: int, ps: int, *, user: dict, biz_type=None, keyword=None):
    with session() as db:
        ctx = build_affairs_context(user or {}, db)
        cond = [EmpAuditTrail.tenant_id == _tid()]
        if biz_type:
            cond.append(EmpAuditTrail.biz_type == biz_type)
        if keyword and str(keyword).strip():
            text = f"%{str(keyword).strip()}%"
            from sqlalchemy import or_
            cond.append(or_(EmpAuditTrail.action.like(text), EmpAuditTrail.detail.like(text)))

        if ctx.scope_type != "TENANT_ALL":
            scope = _scope_condition(db, user)
            student_stmt = select(EmpStudent.id).where(
                EmpStudent.tenant_id == _tid(), EmpStudent.is_deleted.is_(False))
            if scope is not None:
                student_stmt = student_stmt.where(scope)
            ids = [str(i) for i in db.scalars(student_stmt).all()]
            if not ids:
                return [], 0
            cond.extend([
                EmpAuditTrail.biz_type == "RECORD",
                EmpAuditTrail.biz_id.in_(ids),
            ])

        count_stmt = select(func.count()).select_from(EmpAuditTrail).where(*cond)
        total = int(db.scalar(count_stmt) or 0)
        rows = db.scalars(select(EmpAuditTrail).where(*cond).order_by(
            EmpAuditTrail.id.desc()).offset((max(1, page) - 1) * ps).limit(ps)).all()
        return [base._log_row(row) for row in rows], total
