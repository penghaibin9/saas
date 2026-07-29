"""调宿提交的目标楼栋前置授权守卫。

宿管跨楼栋提交调宿时，必须先判断目标楼栋是否属于本人数据范围，
再读取学生当前床位等业务状态。否则越权调用会通过不同的 409 详情泄露
学生是否已有床位。本守卫只前置授权，正式节点服务仍会重复完成全部状态校验。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import not_found
from app.services.db_service import _tid, session


_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.core.affairs_security import build_affairs_context
    from app.models import DormBed
    from app.services import affairs_dorm_service as dorm

    original = dorm.submit_transfer

    def submit_transfer(user, student_id, to_bed_id, reason=""):
        with session() as db:
            context = build_affairs_context(user, db)
            if context.scope_type == "DORM_BUILDING":
                target = db.scalars(select(DormBed).where(
                    DormBed.tenant_id == _tid(),
                    DormBed.id == int(to_bed_id),
                    DormBed.is_deleted.is_(False),
                )).first()
                if not target:
                    raise not_found("目标床位不存在")
                dorm._require_dorm_scope(db, target.building_id, user)
        return original(user, student_id, to_bed_id, reason)

    dorm.submit_transfer = submit_transfer
    _INSTALLED = True
