"""C-W2 Teacher Today read-only work cues.

Only consumes mature Exam invigilation facts and the canonical AA_GRADE_ENTRY UnifiedTodo.
Rendering Teacher Today must never create, refresh, or repair either authority.
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.affairs_security import _derive_keys
from app.services.db_service import _tid

_GRADE_TODO = "AA_GRADE_ENTRY"
_GRADE_ROUTE = "/pages/teacher/academic-affairs/grade-entry"


def _user_keys(user) -> set[str]:
    return {str(value).strip() for value in _derive_keys(user or {}) if str(value).strip()}


def _resolve_user_id(db, user) -> int | None:
    """Resolve the current real User.id by stable id/login facts; read only, no fallback creation."""
    from app.models import User

    raw = str((user or {}).get("userId") or "").strip()
    numeric = raw[3:] if raw.startswith("db-") else raw[2:] if raw.startswith("u_") else raw
    if numeric.isdigit():
        row = db.get(User, int(numeric))
        if row and not row.is_deleted and row.tenant_id == _tid() and row.status == "ACTIVE":
            return int(row.id)
    login = str((user or {}).get("loginName") or "").strip()
    if login:
        row = db.scalars(select(User).where(
            User.tenant_id == _tid(),
            User.login_name == login,
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
        )).first()
        if row:
            return int(row.id)
    return None


def today_invigilations(db, user, *, exam_date: str) -> list[dict]:
    from app.models import AaExamBatch, AaExamCourse, AaExamInvigilator, AaExamRoom

    keys = sorted(_user_keys(user))
    if not keys:
        return []
    invigilators = db.scalars(select(AaExamInvigilator).where(
        AaExamInvigilator.tenant_id == _tid(),
        AaExamInvigilator.teacher_key.in_(keys),
        AaExamInvigilator.is_deleted.is_(False),
    )).all()
    room_ids = sorted({int(row.exam_room_id) for row in invigilators if row.exam_room_id})
    if not room_ids:
        return []
    rooms = db.scalars(select(AaExamRoom).where(
        AaExamRoom.tenant_id == _tid(),
        AaExamRoom.id.in_(room_ids),
        AaExamRoom.status == "ACTIVE",
        AaExamRoom.is_deleted.is_(False),
    )).all()
    room_by_id = {int(row.id): row for row in rooms}
    course_ids = sorted({int(row.exam_course_id) for row in rooms if row.exam_course_id})
    courses = []
    if course_ids:
        courses = db.scalars(select(AaExamCourse).where(
            AaExamCourse.tenant_id == _tid(),
            AaExamCourse.id.in_(course_ids),
            AaExamCourse.exam_date == str(exam_date),
            AaExamCourse.status == "CONFIRMED",
            AaExamCourse.is_deleted.is_(False),
        )).all()
    course_by_id = {int(row.id): row for row in courses}
    batch_ids = sorted({int(row.batch_id) for row in courses if row.batch_id})
    batches = []
    if batch_ids:
        batches = db.scalars(select(AaExamBatch).where(
            AaExamBatch.tenant_id == _tid(),
            AaExamBatch.id.in_(batch_ids),
            AaExamBatch.status == "PUBLISHED",
            AaExamBatch.is_deleted.is_(False),
        )).all()
    published_batch_ids = {int(row.id) for row in batches}

    output = []
    for invigilator in invigilators:
        room = room_by_id.get(int(invigilator.exam_room_id or 0))
        course = course_by_id.get(int(room.exam_course_id or 0)) if room else None
        if not room or not course or int(course.batch_id or 0) not in published_batch_ids:
            continue
        output.append({
            "invigilatorId": str(invigilator.id),
            "examRoomId": str(room.id),
            "examCourseId": str(course.id),
            "courseName": course.course_name or "",
            "className": course.class_name or "",
            "examDate": course.exam_date or "",
            "startTime": course.start_time or "",
            "endTime": course.end_time or "",
            "classroom": room.classroom_text or "",
            "role": invigilator.role,
            "confirmStatus": invigilator.confirm_status,
        })
    output.sort(key=lambda row: (row["startTime"], row["examCourseId"], row["examRoomId"]))
    return output


def pending_grade_todos(db, user, *, term_id=None) -> list[dict]:
    from app.models import UnifiedTodo

    user_id = _resolve_user_id(db, user)
    if not user_id:
        return []
    rows = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(),
        UnifiedTodo.source_module == "academic-affairs",
        UnifiedTodo.source_biz_type == "AA_GRADE_TASK",
        UnifiedTodo.todo_type == _GRADE_TODO,
        UnifiedTodo.assignee_id == int(user_id),
        UnifiedTodo.status == "PENDING",
        UnifiedTodo.is_deleted.is_(False),
    ).order_by(UnifiedTodo.id)).all()
    task_ids = sorted({int(row.source_biz_id) for row in rows if row.source_biz_id})
    allowed_ids = set(task_ids)
    if term_id is not None and task_ids:
        from app.models import AaGradeTask
        allowed_ids = set(db.scalars(select(AaGradeTask.id).where(
            AaGradeTask.tenant_id == _tid(),
            AaGradeTask.id.in_(task_ids),
            AaGradeTask.term_id == int(term_id),
            AaGradeTask.is_deleted.is_(False),
        )).all())
    return [{
        "todoId": str(row.id),
        "todoType": _GRADE_TODO,
        "gradeTaskId": str(row.source_biz_id or ""),
        "title": row.title or "待录成绩",
        "route": f"{_GRADE_ROUTE}?id={int(row.source_biz_id)}" if row.source_biz_id else _GRADE_ROUTE,
        "pcRoute": f"/admin/academic-affairs/grade-entry?taskId={int(row.source_biz_id)}" if row.source_biz_id else "/admin/academic-affairs/grade-entry",
    } for row in rows if int(row.source_biz_id or 0) in allowed_ids]


def current_term_workbench(db, user, *, term_id=None, today_date="", term_start_date="", term_end_date="") -> dict:
    """One authoritative PC/miniapp work projection for the current teaching term."""
    from app.models import (
        AaClassroomBooking, AaGradeTask, AaLabBooking, AaScheduleChange,
        AaTeachingTask, AaTeachingTaskBatch, AaTextbookSelection,
    )
    from . import academic_affairs_teacher_relation_authority as teacher_authority
    from . import academic_affairs_grade_deadline_service as grade_deadline

    if not term_id:
        return {"actionItems": [], "waitingItems": [], "counts": {"actions": 0, "waiting": 0}, "termId": None}

    keys = sorted(_user_keys(user))
    relation = teacher_authority.relation_scope(db, user, term_id=int(term_id))
    formal_task_ids = sorted(int(value) for value in relation.get("taskIds") or [])
    batches = db.scalars(select(AaTeachingTaskBatch).where(
        AaTeachingTaskBatch.tenant_id == _tid(),
        AaTeachingTaskBatch.term_id == int(term_id),
        AaTeachingTaskBatch.is_deleted.is_(False),
    )).all()
    batch_ids = sorted(int(row.id) for row in batches)

    actions, waiting = [], []
    batch_by_id = {int(row.id): row for row in batches}

    # Teaching-task confirmation and its post-confirm waiting state live in one projection.
    # Assignment ownership is teacher_key based because confirmation happens before the
    # occurrence-week authority becomes executable.
    teacher_tasks = db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.batch_id.in_(batch_ids or [-1]),
        AaTeachingTask.teacher_key.in_(keys or ["__none__"]),
        AaTeachingTask.status.in_(["ASSIGNED", "TEACHER_CONFIRMED", "REJECTED_BY_TEACHER", "READY"]),
        AaTeachingTask.is_deleted.is_(False),
    ).order_by(AaTeachingTask.id)).all()
    formal_tasks = db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.id.in_(formal_task_ids or [-1]),
        AaTeachingTask.is_deleted.is_(False),
    )).all()
    formal_task_by_id = {int(row.id): row for row in formal_tasks}

    for row in teacher_tasks:
        if row.status == "ASSIGNED":
            actions.append({
                "kind": "TEACHING_TASK", "id": str(row.id),
                "title": f"确认《{row.course_name or '教学任务'}》",
                "note": " · ".join(value for value in (row.class_name, row.teaching_class_name, "学院已分配") if value),
                "action": "去确认", "primary": True,
                "path": f"/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId={row.id}",
            })
        elif row.status == "TEACHER_CONFIRMED":
            batch_status = str(getattr(batch_by_id.get(int(row.batch_id)), "status", "") or "").upper()
            note = {
                "COLLEGE_CONFIRMED": "学院已核对 · 等待教务终审",
                "RETURNED": "教务已退回学院 · 等待重新核对",
            }.get(batch_status, "本人已确认 · 等待学院核对")
            waiting.append({
                "kind": "TEACHING_TASK_WAITING", "id": str(row.id),
                "title": f"《{row.course_name or '教学任务'}》已确认",
                "note": note, "action": "查看进度",
                "path": f"/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId={row.id}",
            })
        elif row.status == "REJECTED_BY_TEACHER":
            waiting.append({
                "kind": "TEACHING_TASK_REJECTED_WAITING", "id": str(row.id),
                "title": f"《{row.course_name or '教学任务'}》已提出异议",
                "note": "本人已退回 · 等待学院调整并重新分配",
                "action": "查看进度",
                "path": f"/admin/academic-affairs/teaching-tasks/teacher-confirm?taskId={row.id}",
            })

    # Grade responsibility is projected directly from the current-term formal tasks.
    # UnifiedTodo remains a notification mechanism, not the sole source of UI truth.
    grade_rows = db.scalars(select(AaGradeTask).where(
        AaGradeTask.tenant_id == _tid(),
        AaGradeTask.term_id == int(term_id),
        AaGradeTask.teaching_task_id.in_(formal_task_ids or [-1]),
        AaGradeTask.is_deleted.is_(False),
    ).order_by(AaGradeTask.id.desc())).all()
    grade_by_teaching_task = {
        int(row.teaching_task_id): row
        for row in grade_rows if row.teaching_task_id
    }
    deadline_by_task = grade_deadline.deadline_projection_map(
        db, [(int(row.id), str(row.status or "")) for row in grade_rows]
    )
    for row in grade_rows:
        status = str(row.status or "").upper()
        deadline = deadline_by_task.get(int(row.id), {})
        overdue = deadline.get("isOverdue") is True
        item = {
            "kind": "GRADE", "id": str(row.id),
            "title": f"录入《{row.course_name or '课程'}》成绩",
            "path": f"/admin/academic-affairs/grade-entry?taskId={row.id}",
        }
        if status in {"NOT_STARTED", "INPUTTING", "RETURNED"}:
            if overdue:
                note = "已超过提交截止时间；可继续完善，提交需学院或教务延长截止时间"
                action = "继续完善"
            elif status == "RETURNED" and row.return_reason:
                note = f"已退回：{row.return_reason}"
                action = "继续修改"
            elif status == "INPUTTING":
                note = "录入中，请完成正式名单成绩"
                action = "继续录入"
            else:
                note = "成绩任务已建立，等待开始录入"
                action = "开始录入"
            item.update({
                "note": note,
                "action": action,
                "blocked": bool(overdue),
                "deadline": deadline.get("deadline"),
            })
            actions.append(item)
        elif status in {"SUBMITTED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW"}:
            item.update({
                "note": {
                    "SUBMITTED": "已提交 · 等待学院审核",
                    "COLLEGE_REVIEW": "学院审核中",
                    "ACADEMIC_REVIEW": "学院已通过 · 等待教务终审",
                }.get(status, "审核中"),
                "action": "查看进度",
            })
            waiting.append(item)

    for task_id in formal_task_ids:
        task = formal_task_by_id.get(int(task_id))
        if not task or str(task.status or "").upper() != "READY" or int(task_id) in grade_by_teaching_task:
            continue
        actions.append({
            "kind": "GRADE_SETUP", "id": str(task.id),
            "title": f"开始《{task.course_name or '课程'}》成绩录入",
            "note": f"{task.teaching_class_name or task.class_name or '正式教学班'} · 尚未建立成绩任务",
            "action": "开始录入",
            "path": f"/admin/academic-affairs/grade-entry?teachingTaskId={task.id}&action=create",
        })

    if formal_task_ids:
        selections = db.scalars(select(AaTextbookSelection).where(
            AaTextbookSelection.tenant_id == _tid(),
            AaTextbookSelection.task_id.in_(formal_task_ids),
            AaTextbookSelection.is_deleted.is_(False),
        ).order_by(AaTextbookSelection.id.desc())).all()
        selection_task_ids = {int(row.task_id) for row in selections if row.task_id}
        for row in selections:
            status = str(row.status or "").upper()
            if status not in {"DRAFT", "RETURNED", "SUBMITTED", "REVIEWING"}:
                continue
            item = {
                "kind": "TEXTBOOK", "id": str(row.id),
                "title": f"教材选用：{row.course_name or '课程'}",
                "note": "已退回，请修订后重提" if status == "RETURNED" else (
                    "草稿待提交" if status == "DRAFT" else "已提交，等待审核"
                ),
                "action": "去处理" if status in {"DRAFT", "RETURNED"} else "查看进度",
                "path": (
                    f"/admin/academic-affairs/textbooks?tab=selection&selectionId={row.id}&action=edit"
                    if status in {"DRAFT", "RETURNED"}
                    else f"/admin/academic-affairs/textbooks?tab=selection&selectionId={row.id}"
                ),
            }
            (actions if status in {"DRAFT", "RETURNED"} else waiting).append(item)

    if keys:
        changes = db.scalars(select(AaScheduleChange).where(
            AaScheduleChange.tenant_id == _tid(),
            AaScheduleChange.term_id == int(term_id),
            AaScheduleChange.teacher_key.in_(keys),
            AaScheduleChange.status.in_(["SUBMITTED", "COLLEGE_REVIEW", "ACADEMIC_REVIEW", "APPROVED"]),
            AaScheduleChange.is_deleted.is_(False),
        ).order_by(AaScheduleChange.id.desc())).all()
        schedule_change_status_text = {
            "SUBMITTED": "已提交 · 等待学院受理",
            "COLLEGE_REVIEW": "学院审核中",
            "ACADEMIC_REVIEW": "学院已通过 · 等待教务终审",
            "APPROVED": "终审通过 · 等待课表生效",
        }
        for row in changes:
            waiting.append({
                "kind": "SCHEDULE_CHANGE", "id": str(row.id),
                "title": f"调停课申请：{row.course_name or '课程'}",
                "note": schedule_change_status_text.get(
                    str(row.status or "").upper(), "审核状态待核对"
                ),
                "action": "查看进度",
                "path": f"/admin/academic-affairs/schedule-change?changeId={row.id}",
            })

        booking_filters = [today_date] if today_date else []
        for model, kind, path, text_field in (
            (AaClassroomBooking, "CLASSROOM_BOOKING", "/admin/academic-affairs/classroom-bookings", "classroom_text"),
            (AaLabBooking, "LAB_BOOKING", "/admin/academic-affairs/resources/lab-bookings", "lab_text"),
        ):
            conditions = [
                model.tenant_id == _tid(), model.applicant_key.in_(keys),
                model.status == "PENDING", model.is_deleted.is_(False),
            ]
            if term_start_date:
                conditions.append(model.booking_date >= str(term_start_date))
            if term_end_date:
                conditions.append(model.booking_date <= str(term_end_date))
            rows = db.scalars(select(model).where(*conditions).order_by(model.id.desc())).all()
            for row in rows:
                overdue_booking = bool(today_date and str(row.booking_date or "") < str(today_date))
                waiting.append({
                    "kind": kind, "id": str(row.id), "title": "教学资源预约待审核",
                    "note": (
                        "预约日期已过，仍待审核，请联系资源管理员"
                        if overdue_booking else
                        " · ".join(value for value in (
                            getattr(row, text_field, "") or "", row.booking_date,
                            f"第{row.slot_no}节" if row.slot_no else "",
                        ) if value)
                    ),
                    "action": "查看异常" if overdue_booking else "查看进度",
                    "blocked": overdue_booking,
                    "path": f"{path}?bookingId={row.id}&date={row.booking_date}",
                })

    actions.sort(key=lambda row: (0 if row.get("primary") else 1, row["kind"], int(row["id"]) if row["id"].isdigit() else row["id"]))
    waiting.sort(key=lambda row: (row["kind"], -(int(row["id"])) if row["id"].isdigit() else 0))
    counts = {
        "actions": len(actions), "waiting": len(waiting),
        "teachingTasks": sum(1 for row in actions if row["kind"] == "TEACHING_TASK"),
        "grades": sum(1 for row in actions if row["kind"] in {"GRADE", "GRADE_SETUP"}),
        "textbooks": sum(1 for row in actions + waiting if row["kind"] == "TEXTBOOK"),
        "scheduleChanges": sum(1 for row in waiting if row["kind"] == "SCHEDULE_CHANGE"),
        "bookings": sum(1 for row in waiting if row["kind"] in {"CLASSROOM_BOOKING", "LAB_BOOKING"}),
    }
    return {
        "termId": str(term_id), "actionItems": actions, "waitingItems": waiting,
        "counts": counts, "source": "CURRENT_TERM_FORMAL_TEACHER_FACTS",
    }


def teacher_work_cues(db, user, *, exam_date: str, term_id=None, term_start_date="", term_end_date="") -> dict:
    workbench = current_term_workbench(
        db, user, term_id=term_id, today_date=exam_date,
        term_start_date=term_start_date, term_end_date=term_end_date,
    )
    return {
        "invigilations": today_invigilations(db, user, exam_date=exam_date),
        "gradeTodos": pending_grade_todos(db, user, term_id=term_id),
        "workbench": workbench,
    }
