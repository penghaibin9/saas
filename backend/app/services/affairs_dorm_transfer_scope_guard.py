"""调宿提交与列表的数据范围守卫。

宿管跨楼栋提交调宿时，必须先判断目标楼栋是否属于本人数据范围，再读取学生当前床位等
业务状态。列表则按角色语义分别收敛：宿管按负责楼栋，辅导员/学院按本人学生范围，
学工处按全校范围。未知范围一律空列表，绝不回退全校。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.exceptions import not_found
from app.services.db_service import _tid, session


_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.core.affairs_security import build_affairs_context
    from app.models import DormBed, DormTransfer, StudentProfile
    from app.services import affairs_dorm_service as dorm
    from app.services.affairs_dorm_projection_service import project_transfer_items

    original_submit = dorm.submit_transfer
    original_list = dorm.list_transfers

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
        return original_submit(user, student_id, to_bed_id, reason)

    def list_transfers(user, status=None, page=1, page_size=50, student_id=None):
        """调宿列表按真实职责范围收敛，不把 CLASS/COLLEGE 错当宿管楼栋范围。"""
        with session() as db:
            context = build_affairs_context(user, db)
            # 原实现对这两类范围语义正确：全校不收敛；宿管按目标楼栋收敛，且已经过公共投影。
            if context.scope_type in ("TENANT_ALL", "DORM_BUILDING"):
                return original_list(user, status, page, page_size, student_id)
            if context.scope_type not in ("CLASS", "COLLEGE"):
                return [], 0

            allowed_classes = context.allowed_class_ids(db)
            if not allowed_classes:
                return [], 0

            conds = [
                DormTransfer.tenant_id == _tid(),
                DormTransfer.is_deleted.is_(False),
                StudentProfile.tenant_id == _tid(),
                StudentProfile.is_deleted.is_(False),
                StudentProfile.class_id.in_(list(allowed_classes)),
            ]
            if status == "PENDING":
                conds.append(DormTransfer.status.in_([
                    "PENDING", "SUBMITTED", "COUNSELOR_REVIEW", "DORM_REVIEW", "DORM_MANAGER_REVIEW",
                ]))
            elif status:
                conds.append(DormTransfer.status == status)
            if student_id:
                try:
                    conds.append(DormTransfer.student_id == int(student_id))
                except (TypeError, ValueError):
                    return [], 0

            join_on = StudentProfile.id == DormTransfer.student_id
            total = int(db.scalar(
                select(func.count()).select_from(DormTransfer)
                .join(StudentProfile, join_on)
                .where(*conds)
            ) or 0)
            page, page_size = dorm.normalize_page(page, page_size)
            rows = db.execute(
                select(DormTransfer, StudentProfile)
                .join(StudentProfile, join_on)
                .where(*conds)
                .order_by(DormTransfer.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
            out = []
            for transfer, student in rows:
                item = dorm._transfer_row(transfer)
                item["realName"] = student.real_name or ""
                item["studentNo"] = student.student_no or ""
                out.append(item)
            # CLASS/COLLEGE 自己完成范围过滤后，也必须进入与宿管/全校一致的投影层；
            # 否则会丢 from/toBedLabel 和 allowedActions，PC/小程序只能看到内部床位 ID 且无法审批。
            return project_transfer_items(out, user), total

    dorm.submit_transfer = submit_transfer
    dorm.list_transfers = list_transfers
    _INSTALLED = True
