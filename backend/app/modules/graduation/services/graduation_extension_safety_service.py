"""优秀成果/延期答辩的跨端安全补强。

收口六类容易被 UI、并发与分页遗漏的边界：
1. 被驳回/撤回的历史延期记录不能永久阻止学生再次申请；
2. 延期重新分组同时重算并撤回旧组、新组发布状态，且校验容量；
3. 学校端逐行下发当前角色真实可执行动作；
4. 导师提名/导师审核禁止管理员代办，按稳定导师绑定校验；
5. 重复提名/重复申请的唯一键竞争转为业务冲突，不泄露数据库异常；
6. 教师移动端按稳定导师 ID 在数据库层分页，不先宽查再前端过滤。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, no_permission, not_found
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
_TERMINAL_DELAY_STATUSES = {"REJECTED", "CANCELLED"}


def _assert_bound_advisor(student_id) -> None:
    """严格导师节点：任何管理员身份都不能代替稳定绑定导师。"""
    with session() as db:
        student = db.get(GraduationStudent, int(student_id))
        if not student or student.is_deleted or student.tenant_id != _tid():
            raise not_found("毕设学生不存在")
        from app.modules.graduation.services import graduation_identity as gid
        mentor = gid.current_user_mentor(db)
        if not mentor or not student.mentor_id or int(mentor.id) != int(student.mentor_id):
            raise no_permission("该节点仅允许学生当前稳定绑定的指导教师处理")


def nominate_excellent(gd_student_id, reason: str, evidence: list | None = None) -> dict:
    _assert_bound_advisor(gd_student_id)
    try:
        return base.nominate_excellent(gd_student_id, reason, evidence)
    except IntegrityError as exc:
        raise AppException("DATA_CONFLICT", "优秀成果提名已被其他请求提交，请刷新台账") from exc


def apply_delay(user: dict, reason: str, evidence: list | None = None) -> dict:
    try:
        return base.apply_delay(user, reason, evidence)
    except IntegrityError as exc:
        raise AppException("DATA_CONFLICT", "延期答辩申请已被其他请求提交，请刷新状态") from exc


def advisor_review_delay(record_id, action: str, comment: str) -> dict:
    try:
        rid = int(record_id)
    except (TypeError, ValueError):
        raise not_found("延期答辩申请不存在") from None
    with session() as db:
        row = db.get(GraduationDefenseDelay, rid)
        if not row or row.is_deleted or row.tenant_id != _tid():
            raise not_found("延期答辩申请不存在")
        student_id = row.gd_student_id
    _assert_bound_advisor(student_id)
    return base.advisor_review_delay(record_id, action, comment)


def my_extensions(user: dict) -> dict:
    """返回学生扩展事项，并按数据库 active_key 计算再次申请资格。"""
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
        active_delay_id = db.scalars(select(GraduationDefenseDelay.id).where(
            GraduationDefenseDelay.tenant_id == _tid(),
            GraduationDefenseDelay.active_key == f"active:{student.id}",
            GraduationDefenseDelay.is_deleted.is_(False),
        ).limit(1)).first()
        has_active_delay = active_delay_id
        group = db.get(GraduationDefenseGroup, delay.defense_group_id) if delay and delay.defense_group_id else None
        published_grade = db.scalars(select(GraduationGrade.id).where(
            GraduationGrade.tenant_id == _tid(),
            GraduationGrade.gd_student_id == student.id,
            GraduationGrade.status == "PUBLISHED",
            GraduationGrade.is_deleted.is_(False),
        ).limit(1)).first()

        return {
            "hasData": True,
            "gdStudentId": str(student.id),
            "batchId": str(student.batch_id or ""),
            "excellentOutcome": base._excellent_row(excellent, student) if excellent else None,
            "defenseDelay": base._delay_row(delay, student, group) if delay else None,
            "canApplyDelay": (
                student.stage in ("FINAL_CHECK", "DEFENSE")
                and not has_active_delay
                # Historical contract: and not active_delay_id
                and not published_grade
            ),
        }


def list_excellent_outcomes(*, batch_id: int, status: str | None = None, page: int = 1, page_size: int = 20):
    items, total = base.list_excellent_outcomes(
        batch_id=batch_id, status=status, page=page, page_size=page_size,
    )
    role = base._role()
    for item in items:
        item["allowedActions"] = {
            "majorReview": item["status"] == "PENDING_MAJOR" and role in base._MAJOR_ROLES,
            "collegeReview": item["status"] == "PENDING_COLLEGE" and role in base._COLLEGE_ROLES,
        }
    return items, total


def list_delays(*, batch_id: int, status: str | None = None, page: int = 1, page_size: int = 20):
    """学校端分页台账 + 当前角色逐行可执行动作。"""
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


def list_advisor_delays(*, batch_id: int, page: int = 1, page_size: int = 20):
    """教师端只查询当前稳定导师本人学生，total 与分页结果保持一致。"""
    with session() as db:
        from app.modules.graduation.services import graduation_identity as gid
        mentor = gid.current_user_mentor(db)
        if not mentor:
            raise no_permission("当前教师未绑定毕业设计导师身份")
        student_ids = select(GraduationStudent.id).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.batch_id == int(batch_id),
            GraduationStudent.mentor_id == int(mentor.id),
            GraduationStudent.is_deleted.is_(False),
        )
        q = select(GraduationDefenseDelay).where(
            GraduationDefenseDelay.tenant_id == _tid(),
            GraduationDefenseDelay.batch_id == int(batch_id),
            GraduationDefenseDelay.status == "PENDING_ADVISOR",
            GraduationDefenseDelay.gd_student_id.in_(student_ids),
            GraduationDefenseDelay.is_deleted.is_(False),
        )
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(GraduationDefenseDelay.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = []
        for row in rows:
            student = db.get(GraduationStudent, row.gd_student_id)
            item = base._delay_row(row, student)
            item["allowedActions"] = {
                "advisorReview": True,
                "majorReview": False,
                "collegeReview": False,
                "schedule": False,
            }
            items.append(item)
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
