"""13B-P3 教学任务（批次生成→分配教师→教师确认→提交审核 ACAD_TASK_CONFIRM）。

按已发布培养方案(ENABLED+ACTIVE绑定)生成应开课程的教学任务(课程×教学班)，generate 幂等。
含商业软件标配：教学班(可合班)、周学时/起止周、多环节确认。教师确认/退回，批次两级确认后提交审核。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

_TEACH_WEEKS = 18  # 默认学期教学周（真实：应读校历，V1 取常规 18 周）


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_type, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


def _task_row(t) -> dict:
    return {"taskId": str(t.id), "batchId": str(t.batch_id), "courseId": str(t.course_id),
            "courseCode": t.course_code or "", "courseName": t.course_name or "",
            "classId": str(t.class_id or ""), "teachingClassName": t.teaching_class_name or "",
            "isMerged": bool(t.is_merged), "teacherId": str(t.teacher_id or ""),
            "teacherName": t.teacher_name or "", "expectedStudents": t.expected_students,
            "weeklyHours": t.weekly_hours, "totalHours": t.total_hours,
            "startWeek": t.start_week, "endWeek": t.end_week, "status": t.status}


# ═══════════ 批次生成（幂等）═══════════

def generate_batch(body, user) -> dict:
    """按已发布方案生成教学任务批次。幂等：同(term,college)复用批次，已存在(course,class)任务不重复。"""
    term_id = int(body.termId)
    college_id = int(body.collegeId) if getattr(body, "collegeId", None) else None
    with session() as db:
        from app.models import (AaProgram, AaProgramBinding, AaProgramCourse, AaCourse,
                                AaTeachingTask, AaTeachingTaskBatch, SchoolClass)
        # 幂等：找现有 DRAFT 批次或新建
        batch = db.scalars(select(AaTeachingTaskBatch).where(
            AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.term_id == term_id,
            AaTeachingTaskBatch.status == "DRAFT", AaTeachingTaskBatch.is_deleted.is_(False))).first()
        if not batch:
            batch = AaTeachingTaskBatch(tenant_id=_tid(), term_id=term_id,
                                        batch_name=(getattr(body, "batchName", None) or f"学期{term_id}教学任务"),
                                        college_id=college_id, generate_at=datetime.utcnow(), status="DRAFT")
            db.add(batch)
            db.flush()
        made = 0
        # 已启用方案 + ACTIVE 绑定 → 方案课程 → 教学任务
        prog_conds = [AaProgram.tenant_id == _tid(), AaProgram.status == "ENABLED",
                      AaProgram.is_deleted.is_(False)]
        for p in db.scalars(select(AaProgram).where(*prog_conds)).all():
            bindings = db.scalars(select(AaProgramBinding).where(
                AaProgramBinding.tenant_id == _tid(), AaProgramBinding.program_id == p.id,
                AaProgramBinding.status == "ACTIVE", AaProgramBinding.class_id.is_not(None),
                AaProgramBinding.is_deleted.is_(False))).all()
            courses = db.scalars(select(AaProgramCourse).where(
                AaProgramCourse.tenant_id == _tid(), AaProgramCourse.program_id == p.id,
                AaProgramCourse.is_deleted.is_(False))).all()
            for bd in bindings:
                cls = db.get(SchoolClass, int(bd.class_id))
                for pc in courses:
                    if not pc.course_id:
                        continue
                    # 幂等去重
                    exist = db.scalars(select(AaTeachingTask).where(
                        AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id == batch.id,
                        AaTeachingTask.course_id == pc.course_id, AaTeachingTask.class_id == bd.class_id,
                        AaTeachingTask.is_deleted.is_(False))).first()
                    if exist:
                        continue
                    course = db.get(AaCourse, int(pc.course_id))
                    hours = (course.hours_total if course and course.hours_total else 0)
                    db.add(AaTeachingTask(
                        tenant_id=_tid(), batch_id=batch.id, course_id=pc.course_id,
                        course_code=course.course_code if course else "",
                        course_name=course.course_name if course else "",
                        class_id=bd.class_id,
                        teaching_class_name=f"{course.course_name if course else ''}({cls.class_name if cls else ''})",
                        total_hours=hours, weekly_hours=(round(hours / _TEACH_WEEKS) if hours else None),
                        start_week=1, end_week=_TEACH_WEEKS, status="PENDING_ASSIGN"))
                    made += 1
        _audit(db, "AA_TASK_BATCH", batch.id, "GENERATE", f"+{made}")
        db.commit()
        db.refresh(batch)
        return {"batchId": str(batch.id), "batchName": batch.batch_name, "status": batch.status,
                "tasksGenerated": made}


# ═══════════ 分配 / 教师确认 ═══════════

def assign_teacher(task_id, user, body) -> dict:
    with session() as db:
        from app.models import AaTeachingTask
        t = db.get(AaTeachingTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("教学任务不存在")
        if t.status not in ("PENDING_ASSIGN", "REJECTED_BY_TEACHER", "ASSIGNED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该任务当前状态不可分配")
        t.teacher_id = int(body.teacherId) if getattr(body, "teacherId", None) else None
        t.teacher_key = getattr(body, "teacherKey", None)
        t.teacher_name = getattr(body, "teacherName", None)
        if getattr(body, "weeklyHours", None) is not None:
            t.weekly_hours = body.weeklyHours
        if getattr(body, "expectedStudents", None) is not None:
            t.expected_students = body.expectedStudents
        if getattr(body, "isMerged", None) is not None:
            t.is_merged = bool(body.isMerged)
        t.status, t.reject_reason = "ASSIGNED", None
        _audit(db, "AA_TASK", t.id, "ASSIGN", t.teacher_name or "")
        db.commit()
        db.refresh(t)
        return _task_row(t)


def teacher_act(task_id, user, action, reason="") -> dict:
    """教师确认/退回教学任务。"""
    action = (action or "").upper()
    with session() as db:
        from app.models import AaTeachingTask
        t = db.get(AaTeachingTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("教学任务不存在")
        if t.status != "ASSIGNED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已分配任务可确认/退回")
        if action == "CONFIRM":
            t.status, t.confirm_at = "TEACHER_CONFIRMED", datetime.utcnow()
            _audit(db, "AA_TASK", t.id, "TEACHER_CONFIRM")
        elif action == "REJECT":
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
            t.status, t.reject_reason = "REJECTED_BY_TEACHER", reason.strip()
            _audit(db, "AA_TASK", t.id, "TEACHER_REJECT", reason.strip())
        else:
            raise AppException("VALIDATION_ERROR", "无效操作")
        db.commit()
        db.refresh(t)
        return _task_row(t)


def submit_batch(batch_id, user) -> dict:
    """批次提交审核：要求所有任务已分配（无待分配/被教师退回）。"""
    with session() as db:
        from app.models import AaTeachingTask, AaTeachingTaskBatch
        b = db.get(AaTeachingTaskBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("任务批次不存在")
        if b.status not in ("DRAFT", "COLLEGE_CONFIRMED", "TEACHER_CONFIRMED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该批次当前状态不可提交")
        pending = db.scalar(select(func.count()).select_from(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id == b.id,
            AaTeachingTask.status.in_(["PENDING_ASSIGN", "REJECTED_BY_TEACHER"]),
            AaTeachingTask.is_deleted.is_(False))) or 0
        if pending:
            raise AppException("DATA_CONFLICT", f"仍有 {pending} 条任务未分配/被教师退回，不可提交")
        b.status = "APPROVED"
        _audit(db, "AA_TASK_BATCH", b.id, "APPROVED")
        db.commit()
        db.refresh(b)
        return {"batchId": str(b.id), "status": b.status}


# ═══════════ 查询 ═══════════

def list_batches(user, term_id=None, status=None, page=1, page_size=20):
    from app.models import AaTeachingTaskBatch
    with session() as db:
        conds = [AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.is_deleted.is_(False)]
        if term_id:
            conds.append(AaTeachingTaskBatch.term_id == int(term_id))
        if status:
            conds.append(AaTeachingTaskBatch.status == status)
        rows = db.scalars(select(AaTeachingTaskBatch).where(*conds).order_by(
            AaTeachingTaskBatch.id.desc())).all()
        out = [{"batchId": str(b.id), "batchName": b.batch_name, "termId": str(b.term_id),
                "status": b.status} for b in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def list_tasks(batch_id, user, status=None, page=1, page_size=50):
    from app.models import AaTeachingTask
    with session() as db:
        conds = [AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id == int(batch_id),
                 AaTeachingTask.is_deleted.is_(False)]
        if status:
            conds.append(AaTeachingTask.status == status)
        rows = db.scalars(select(AaTeachingTask).where(*conds).order_by(AaTeachingTask.id.desc())).all()
        out = [_task_row(t) for t in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total
