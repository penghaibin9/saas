"""优秀成果/延期答辩的跨端安全补强。

收口三类容易被 UI 与排期流程遗漏的边界：
1. 被驳回/撤回的历史延期记录不能永久阻止学生再次申请；
2. 延期重新分组必须同时重算并撤回旧组、新组发布状态，且校验新组容量；
3. 学校端按钮按稳定导师身份和当前审核角色逐行下发，避免“看得见但必失败”。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.exceptions import AppException, not_found
from app.models import GraduationDefenseGroup, GraduationGrade, GraduationStudent
from app.models.graduation_extension import GraduationDefenseDelay, GraduationExcellentOutcome
from app.modules.graduation.services import graduation_extension_service as base
from app.modules.graduation.services.graduation_record_resolver import resolve_current_gd_student
from app.services.db_service import _tid, session

_ACTIVE_DELAY_STATUSES = {
    "PENDING_ADVISOR",
    "PENDING_MAJOR",
    "PENDING_COLLEGE",
    "APPROVED",
    "SCHEDULED",
}


def my_extensions(user: dict) -> dict:
    """返回学生扩展事项，并正确计算延期再次申请资格。"""
    with session() as db:
        student = resolve_current_gd_student(db, user)
        if not student:
            return {
                "hasData": False,
                "excellentOutcome": None,
                "defenseDelay": None,
                "canApplyDelay": False,
            }

        excellent = db.scalars(select(GraduationExcellentOutcome).where(
            GraduationExcellentOutcome.tenant_id == _tid(),
            GraduationExcellentOutcome.gd_student_id == student.id,
            GraduationExcellentOutcome.is_deleted.is_(False),
        ).order_by(GraduationExcellentOutcome.id.desc())).first()
        delay = db.scalars(select(GraduationDefenseDelay).where(
            GraduationDefenseDelay.tenant_id == _tid(),
            GraduationDefenseDelay.gd_student_id == student.id,
            GraduationDefenseDelay.is_deleted.is_(False),
        ).order_by(GraduationDefenseDelay.id.desc())).first()
        group = db.get(GraduationDefenseGroup, delay.defense_group_id) if delay and delay.defense_group_id else None
        published_grade = db.scalars(select(GraduationGrade.id).where(
            GraduationGrade.tenant_id == _tid(),
            GraduationGrade.gd_student_id == student.id,
            GraduationGrade.status == "PUBLISHED",
            GraduationGrade.is_deleted.is_(False),
        ).limit(1)).first()
        has_active_delay = bool(delay and delay.status in _ACTIVE_DELAY_STATUSES)

        return {
            "hasData": True,
            "gdStudentId": str(student.id),
            "batchId": str(student.batch_id or ""),
            "excellentOutcome": base._excellent_row(excellent, student) if excellent else None,
            "defenseDelay": base._delay_row(delay, student, group) if delay else None,
            "canApplyDelay": (
                student.stage in ("FINAL_CHECK", "DEFENSE")
                and not has_active_delay
                and not published_grade
            ),
        }


def list_delays(*, batch_id: int, status: str | None = None, page: int = 1, page_size: int = 20):
    """分页台账 + 当前角色逐行可执行动作。"""
    items, total = base.list_delays(
        batch_id=batch_id, status=status, page=page, page_size=page_size,
    )
    if not items:
        return items, total

    role = base._role()
    with session() as db:
        from app.modules.graduation.services import graduation_identity as gid
        mentor = gid.current_user_mentor(db)
        mentor_id = int(mentor.id) if mentor else None
        for item in items:
            student = db.get(GraduationStudent, int(item["gdStudentId"]))
            owns_student = bool(
                mentor_id and student and student.mentor_id
                and int(student.mentor_id) == mentor_id
            )
            item["allowedActions"] = {
                "advisorReview": item["status"] == "PENDING_ADVISOR" and owns_student,
                "majorReview": item["status"] == "PENDING_MAJOR" and role in base._MAJOR_ROLES,
                "collegeReview": item["status"] == "PENDING_COLLEGE" and role in base._COLLEGE_ROLES,
                "schedule": item["status"] == "APPROVED" and role in base._COLLEGE_ROLES,
            }
    return items, total


def schedule_delay(record_id, defense_group_id, planned_date: str) -> dict:
    """安全重新排期，同时维护旧组/新组人数、回避冲突与发布状态。"""
    base._require_college()
    planned = str(planned_date or "").strip()
    if not planned:
        raise AppException("VALIDATION_ERROR", "延期答辩日期必填")
    try:
        record_id_int = int(record_id)
        group_id_int = int(defense_group_id)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "延期答辩申请和答辩组参数无效") from None

    with session() as db:
        row = db.get(GraduationDefenseDelay, record_id_int, with_for_update=True)
        if not row or row.is_deleted or row.tenant_id != _tid():
            raise not_found("延期答辩申请不存在")
        student = base._student(db, row.gd_student_id)
        if row.status != "APPROVED":
            raise AppException("DATA_CONFLICT", "仅学院已批准申请可重新排期")

        group = db.get(GraduationDefenseGroup, group_id_int, with_for_update=True)
        if (
            not group
            or group.is_deleted
            or group.tenant_id != _tid()
            or int(group.batch_id or 0) != int(row.batch_id)
        ):
            raise AppException("DATA_CONFLICT", "延期答辩组不存在或与学生批次不一致")
        if group.defense_date and str(group.defense_date) != planned:
            raise AppException("DATA_CONFLICT", "所选答辩组日期与延期日期不一致，请新建独立延期答辩组")

        occupied = int(db.scalar(select(func.count()).select_from(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.defense_group_id == group.id,
            GraduationStudent.id != student.id,
            GraduationStudent.is_deleted.is_(False),
        )) or 0)
        from app.modules.graduation.services import graduation_service as graduation_svc
        if occupied >= graduation_svc.MAX_DEFENSE_STUDENTS:
            raise AppException(
                "DATA_CONFLICT",
                f"延期答辩组人数已达上限 {graduation_svc.MAX_DEFENSE_STUDENTS} 人，请选择其他答辩组",
            )

        old_group = None
        if student.defense_group_id and int(student.defense_group_id) != int(group.id):
            old_group = db.get(GraduationDefenseGroup, int(student.defense_group_id), with_for_update=True)
            if old_group and (old_group.is_deleted or old_group.tenant_id != _tid()):
                old_group = None

        group.defense_date = planned
        group.published = False
        if old_group:
            old_group.published = False

        student.defense_group_id = group.id
        student.defense_group = group.group_name
        student.stage = "DEFENSE"
        student.version = int(student.version or 0) + 1

        row.status = "SCHEDULED"
        row.planned_defense_date = planned
        row.defense_group_id = group.id
        row.scheduled_at = base._now()
        row.version = int(row.version or 0) + 1

        if old_group:
            graduation_svc._recompute_defense(db, old_group)
        graduation_svc._recompute_defense(db, group)
        base._audit(
            db,
            "DEFENSE_DELAY",
            row.id,
            "SCHEDULE",
            f"oldGroup={getattr(old_group, 'id', None)};newGroup={group.id};date={planned}",
            batch_id=row.batch_id,
        )
        db.commit()
        return base._delay_row(row, student, group)
