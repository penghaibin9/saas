"""教学任务最终工作台兼容层。

在教学周/应开课程facade之上收口：
- ``ASSIGNED``（待教师确认）与未分配、教师退回一样阻断批次确认；
- 历史 ``submit_batch`` 不再单步直达APPROVED，统一进入COLLEGE_CONFIRMED后等待教务终审；
- 批次列表、批次明细和工作台按学院/班级范围fail-closed；
- 返回首屏指标、阻断项和下一步动作，供PC管理页直接呈现业务结论。
"""
from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import func, select

from app.core.affairs_security import no_data_scope
from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid

from . import academic_affairs_task_facade as _base

_legacy = _base._legacy
_BLOCKING_STATUSES = {"PENDING_ASSIGN", "ASSIGNED", "REJECTED_BY_TEACHER"}
_READY_STATUSES = {"TEACHER_CONFIRMED", "READY"}


def __getattr__(name):
    return getattr(_base, name)


def _scope(user, db):
    from app.modules.academic_affairs.services import academic_affairs_stats_service as stats

    scope = stats._resolve_scope(user, db)
    if getattr(scope, "blocked", False):
        raise no_data_scope("当前身份未配置可查看的学院或班级范围")
    return scope


def _visible_task_conditions(scope, Task):
    if scope.all:
        return []
    class_ids = set(getattr(scope, "class_ids", set()) or set())
    if not class_ids:
        return [Task.id == -1]
    return [Task.class_id.in_(sorted(class_ids))]


def _visible_batch_ids(db, scope) -> set[int] | None:
    from app.models import AaTeachingTask

    if scope.all:
        return None
    ids = set(db.scalars(select(AaTeachingTask.batch_id).where(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.is_deleted.is_(False),
        *_visible_task_conditions(scope, AaTeachingTask),
    )).all())
    return {int(value) for value in ids if value}


def _pending_count(db, batch_id) -> int:
    """批次确认阻断：未分配、待教师确认、教师退回都必须先处理。"""
    from app.models import AaTeachingTask

    return db.scalar(select(func.count()).select_from(AaTeachingTask).where(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.batch_id == int(batch_id),
        AaTeachingTask.status.in_(sorted(_BLOCKING_STATUSES)),
        AaTeachingTask.is_deleted.is_(False),
    )) or 0


def _summary(tasks) -> dict:
    tasks = [task for task in tasks if str(task.status or "").upper() != "MERGED"]
    by_status = Counter(str(task.status or "UNKNOWN").upper() for task in tasks)
    blockers = []
    if by_status.get("PENDING_ASSIGN"):
        blockers.append({
            "code": "UNASSIGNED",
            "count": by_status["PENDING_ASSIGN"],
            "message": f"仍有 {by_status['PENDING_ASSIGN']} 条任务未分配教师",
            "route": "/admin/academic-affairs/teaching-tasks/assign",
        })
    if by_status.get("ASSIGNED"):
        blockers.append({
            "code": "WAIT_TEACHER",
            "count": by_status["ASSIGNED"],
            "message": f"仍有 {by_status['ASSIGNED']} 条任务等待教师本人确认",
            "route": "/admin/academic-affairs/teaching-tasks/teacher-confirm",
        })
    if by_status.get("REJECTED_BY_TEACHER"):
        blockers.append({
            "code": "TEACHER_REJECTED",
            "count": by_status["REJECTED_BY_TEACHER"],
            "message": f"仍有 {by_status['REJECTED_BY_TEACHER']} 条任务被教师退回",
            "route": "/admin/academic-affairs/teaching-tasks/assign",
        })
    missing_teacher_key = sum(
        1 for task in tasks
        if str(task.status or "").upper() in {"ASSIGNED", "TEACHER_CONFIRMED", "READY"}
        and not str(task.teacher_key or "").strip()
    )
    if missing_teacher_key:
        blockers.append({
            "code": "TEACHER_KEY_MISSING",
            "count": missing_teacher_key,
            "message": f"有 {missing_teacher_key} 条任务缺少稳定教师工号",
            "route": "/admin/academic-affairs/teaching-tasks/assign",
        })
    total = len(tasks)
    assigned = sum(
        by_status.get(status, 0)
        for status in ("ASSIGNED", "TEACHER_CONFIRMED", "READY")
    )
    confirmed = sum(by_status.get(status, 0) for status in _READY_STATUSES)
    return {
        "taskTotal": total,
        "taskByStatus": dict(by_status),
        "unassignedCount": by_status.get("PENDING_ASSIGN", 0),
        "waitingTeacherCount": by_status.get("ASSIGNED", 0),
        "teacherRejectedCount": by_status.get("REJECTED_BY_TEACHER", 0),
        "teacherConfirmedCount": by_status.get("TEACHER_CONFIRMED", 0),
        "readyCount": by_status.get("READY", 0),
        "assignedRate": round(assigned * 100.0 / total, 1) if total else 0.0,
        "teacherConfirmRate": round(confirmed * 100.0 / assigned, 1) if assigned else 0.0,
        "blockers": blockers,
        "blockerCount": sum(int(item["count"]) for item in blockers),
        "canAdvance": total > 0 and not blockers,
    }


def _batch_next_action(batch, summary) -> dict:
    status = str(batch.status or "").upper()
    if summary["blockers"]:
        first = summary["blockers"][0]
        return {"code": first["code"], "label": first["message"], "route": first["route"]}
    if status in {"DRAFT", "RETURNED"}:
        return {"code": "COLLEGE_CONFIRM", "label": "学院核对确认后提交教务终审", "route": ""}
    if status == "COLLEGE_CONFIRMED":
        return {"code": "ACADEMIC_REVIEW", "label": "等待教务终审", "route": "/admin/academic-affairs/teaching-tasks/confirm"}
    if status == "APPROVED":
        return {"code": "READY", "label": "任务已终审，可进入排课", "route": "/admin/academic-affairs/schedule"}
    if status == "ARCHIVED":
        return {"code": "ARCHIVED", "label": "批次已归档，只读查看", "route": ""}
    return {"code": "CHECK_STATUS", "label": f"核对批次状态：{status or 'UNKNOWN'}", "route": ""}


def submit_batch(batch_id, user) -> dict:
    """兼容旧提交入口：统一走学院确认，不再跳过教务终审。"""
    from app.models import AaTeachingTaskBatch
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    with _legacy.session() as db:
        batch = db.get(AaTeachingTaskBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("任务批次不存在")
        guard_term_writable(db, batch.term_id)
        scope = _scope(user, db)
        visible_ids = _visible_batch_ids(db, scope)
        if visible_ids is not None and int(batch.id) not in visible_ids:
            raise no_data_scope("该教学任务批次不在您的数据范围内")
        if batch.status not in ("DRAFT", "RETURNED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅草稿或教务退回批次可提交学院确认")
        pending = _pending_count(db, batch.id)
        if pending:
            raise AppException("DATA_CONFLICT", f"仍有 {pending} 条任务未分配、待教师确认或被教师退回，不可提交")
        batch.status = "COLLEGE_CONFIRMED"
        _legacy._audit(db, "AA_TASK_BATCH", batch.id, "COLLEGE_CONFIRM", "兼容提交入口统一进入教务终审")
        db.commit()
        db.refresh(batch)
        return {"batchId": str(batch.id), "status": batch.status, "nextAction": "ACADEMIC_REVIEW"}


def list_batches(user, term_id=None, status=None, page=1, page_size=20):
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    with _legacy.session() as db:
        scope = _scope(user, db)
        conditions = [
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ]
        if term_id:
            conditions.append(AaTeachingTaskBatch.term_id == int(term_id))
        if status:
            conditions.append(AaTeachingTaskBatch.status == status)
        visible_ids = _visible_batch_ids(db, scope)
        if visible_ids is not None:
            conditions.append(AaTeachingTaskBatch.id.in_(sorted(visible_ids) or [-1]))
        batches = db.scalars(select(AaTeachingTaskBatch).where(*conditions).order_by(
            AaTeachingTaskBatch.id.desc(),
        )).all()
        batch_ids = [int(batch.id) for batch in batches]
        tasks = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.batch_id.in_(batch_ids or [-1]),
            AaTeachingTask.is_deleted.is_(False),
            *_visible_task_conditions(scope, AaTeachingTask),
        )).all()
        grouped = defaultdict(list)
        for task in tasks:
            grouped[int(task.batch_id)].append(task)
        output = []
        for batch in batches:
            summary = _summary(grouped.get(int(batch.id), []))
            output.append({
                "batchId": str(batch.id),
                "batchName": batch.batch_name,
                "termId": str(batch.term_id),
                "collegeId": str(batch.college_id or ""),
                "status": batch.status,
                **summary,
                "nextAction": _batch_next_action(batch, summary),
            })
        total = len(output)
        start = (max(1, int(page)) - 1) * int(page_size)
        return output[start:start + int(page_size)], total


def list_tasks(batch_id, user, status=None, page=1, page_size=50):
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    with _legacy.session() as db:
        scope = _scope(user, db)
        batch = db.get(AaTeachingTaskBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("任务批次不存在")
        visible_ids = _visible_batch_ids(db, scope)
        if visible_ids is not None and int(batch.id) not in visible_ids:
            raise no_data_scope("该教学任务批次不在您的数据范围内")
        conditions = [
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.batch_id == int(batch_id),
            AaTeachingTask.is_deleted.is_(False),
            *_visible_task_conditions(scope, AaTeachingTask),
        ]
        if status:
            conditions.append(AaTeachingTask.status == status)
        rows = db.scalars(select(AaTeachingTask).where(*conditions).order_by(
            AaTeachingTask.course_code,
            AaTeachingTask.teaching_class_code,
            AaTeachingTask.id,
        )).all()
        output = [_legacy._task_row(task) for task in rows]
        total = len(output)
        start = (max(1, int(page)) - 1) * int(page_size)
        return output[start:start + int(page_size)], total


def get_batch_workbench(batch_id, user) -> dict:
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm

    with _legacy.session() as db:
        scope = _scope(user, db)
        batch = db.get(AaTeachingTaskBatch, int(batch_id))
        if not batch or batch.is_deleted or batch.tenant_id != _tid():
            raise not_found("任务批次不存在")
        visible_ids = _visible_batch_ids(db, scope)
        if visible_ids is not None and int(batch.id) not in visible_ids:
            raise no_data_scope("该教学任务批次不在您的数据范围内")
        tasks = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.batch_id == batch.id,
            AaTeachingTask.is_deleted.is_(False),
            *_visible_task_conditions(scope, AaTeachingTask),
        )).all()
        summary = _summary(tasks)
        term = db.get(AaTerm, int(batch.term_id)) if batch.term_id else None
        role = str((user or {}).get("currentRoleCode") or "").upper()
        school_review = role in {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}
        college_manage = scope.all or bool(getattr(scope, "college_ids", set()))
        return {
            "batchId": str(batch.id),
            "batchName": batch.batch_name,
            "termId": str(batch.term_id),
            "termLabel": (
                f"{term.year_code} 第{term.term_no}学期" if term else f"学期{batch.term_id}"
            ),
            "collegeId": str(batch.college_id or ""),
            "status": batch.status,
            "generatedAt": _legacy._iso(batch.generate_at),
            **summary,
            "nextAction": _batch_next_action(batch, summary),
            "actions": {
                "canAssign": college_manage and batch.status in {"DRAFT", "RETURNED"},
                "canCollegeConfirm": college_manage and batch.status in {"DRAFT", "RETURNED"} and summary["canAdvance"],
                "canAcademicReview": school_review and batch.status == "COLLEGE_CONFIRMED" and summary["canAdvance"],
                "canEditComposition": batch.status in {"DRAFT", "RETURNED"},
            },
        }


# 原状态机内部读取_pending_count，显式替换后所有确认入口都把ASSIGNED纳入阻断。
_legacy._pending_count = _pending_count
_legacy.submit_batch = submit_batch
_legacy.list_batches = list_batches
_legacy.list_tasks = list_tasks
