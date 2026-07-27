"""教学任务唯一公开 Service。

原状态机和通用 CRUD 保存在 ``academic_affairs_task_core_service``；本文件显式收口：
- 学期教学周和方案学期生成；
- 生成前培养方案治理门禁；
- 教学任务管理数据范围；
- 学院确认→教务终审状态机；
- 独立教学班与名单版本投影；
- 首屏工作台和范围内统计。

禁止 monkey patch、``sys.modules`` 别名和导入副作用。
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from sqlalchemy import func, select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.exceptions import AppException, not_found
from app.core.permissions import is_super_admin
from app.services.db_service import _tid, session

from . import academic_affairs_program_governance_service as program_governance
from . import academic_affairs_task_core_service as _core
from . import academic_affairs_task_generation_service as generation
from . import academic_affairs_teaching_class_service as teaching_class

_BLOCKING_STATUSES = {"PENDING_ASSIGN", "ASSIGNED", "REJECTED_BY_TEACHER"}
_READY_STATUSES = {"TEACHER_CONFIRMED", "READY"}
_SCHOOL_REVIEW_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}


def __getattr__(name):
    return getattr(_core, name)


@dataclass
class TaskManageScope:
    all: bool = False
    college_ids: set[int] = field(default_factory=set)
    class_ids: set[int] = field(default_factory=set)
    role: str = ""

    @property
    def blocked(self) -> bool:
        return not self.all and not self.college_ids and not self.class_ids


def _scope(user, db) -> TaskManageScope:
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if is_super_admin(user) or role in _SCHOOL_REVIEW_ROLES:
        return TaskManageScope(all=True, role=role)
    context = build_affairs_context(user, db)
    if str(context.scope_type or "").upper() == "TENANT_ALL":
        return TaskManageScope(all=True, role=role)
    allowed_classes = {int(value) for value in (context.allowed_class_ids(db) or set())}
    scope = TaskManageScope(
        all=False,
        college_ids={int(value) for value in (context.college_ids or set())},
        class_ids=allowed_classes,
        role=role,
    )
    if scope.blocked:
        raise no_data_scope("当前身份未配置教学任务管理的学院或班级范围")
    return scope


def _visible_task_conditions(scope: TaskManageScope, Task):
    if scope.all:
        return []
    if scope.class_ids:
        return [Task.class_id.in_(sorted(scope.class_ids))]
    return [Task.id == -1]


def _visible_batch_ids(db, scope: TaskManageScope) -> set[int] | None:
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    if scope.all:
        return None
    ids = {
        int(value) for (value,) in db.query(AaTeachingTask.batch_id).filter(
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.is_deleted.is_(False),
            *_visible_task_conditions(scope, AaTeachingTask),
        ).all() if value
    }
    if scope.college_ids:
        ids.update(
            int(value) for (value,) in db.query(AaTeachingTaskBatch.id).filter(
                AaTeachingTaskBatch.tenant_id == _tid(),
                AaTeachingTaskBatch.college_id.in_(sorted(scope.college_ids)),
                AaTeachingTaskBatch.is_deleted.is_(False),
            ).all()
        )
    return ids


def _ensure_batch_visible(db, batch, scope: TaskManageScope) -> None:
    visible = _visible_batch_ids(db, scope)
    if visible is not None and int(batch.id) not in visible:
        raise no_data_scope("该教学任务批次不在当前数据范围内")


def _ensure_task_visible(db, task_id: int, user):
    from app.models import AaTeachingTask

    task = db.query(AaTeachingTask).filter(
        AaTeachingTask.id == int(task_id),
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.is_deleted.is_(False),
    ).first()
    if not task:
        raise not_found("教学任务不存在")
    scope = _scope(user, db)
    if not scope.all and (not task.class_id or int(task.class_id) not in scope.class_ids):
        raise no_data_scope("该教学任务不在当前数据范围内")
    return task, scope


def _pending_count(db, batch_id: int) -> int:
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
    for code, status, route, template in (
        ("UNASSIGNED", "PENDING_ASSIGN", "/admin/academic-affairs/teaching-tasks/assign", "仍有 {count} 条任务未分配教师"),
        ("WAIT_TEACHER", "ASSIGNED", "/admin/academic-affairs/teaching-tasks/teacher-confirm", "仍有 {count} 条任务等待教师本人确认"),
        ("TEACHER_REJECTED", "REJECTED_BY_TEACHER", "/admin/academic-affairs/teaching-tasks/assign", "仍有 {count} 条任务被教师退回"),
    ):
        count = int(by_status.get(status, 0))
        if count:
            blockers.append({
                "code": code, "count": count,
                "message": template.format(count=count), "route": route,
            })
    missing_teacher_key = sum(
        1 for task in tasks
        if str(task.status or "").upper() in {"ASSIGNED", "TEACHER_CONFIRMED", "READY"}
        and not str(task.teacher_key or "").strip()
    )
    if missing_teacher_key:
        blockers.append({
            "code": "TEACHER_KEY_MISSING", "count": missing_teacher_key,
            "message": f"有 {missing_teacher_key} 条任务缺少稳定教师工号",
            "route": "/admin/academic-affairs/teaching-tasks/assign",
        })
    total = len(tasks)
    assigned = sum(by_status.get(status, 0) for status in ("ASSIGNED", "TEACHER_CONFIRMED", "READY"))
    confirmed = sum(by_status.get(status, 0) for status in _READY_STATUSES)
    return {
        "taskTotal": total, "taskByStatus": dict(by_status),
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


def _generation_programs(db, user, college_id=None):
    from app.models import AaProgram, Major

    scope = _scope(user, db)
    rows = db.query(AaProgram).filter(
        AaProgram.tenant_id == _tid(),
        AaProgram.status == "ENABLED",
        AaProgram.is_deleted.is_(False),
    ).all()
    if college_id:
        major_ids = {
            int(value) for (value,) in db.query(Major.id).filter(
                Major.tenant_id == _tid(), Major.college_id == int(college_id),
                Major.is_deleted.is_(False),
            ).all()
        }
        rows = [row for row in rows if row.major_id and int(row.major_id) in major_ids]
    elif not scope.all:
        allowed_major_ids = program_governance._allowed_major_ids(db, scope)
        rows = [row for row in rows if row.major_id and int(row.major_id) in allowed_major_ids]
    return rows


def _generation_precheck(db, user, college_id=None) -> dict:
    programs = _generation_programs(db, user, college_id)
    if not programs:
        raise AppException(
            "PROGRAM_NOT_READY", "当前学院或数据范围没有已启用培养方案，不能生成教学任务",
            http_status=409,
        )
    blocked, warning_count = [], 0
    for program in programs:
        result = program_governance.validate_program_db(db, int(program.id))
        blockers = [item for item in result["issues"] if item["level"] == "BLOCKER"]
        warning_count += int(result["counts"]["warning"])
        if blockers:
            blocked.append({
                "programId": str(program.id), "programName": program.program_name,
                "blockerCount": len(blockers),
                "messages": [item["message"] for item in blockers[:3]],
            })
    if blocked:
        preview = "；".join(
            f"{item['programName']}：{'、'.join(item['messages'])}" for item in blocked[:3]
        )
        suffix = f"；另有 {len(blocked) - 3} 个方案" if len(blocked) > 3 else ""
        raise AppException(
            "PROGRAM_VALIDATION_BLOCKED",
            f"有 {len(blocked)} 个已启用方案存在阻断项，不能生成教学任务：{preview}{suffix}",
            http_status=409,
        )
    return {"programCount": len(programs), "warningCount": warning_count}


def _sync_task(task_id: int) -> dict:
    with session() as db:
        try:
            row = teaching_class.ensure_teaching_class_for_task(db, int(task_id))
            db.commit()
            return {
                "ok": True, "teachingTaskId": str(task_id),
                "teachingClassId": str(row.id),
                "rosterVersionNo": int(row.current_roster_version_no or 0),
            }
        except Exception as exc:
            db.rollback()
            return {"ok": False, "teachingTaskId": str(task_id), "error": str(exc)}


def _refresh_administrative_roster(task_id: int, reason: str) -> dict:
    with session() as db:
        try:
            from app.models import AaSelectionCourse, AaTeachingTask

            task = db.query(AaTeachingTask).filter(
                AaTeachingTask.id == int(task_id),
                AaTeachingTask.tenant_id == _tid(),
                AaTeachingTask.is_deleted.is_(False),
            ).first()
            if not task:
                raise ValueError("教学任务不存在")
            selection_exists = db.query(AaSelectionCourse.id).filter(
                AaSelectionCourse.tenant_id == _tid(),
                AaSelectionCourse.teaching_task_id == int(task_id),
                AaSelectionCourse.is_deleted.is_(False),
            ).first() is not None
            if selection_exists:
                raise ValueError("教学任务已进入选课流程，合拆班名单必须回选课管理重新锁定")
            klass = teaching_class.ensure_teaching_class_for_task(
                db, int(task_id), initialize_admin_roster=False,
            )
            student_ids = teaching_class._administrative_roster(db, task)
            if not student_ids:
                raise ValueError("教学任务当前行政班范围没有有效学生，不能形成正式名单版本")
            version, created = teaching_class.create_roster_version(
                db, klass, student_ids, source_type="ADMIN_CLASS",
                source_id=None if task.is_merged else task.class_id, reason=reason,
            )
            db.commit()
            return {
                "ok": True, "teachingTaskId": str(task_id),
                "teachingClassId": str(klass.id), "rosterVersionId": str(version.id),
                "rosterVersionNo": int(version.version_no),
                "memberCount": int(version.member_count), "created": bool(created),
            }
        except Exception as exc:
            db.rollback()
            return {"ok": False, "teachingTaskId": str(task_id), "error": str(exc)}


def generate_batch(body, user) -> dict:
    college_id = int(body.collegeId) if getattr(body, "collegeId", None) else None
    with session() as db:
        precheck = _generation_precheck(db, user, college_id)
    result = generation.generate_batch(body, user)
    batch_id = int(result["batchId"])
    with session() as db:
        projection = teaching_class.sync_batch_teaching_classes(db, batch_id)
        db.commit()
    result["programValidation"] = {
        "programCount": precheck["programCount"],
        "warningCount": precheck["warningCount"],
        "conclusion": "已启用方案结构与绑定校验通过",
    }
    result["teachingClassProjection"] = projection
    return result


def assign_teacher(task_id, user, body) -> dict:
    with session() as db:
        _ensure_task_visible(db, int(task_id), user)
    result = _core.assign_teacher(task_id, user, body)
    result["teachingClassProjection"] = _sync_task(int(task_id))
    return result


def adjust_task(task_id, user, body) -> dict:
    with session() as db:
        _ensure_task_visible(db, int(task_id), user)
    result = _core.adjust_task(task_id, user, body)
    result["teachingClassProjection"] = _sync_task(int(task_id))
    return result


def merge_tasks(body, user) -> dict:
    task_ids = sorted({int(value) for value in (getattr(body, "taskIds", None) or []) if str(value).isdigit()})
    with session() as db:
        for task_id in task_ids:
            _ensure_task_visible(db, task_id, user)
    result = _core.merge_tasks(body, user)
    survivor_id = int(result.get("taskId") or result.get("id") or 0) or None
    projections = [_sync_task(task_id) for task_id in task_ids]
    if survivor_id and survivor_id not in task_ids:
        projections.append(_sync_task(survivor_id))
    result["teachingClassProjections"] = projections
    result["rosterProjection"] = (
        _refresh_administrative_roster(survivor_id, "教学任务合班后重建行政班成员并集")
        if survivor_id else {"ok": False, "error": "合班结果缺少存续教学任务ID"}
    )
    return result


def split_task(task_id, user) -> dict:
    member_ids = []
    with session() as db:
        task, _scope_value = _ensure_task_visible(db, int(task_id), user)
        if task.merge_snapshot_json:
            try:
                snapshot = json.loads(task.merge_snapshot_json)
                member_ids = [int(value) for value in snapshot.get("memberTaskIds", []) if str(value).isdigit()]
            except (TypeError, ValueError):
                member_ids = []
    result = _core.split_task(task_id, user)
    restored_ids = list(dict.fromkeys([int(task_id), *member_ids]))
    result["teachingClassProjections"] = [_sync_task(value) for value in restored_ids]
    result["rosterProjections"] = [
        _refresh_administrative_roster(value, "教学任务拆班后恢复行政班正式名单")
        for value in restored_ids
    ]
    return result


def college_confirm_batch(batch_id, user) -> dict:
    from app.models import AaTeachingTaskBatch
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    with session() as db:
        batch = db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.id == int(batch_id),
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("任务批次不存在")
        guard_term_writable(db, batch.term_id)
        scope = _scope(user, db)
        _ensure_batch_visible(db, batch, scope)
        if batch.status not in {"DRAFT", "RETURNED"}:
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅草稿或教务退回批次可提交学院确认")
        pending = _pending_count(db, batch.id)
        if pending:
            raise AppException("DATA_CONFLICT", f"仍有 {pending} 条任务未分配、待教师确认或被教师退回，不可提交")
        batch.status = "COLLEGE_CONFIRMED"
        _core._audit(db, "AA_TASK_BATCH", batch.id, "COLLEGE_CONFIRM")
        db.commit()
        db.refresh(batch)
        return {"batchId": str(batch.id), "status": batch.status, "nextAction": "ACADEMIC_REVIEW"}


def submit_batch(batch_id, user) -> dict:
    """旧入口兼容：不再跳过学院确认和教务终审。"""
    return college_confirm_batch(batch_id, user)


def review_batch(batch_id, user, action, reason="") -> dict:
    from app.models import AaTeachingTask, AaTeachingTaskBatch
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable

    action = str(action or "").upper()
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if not (is_super_admin(user) or role in _SCHOOL_REVIEW_ROLES):
        raise no_data_scope("仅学校教务管理员可执行教学任务终审")
    with session() as db:
        batch = db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.id == int(batch_id),
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).with_for_update().first()
        if not batch:
            raise not_found("任务批次不存在")
        guard_term_writable(db, batch.term_id)
        if batch.status != "COLLEGE_CONFIRMED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该批次须先完成学院核对确认")
        if action == "APPROVE":
            pending = _pending_count(db, batch.id)
            if pending:
                raise AppException("DATA_CONFLICT", f"仍有 {pending} 条任务未完成教师确认，不可终审")
            rows = db.scalars(select(AaTeachingTask).where(
                AaTeachingTask.tenant_id == _tid(),
                AaTeachingTask.batch_id == batch.id,
                AaTeachingTask.status == "TEACHER_CONFIRMED",
                AaTeachingTask.is_deleted.is_(False),
            )).all()
            batch.status = "APPROVED"
            for task in rows:
                task.status = "READY"
            _core._audit(db, "AA_TASK_BATCH", batch.id, "ACADEMIC_APPROVE", f"READY x{len(rows)}")
        elif action in {"RETURN", "REJECT"}:
            reason = str(reason or "").strip()
            if len(reason) < 5:
                raise AppException("VALIDATION_ERROR", "退回原因必填且不少于5字")
            batch.status = "RETURNED"
            _core._audit(db, "AA_TASK_BATCH", batch.id, "ACADEMIC_RETURN", reason)
        else:
            raise AppException("VALIDATION_ERROR", "无效操作")
        db.commit()
        db.refresh(batch)
        return {"batchId": str(batch.id), "status": batch.status}


def list_batches(user, term_id=None, status=None, page=1, page_size=20):
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    with session() as db:
        scope = _scope(user, db)
        conditions = [
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ]
        if term_id:
            conditions.append(AaTeachingTaskBatch.term_id == int(term_id))
        if status:
            conditions.append(AaTeachingTaskBatch.status == status)
        visible = _visible_batch_ids(db, scope)
        if visible is not None:
            conditions.append(AaTeachingTaskBatch.id.in_(sorted(visible) or [-1]))
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
                "batchId": str(batch.id), "batchName": batch.batch_name,
                "termId": str(batch.term_id), "collegeId": str(batch.college_id or ""),
                "status": batch.status, **summary,
                "nextAction": _batch_next_action(batch, summary),
            })
        total = len(output)
        start = (max(1, int(page)) - 1) * int(page_size)
        return output[start:start + int(page_size)], total


def list_tasks(batch_id, user, status=None, page=1, page_size=50):
    from app.models import AaTeachingTask, AaTeachingTaskBatch

    with session() as db:
        scope = _scope(user, db)
        batch = db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.id == int(batch_id),
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("任务批次不存在")
        _ensure_batch_visible(db, batch, scope)
        conditions = [
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.batch_id == int(batch_id),
            AaTeachingTask.is_deleted.is_(False),
            *_visible_task_conditions(scope, AaTeachingTask),
        ]
        if status:
            conditions.append(AaTeachingTask.status == status)
        rows = db.scalars(select(AaTeachingTask).where(*conditions).order_by(
            AaTeachingTask.course_code, AaTeachingTask.teaching_class_code, AaTeachingTask.id,
        )).all()
        output = [_core._task_row(task) for task in rows]
        total = len(output)
        start = (max(1, int(page)) - 1) * int(page_size)
        return output[start:start + int(page_size)], total


def list_all_tasks(user, batch_id=None, course_id=None, status=None, mergeable=False, mine=False,
                   page=1, page_size=50):
    from app.models import AaTeachingTask

    with session() as db:
        conditions = [AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False)]
        if batch_id:
            conditions.append(AaTeachingTask.batch_id == int(batch_id))
        if course_id:
            conditions.append(AaTeachingTask.course_id == int(course_id))
        if status:
            conditions.append(AaTeachingTask.status == status)
        if mergeable:
            conditions.extend([
                AaTeachingTask.status.in_(_core._PRE_CONFIRM_STATUSES),
                AaTeachingTask.is_merged.is_(False),
                AaTeachingTask.merged_into_id.is_(None),
            ])
        if mine:
            keys = _core._user_keys(user)
            conditions.append(AaTeachingTask.teacher_key.in_(sorted(keys) or ["__none__"]))
        else:
            scope = _scope(user, db)
            conditions.extend(_visible_task_conditions(scope, AaTeachingTask))
        rows = db.scalars(select(AaTeachingTask).where(*conditions).order_by(
            AaTeachingTask.batch_id.desc(), AaTeachingTask.course_id, AaTeachingTask.id,
        )).all()
        output = [_core._task_row(task) for task in rows]
        total = len(output)
        start = (max(1, int(page)) - 1) * int(page_size)
        return output[start:start + int(page_size)], total


def get_batch_workbench(batch_id, user) -> dict:
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm

    with session() as db:
        scope = _scope(user, db)
        batch = db.query(AaTeachingTaskBatch).filter(
            AaTeachingTaskBatch.id == int(batch_id),
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("任务批次不存在")
        _ensure_batch_visible(db, batch, scope)
        tasks = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.batch_id == batch.id,
            AaTeachingTask.is_deleted.is_(False),
            *_visible_task_conditions(scope, AaTeachingTask),
        )).all()
        summary = _summary(tasks)
        term = db.get(AaTerm, int(batch.term_id)) if batch.term_id else None
        role = str((user or {}).get("currentRoleCode") or "").upper()
        school_review = is_super_admin(user) or role in _SCHOOL_REVIEW_ROLES
        college_manage = scope.all or bool(scope.college_ids)
        return {
            "batchId": str(batch.id), "batchName": batch.batch_name,
            "termId": str(batch.term_id),
            "termLabel": f"{term.year_code} 第{term.term_no}学期" if term else f"学期{batch.term_id}",
            "collegeId": str(batch.college_id or ""), "status": batch.status,
            "generatedAt": _core._iso(batch.generate_at), **summary,
            "nextAction": _batch_next_action(batch, summary),
            "actions": {
                "canAssign": college_manage and batch.status in {"DRAFT", "RETURNED"},
                "canCollegeConfirm": college_manage and batch.status in {"DRAFT", "RETURNED"} and summary["canAdvance"],
                "canAcademicReview": school_review and batch.status == "COLLEGE_CONFIRMED" and summary["canAdvance"],
                "canEditComposition": batch.status in {"DRAFT", "RETURNED"},
            },
        }


def get_task_stats(user, term_id=None) -> dict:
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm

    with session() as db:
        scope = _scope(user, db)
        batch_conditions = [
            AaTeachingTaskBatch.tenant_id == _tid(),
            AaTeachingTaskBatch.is_deleted.is_(False),
        ]
        if term_id:
            batch_conditions.append(AaTeachingTaskBatch.term_id == int(term_id))
        visible = _visible_batch_ids(db, scope)
        if visible is not None:
            batch_conditions.append(AaTeachingTaskBatch.id.in_(sorted(visible) or [-1]))
        batches = db.scalars(select(AaTeachingTaskBatch).where(*batch_conditions)).all()
        batch_ids = [int(batch.id) for batch in batches]
        tasks = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.batch_id.in_(batch_ids or [-1]),
            AaTeachingTask.status != "MERGED",
            AaTeachingTask.is_deleted.is_(False),
            *_visible_task_conditions(scope, AaTeachingTask),
        )).all()
        batch_by_status = Counter(str(batch.status or "UNKNOWN") for batch in batches)
        task_by_status = Counter(str(task.status or "UNKNOWN") for task in tasks)
        assigned = sum(1 for task in tasks if task.status in _core._TERMINAL_ASSIGN_STATUSES)
        confirmed = sum(1 for task in tasks if task.status in _core._DONE_TASK_STATUSES)
        rejected = sum(1 for task in tasks if task.status == "REJECTED_BY_TEACHER")

        def rate(numerator, denominator):
            return round(numerator * 100.0 / denominator, 1) if denominator else 0.0

        by_term = {}
        batch_index = {int(batch.id): batch for batch in batches}
        for batch in batches:
            by_term.setdefault(int(batch.term_id), {
                "termId": str(batch.term_id), "batchCount": 0,
                "taskTotal": 0, "confirmedTotal": 0,
            })["batchCount"] += 1
        for task in tasks:
            batch = batch_index.get(int(task.batch_id))
            if not batch:
                continue
            item = by_term[int(batch.term_id)]
            item["taskTotal"] += 1
            if task.status in _core._DONE_TASK_STATUSES:
                item["confirmedTotal"] += 1
        labels = {
            int(row.id): f"{row.year_code} 第{row.term_no}学期"
            for row in db.scalars(select(AaTerm).where(
                AaTerm.tenant_id == _tid(), AaTerm.id.in_(list(by_term.keys()) or [-1]),
            )).all()
        }
        by_term_items = []
        for term_value, item in by_term.items():
            item["termLabel"] = labels.get(term_value, f"学期{term_value}")
            item["confirmRate"] = rate(item["confirmedTotal"], item["taskTotal"])
            by_term_items.append(item)
        by_term_items.sort(key=lambda item: item["termId"], reverse=True)
        return {
            "batchTotal": len(batches), "batchByStatus": dict(batch_by_status),
            "taskTotal": len(tasks), "taskByStatus": dict(task_by_status),
            "mergedCount": 0,
            "assignRate": {"numerator": assigned, "denominator": len(tasks), "rate": rate(assigned, len(tasks))},
            "teacherConfirmRate": {
                "numerator": confirmed, "denominator": assigned + rejected,
                "rate": rate(confirmed, assigned + rejected),
            },
            "byTerm": by_term_items,
        }
