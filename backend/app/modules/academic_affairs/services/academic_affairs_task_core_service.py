"""13B-P3 教学任务（批次生成→分配教师→教师确认→提交审核 ACAD_TASK_CONFIRM）。

按已发布培养方案(ENABLED+ACTIVE绑定)生成应开课程的教学任务(课程×教学班)，generate 幂等。
含商业软件标配：教学班(可合班)、周学时/起止周、多环节确认。教师确认/退回，批次两级确认后提交审核。

Tier1 R1（续工）新增：
- 合班/拆班（merge_tasks/split_task）：同批次同课程多条任务合并为一条教学班任务，可逆（教师确认前）。
- 批次两级确认链（college_confirm_batch→review_batch）：学院核对确认→教务终审通过(READY)/退回；
  与既有 submit_batch（DRAFT→APPROVED 单步直提）并存，不改既有契约（TT1/TT2/TT4 测试基线不变）。
- 跨批次任务列表（list_all_tasks）：供「任课教师分配/合班拆班/教师任务确认」等全局工作队列页使用。
- 统计（get_task_stats）：批次/任务状态分布 + 分配率/教师确认率。
"""
from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

_TEACH_WEEKS = 18  # 兼容旧数据；新任务教学周后续改由校历解析器统一提供

# 处于「已分配教师之前」的可合并/可拆分阶段（教师确认后禁止改动教学班组成，需先由教师/学院退回）
_PRE_CONFIRM_STATUSES = ("PENDING_ASSIGN", "ASSIGNED")


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _user_keys(user) -> set[str]:
    """派生当前用户教师标识键，用于教师任务确认按本人授课范围收敛。

    只使用 userId/登录名，不含 realName，避免同名教师越权。
    """
    u = user or {}
    uid = str(u.get("userId") or "")
    login = u.get("loginName") or ""
    return {k for k in (uid, login, uid[2:] if uid.startswith("u_") else "") if k}


def _audit(db, biz_type, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


def _task_row(t) -> dict:
    return {"taskId": str(t.id), "batchId": str(t.batch_id), "courseId": str(t.course_id),
            "courseCode": t.course_code or "", "courseName": t.course_name or "",
            "classId": str(t.class_id or ""), "teachingClassCode": t.teaching_class_code or "",
            "teachingClassName": t.teaching_class_name or "",
            "isMerged": bool(t.is_merged), "mergedIntoId": str(t.merged_into_id or ""),
            "teacherId": str(t.teacher_id or ""), "teacherKey": t.teacher_key or "",
            "teacherName": t.teacher_name or "", "expectedStudents": t.expected_students,
            "weeklyHours": t.weekly_hours, "totalHours": t.total_hours,
            "startWeek": t.start_week, "endWeek": t.end_week, "status": t.status,
            "rejectReason": t.reject_reason or ""}


def _teaching_class_code(term_id, course_code, class_id) -> str:
    """确定性教学班代码：学期+课程代码+行政班 id。"""
    return f"TC{term_id}-{course_code or 'X'}-{class_id}"


# ═══════════ 批次生成（幂等）═══════════

def generate_batch(body, user) -> dict:
    """按已发布方案生成教学任务批次。幂等：同(term,college)复用批次，已存在(course,class)任务不重复。"""
    term_id = int(body.termId)
    college_id = int(body.collegeId) if getattr(body, "collegeId", None) else None
    with session() as db:
        from app.models import (AaProgram, AaProgramBinding, AaProgramCourse, AaCourse,
                                AaTeachingTask, AaTeachingTaskBatch, SchoolClass)
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        from app.modules.academic_affairs.services.academic_affairs_stats_service import (
            _resolve_scope, _validate_college_param)
        guard_term_writable(db, term_id)
        scope = _resolve_scope(user, db)
        _validate_college_param(scope, college_id)
        if not scope.all and not college_id:
            if len(scope.college_ids) == 1:
                college_id = next(iter(scope.college_ids))
            else:
                raise AppException("VALIDATION_ERROR", "请指定学院后再生成教学任务")
        batch_conds = [
            AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.term_id == term_id,
            AaTeachingTaskBatch.status == "DRAFT", AaTeachingTaskBatch.is_deleted.is_(False)]
        if college_id:
            batch_conds.append(AaTeachingTaskBatch.college_id == college_id)
        batch = db.scalars(select(AaTeachingTaskBatch).where(*batch_conds)).first()
        if not batch:
            batch = AaTeachingTaskBatch(tenant_id=_tid(), term_id=term_id,
                                        batch_name=(getattr(body, "batchName", None) or f"学期{term_id}教学任务"),
                                        college_id=college_id, generate_at=datetime.utcnow(), status="DRAFT")
            db.add(batch)
            db.flush()
        made = 0
        prog_conds = [AaProgram.tenant_id == _tid(), AaProgram.status == "ENABLED",
                      AaProgram.is_deleted.is_(False)]
        for p in db.scalars(select(AaProgram).where(*prog_conds)).all():
            bindings = db.scalars(select(AaProgramBinding).where(
                AaProgramBinding.tenant_id == _tid(), AaProgramBinding.program_id == p.id,
                AaProgramBinding.status == "ACTIVE",
                AaProgramBinding.is_deleted.is_(False))).all()
            courses = db.scalars(select(AaProgramCourse).where(
                AaProgramCourse.tenant_id == _tid(), AaProgramCourse.program_id == p.id,
                AaProgramCourse.is_deleted.is_(False))).all()
            for bd in bindings:
                if bd.class_id:
                    target_classes = [db.get(SchoolClass, int(bd.class_id))]
                else:
                    target_classes = db.scalars(select(SchoolClass).where(
                        SchoolClass.tenant_id == _tid(), SchoolClass.major_id == bd.major_id,
                        SchoolClass.grade == bd.grade_year, SchoolClass.class_status == "NORMAL",
                        SchoolClass.is_deleted.is_(False))).all()
                for cls in target_classes:
                    if not cls:
                        continue
                    if college_id:
                        from app.models import Major
                        maj = db.get(Major, int(cls.major_id)) if cls.major_id else None
                        if not maj or maj.college_id != college_id:
                            continue
                    if not scope.all and scope.class_ids and cls.id not in scope.class_ids:
                        continue
                    for pc in courses:
                        if not pc.course_id:
                            continue
                        exist = db.scalars(select(AaTeachingTask).where(
                            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id == batch.id,
                            AaTeachingTask.course_id == pc.course_id, AaTeachingTask.class_id == cls.id,
                            AaTeachingTask.is_deleted.is_(False))).first()
                        if exist:
                            continue
                        course = db.get(AaCourse, int(pc.course_id))
                        hours = course.hours_total if course and course.hours_total else 0
                        ccode = course.course_code if course else ""
                        db.add(AaTeachingTask(
                            tenant_id=_tid(), batch_id=batch.id, course_id=pc.course_id,
                            course_code=ccode, course_name=course.course_name if course else "",
                            class_id=cls.id,
                            teaching_class_code=_teaching_class_code(term_id, ccode, cls.id),
                            teaching_class_name=f"{course.course_name if course else ''}({cls.class_name})",
                            total_hours=hours, weekly_hours=(round(hours / _TEACH_WEEKS) if hours else None),
                            start_week=1, end_week=_TEACH_WEEKS, status="PENDING_ASSIGN"))
                        made += 1
        _audit(db, "AA_TASK_BATCH", batch.id, "GENERATE", f"+{made}")
        db.commit()
        db.refresh(batch)
        return {"batchId": str(batch.id), "batchName": batch.batch_name, "status": batch.status,
                "tasksGenerated": made}


# ═══════════ 分配 / 教师确认 ═══════════

def assign_teacher_tx(db, task_id, user, body) -> dict:
    from app.models import AaTeachingTask
    from .academic_affairs_task_service import _require_college_task_action

    t = db.query(AaTeachingTask).filter(
        AaTeachingTask.id == int(task_id),
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.is_deleted.is_(False),
    ).first()
    if not t:
        raise not_found("教学任务不存在")
    _require_college_task_action(db, t, user, "manage")
    db.refresh(t, with_for_update=True)
    if t.status not in ("PENDING_ASSIGN", "REJECTED_BY_TEACHER", "ASSIGNED"):
        raise AppException("APPROVAL_VERSION_CONFLICT", "该任务当前状态不可分配")
    previous_assignment = SimpleNamespace(teacher_key=t.teacher_key, start_week=t.start_week, end_week=t.end_week)
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
    from .academic_affairs_grade_todo_teacher_relation_guard import sync_default_assignment_change
    sync_default_assignment_change(db, t, previous_assignment)
    _audit(db, "AA_TASK", t.id, "ASSIGN", t.teacher_name or "")
    db.flush()
    return _task_row(t)


def assign_teacher(task_id, user, body) -> dict:
    with session() as db:
        result = assign_teacher_tx(db, task_id, user, body)
        db.commit()
        return result


def teacher_act(task_id, user, action, reason="") -> dict:
    """教师确认/退回使用正式任课关系；管理角色不能冒充教师。"""
    action = (action or "").upper()
    with session() as db:
        from app.models import AaTeachingTask
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        from .academic_affairs_teacher_relation_authority import require_teacher
        t = db.query(AaTeachingTask).filter(
            AaTeachingTask.id == int(task_id), AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.is_deleted.is_(False),
        ).with_for_update().first()
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("教学任务不存在")
        guard_term_writable(db, _term_id_of(db, t.batch_id))
        require_teacher(db, t, user, lock=True)
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


def _pending_count(db, batch_id) -> int:
    """批内待分配/被教师退回任务数（MERGED 已并入他行不计）。"""
    from app.models import AaTeachingTask
    return db.scalar(select(func.count()).select_from(AaTeachingTask).where(
        AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id == int(batch_id),
        AaTeachingTask.status.in_(["PENDING_ASSIGN", "REJECTED_BY_TEACHER"]),
        AaTeachingTask.is_deleted.is_(False))) or 0


def submit_batch(batch_id, user) -> dict:
    """批次提交审核：要求所有任务已分配。"""
    with session() as db:
        from app.models import AaTeachingTaskBatch
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        b = db.get(AaTeachingTaskBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("任务批次不存在")
        guard_term_writable(db, b.term_id)
        if b.status not in ("DRAFT", "COLLEGE_CONFIRMED", "TEACHER_CONFIRMED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该批次当前状态不可提交")
        pending = _pending_count(db, b.id)
        if pending:
            raise AppException("DATA_CONFLICT", f"仍有 {pending} 条任务未分配/被教师退回，不可提交")
        b.status = "APPROVED"
        _audit(db, "AA_TASK_BATCH", b.id, "APPROVED")
        db.commit()
        db.refresh(b)
        return {"batchId": str(b.id), "status": b.status}


# ═══════════ 教务两级确认 ═══════════

def college_confirm_batch(batch_id, user) -> dict:
    with session() as db:
        from app.models import AaTeachingTaskBatch
        b = db.get(AaTeachingTaskBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("任务批次不存在")
        if b.status not in ("DRAFT", "RETURNED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该批次当前状态不可核对确认")
        pending = _pending_count(db, b.id)
        if pending:
            raise AppException("DATA_CONFLICT", f"仍有 {pending} 条任务未分配/被教师退回，不可确认")
        b.status = "COLLEGE_CONFIRMED"
        _audit(db, "AA_TASK_BATCH", b.id, "COLLEGE_CONFIRM")
        db.commit()
        db.refresh(b)
        return {"batchId": str(b.id), "status": b.status}


def review_batch(batch_id, user, action, reason="") -> dict:
    """教务终审：通过后教师已确认任务进入 READY；退回学院重新核对。"""
    action = (action or "").upper()
    with session() as db:
        from app.models import AaTeachingTask, AaTeachingTaskBatch
        b = db.get(AaTeachingTaskBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("任务批次不存在")
        if b.status != "COLLEGE_CONFIRMED":
            raise AppException("APPROVAL_VERSION_CONFLICT", "该批次当前状态不可教务终审（需先学院核对确认）")
        if action == "APPROVE":
            b.status = "APPROVED"
            rows = db.scalars(select(AaTeachingTask).where(
                AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id == b.id,
                AaTeachingTask.status == "TEACHER_CONFIRMED", AaTeachingTask.is_deleted.is_(False))).all()
            for t in rows:
                t.status = "READY"
            _audit(db, "AA_TASK_BATCH", b.id, "ACADEMIC_APPROVE", f"READY x{len(rows)}")
        elif action in ("RETURN", "REJECT"):
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
            b.status = "RETURNED"
            _audit(db, "AA_TASK_BATCH", b.id, "ACADEMIC_RETURN", reason.strip())
        else:
            raise AppException("VALIDATION_ERROR", "无效操作")
        db.commit()
        db.refresh(b)
        return {"batchId": str(b.id), "status": b.status}


# ═══════════ 合班 / 拆班 ═══════════

def merge_tasks(body, user) -> dict:
    from .academic_affairs_task_service import _require_college_task_action
    task_ids = list(dict.fromkeys(int(x) for x in (getattr(body, "taskIds", None) or [])))
    if len(task_ids) < 2:
        raise AppException("VALIDATION_ERROR", "合班至少需选择 2 条教学任务")
    note = (getattr(body, "note", None) or "").strip()
    with session() as db:
        from app.models import AaTeachingTask
        rows = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.id.in_(task_ids),
            AaTeachingTask.is_deleted.is_(False)).order_by(AaTeachingTask.id)).all()
        if len(rows) != len(set(task_ids)):
            raise not_found("部分教学任务不存在")
        by_id = {t.id: t for t in rows}
        ordered = [by_id[i] for i in task_ids]
        survivor, members = ordered[0], ordered[1:]
        batch_id, course_id = survivor.batch_id, survivor.course_id
        _require_college_task_action(db, survivor, user, "merge")
        for task in rows:
            db.refresh(task, with_for_update=True)
        for t in ordered:
            if t.batch_id != batch_id or t.course_id != course_id:
                raise AppException("VALIDATION_ERROR", "合班的教学任务须同批次、同课程")
            if t.status not in _PRE_CONFIRM_STATUSES:
                raise AppException("DATA_CONFLICT", f"任务 {t.id} 当前状态（{t.status}）不可合班，需先撤回教师确认")
            if t.is_merged or t.merged_into_id:
                raise AppException("DATA_CONFLICT", f"任务 {t.id} 已参与过合班，不可重复合并")
        snapshot = {
            "selfClassId": str(survivor.class_id or ""), "selfClassName": survivor.teaching_class_name or "",
            "selfExpectedStudents": survivor.expected_students,
            "memberTaskIds": [t.id for t in members],
        }
        merged_names = [survivor.teaching_class_name or ""] + [m.teaching_class_name or "" for m in members]
        survivor.teaching_class_name = " + ".join([n for n in merged_names if n])
        survivor.teaching_class_code = _teaching_class_code(
            _term_id_of(db, batch_id), survivor.course_code, f"M{survivor.id}")
        survivor.expected_students = sum((t.expected_students or 0) for t in ordered) or None
        survivor.is_merged = True
        survivor.merge_snapshot_json = json.dumps(snapshot, ensure_ascii=False)
        for m in members:
            m.status = "MERGED"
            m.merged_into_id = survivor.id
        _audit(db, "AA_TASK", survivor.id, "MERGE",
               f"members={[m.id for m in members]} note={note}" if note else f"members={[m.id for m in members]}")
        db.commit()
        db.refresh(survivor)
        return _task_row(survivor)


def split_task(task_id, user) -> dict:
    from .academic_affairs_task_service import _require_college_task_action
    with session() as db:
        from app.models import AaTeachingTask
        t = db.query(AaTeachingTask).filter(AaTeachingTask.id == int(task_id),
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False)).first()
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("教学任务不存在")
        _require_college_task_action(db, t, user, "merge")
        db.refresh(t, with_for_update=True)
        if not t.is_merged or not t.merge_snapshot_json:
            raise AppException("DATA_CONFLICT", "该任务非合班 survivor，无法拆班")
        if t.status not in _PRE_CONFIRM_STATUSES:
            raise AppException("DATA_CONFLICT", f"任务当前状态（{t.status}）不可拆班，需先撤回教师确认")
        snap = json.loads(t.merge_snapshot_json)
        member_ids = snap.get("memberTaskIds") or []
        members = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.id.in_(member_ids),
            AaTeachingTask.is_deleted.is_(False)).order_by(AaTeachingTask.id).with_for_update()).all() if member_ids else []
        if any(m.batch_id != t.batch_id for m in members):
            raise AppException("DATA_CONFLICT", "合班历史包含其他批次任务，不能直接拆班")
        for m in members:
            if m.merged_into_id == t.id:
                m.status, m.merged_into_id = "PENDING_ASSIGN", None
        t.teaching_class_name = snap.get("selfClassName") or t.teaching_class_name
        t.expected_students = snap.get("selfExpectedStudents")
        t.is_merged = False
        t.merge_snapshot_json = None
        term_id = _term_id_of(db, t.batch_id)
        t.teaching_class_code = _teaching_class_code(term_id, t.course_code, t.class_id)
        _audit(db, "AA_TASK", t.id, "SPLIT", f"members={member_ids}")
        db.commit()
        db.refresh(t)
        return _task_row(t)


# ═══════════ 教学任务调整 ═══════════

_TEACHER_FIELDS = ("teacherId", "teacherKey")


def adjust_task_tx(db, task_id, user, body) -> dict:
    """学院更正任务；任务、原批次复核与投影由调用方同事务提交。"""
    from app.models import AaScheduleItem, AaTeachingTask
    from .academic_affairs_task_service import _require_college_task_action
    reason = (getattr(body, "reason", None) or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "调整原因必填且不少于 5 字")
    t = db.query(AaTeachingTask).filter(AaTeachingTask.id == int(task_id),
        AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False)).first()
    if not t or t.is_deleted or t.tenant_id != _tid():
        raise not_found("教学任务不存在")
    batch = _require_college_task_action(db, t, user, "adjust")
    db.refresh(t, with_for_update=True)
    from .academic_affairs_task_execution_authority import require_independent_task
    require_independent_task(db, t)
    from app.models import AaTeachingTaskSourceHandoff
    if db.scalar(select(AaTeachingTaskSourceHandoff.id).where(
        AaTeachingTaskSourceHandoff.tenant_id == _tid(),
        AaTeachingTaskSourceHandoff.execution_task_id == t.id).limit(1).with_for_update(read=True)) is not None:
        raise AppException("DATA_CONFLICT", "本任务已承接后继方案来源，不能直接改写原任务计划；请沿正式任课或排课变更办理。", http_status=409)
    if t.status == "MERGED":
        raise AppException("DATA_CONFLICT", "该任务已合班并入其他教学班，请先对合班后的主任务拆班后再调整")
    scheduled = db.scalar(select(func.count()).select_from(AaScheduleItem).where(
        AaScheduleItem.tenant_id == _tid(), AaScheduleItem.task_id == t.id,
        AaScheduleItem.is_deleted.is_(False))) or 0
    if scheduled:
        raise AppException("DATA_CONFLICT", "该任务已生成课表项，请先在排课管理调整/作废对应课表项后再调整教学任务")
    previous_assignment = SimpleNamespace(teacher_key=t.teacher_key, start_week=t.start_week, end_week=t.end_week)
    changed: list[str] = []

    def _apply(field: str, attr: str, new_v) -> None:
        if getattr(body, field, None) is None:
            return
        if new_v != getattr(t, attr):
            setattr(t, attr, new_v)
            changed.append(field)

    _apply("teacherId", "teacher_id", int(body.teacherId) if getattr(body, "teacherId", None) else None)
    _apply("teacherKey", "teacher_key", getattr(body, "teacherKey", None) or None)
    _apply("teacherName", "teacher_name", getattr(body, "teacherName", None) or None)
    _apply("weeklyHours", "weekly_hours", getattr(body, "weeklyHours", None))
    _apply("totalHours", "total_hours", getattr(body, "totalHours", None))
    _apply("startWeek", "start_week", getattr(body, "startWeek", None))
    _apply("endWeek", "end_week", getattr(body, "endWeek", None))
    _apply("expectedStudents", "expected_students", getattr(body, "expectedStudents", None))
    if not changed:
        raise AppException("VALIDATION_ERROR", "提交的字段与当前值相同，未发生实际调整")
    if t.start_week is not None and t.end_week is not None and t.start_week > t.end_week:
        raise AppException("VALIDATION_ERROR", "起始周不能晚于结束周")
    if any(f in changed for f in _TEACHER_FIELDS):
        if batch.status in {"COLLEGE_CONFIRMED", "APPROVED"}:
            downstream = db.scalar(select(AaScheduleItem.id).join(
                AaTeachingTask, AaTeachingTask.id == AaScheduleItem.task_id).where(
                AaScheduleItem.tenant_id == _tid(), AaScheduleItem.is_deleted.is_(False),
                AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id == batch.id,
                AaTeachingTask.is_deleted.is_(False)).limit(1))
            if downstream:
                raise AppException("DATA_CONFLICT", "本批次已有课表，不能退回整批任务；请通过正式任课关系或排课变更办理")
            previous_status = batch.status
            from .academic_affairs_task_service import _return_editable_batch
            _return_editable_batch(db, batch)
            _audit(db, "AA_TASK_BATCH", batch.id, "TEACHER_ADJUST_REOPEN",
                   f"教师调整触发重新校院复核；原状态={previous_status}；任务={t.id}；原因={reason}")
        t.status = "ASSIGNED"
        t.confirm_at = None
        t.reject_reason = None
    from .academic_affairs_grade_todo_teacher_relation_guard import sync_default_assignment_change
    sync_default_assignment_change(db, t, previous_assignment)
    _audit(db, "AA_TASK", t.id, "ADJUST", f"fields={changed} reason={reason}")
    db.flush()
    return _task_row(t)


def adjust_task(task_id, user, body) -> dict:
    with session() as db:
        result = adjust_task_tx(db, task_id, user, body)
        db.commit()
        return result


def _validate_draft_task_voidable(task, batch, dependent_counts: dict[str, int]) -> None:
    """只允许作废尚未分配、仍处草稿批次且没有下游引用的误生成任务。"""
    if str(batch.status or "").upper() != "DRAFT":
        raise AppException("DATA_CONFLICT", "仅草稿批次中的任务可以作废")
    if (str(task.status or "").upper() != "PENDING_ASSIGN"
            or str(getattr(task, "teacher_key", "") or "").strip()
            or getattr(task, "teacher_id", None)):
        raise AppException("DATA_CONFLICT", "任务已分配或已进入办理流程，不能按草稿作废")
    if any(int(value or 0) for value in dependent_counts.values()):
        raise AppException("DATA_CONFLICT", "任务已有业务引用，不能作废")


def _validate_auto_draft_teaching_class(task, teaching_class, roster_versions, roster_members,
                                        teacher_count: int, consumer_count: int) -> None:
    """Allow only the untouched initial roster projection created with a draft task."""
    if teaching_class is None:
        return
    if (teaching_class.status != "ACTIVE" or teaching_class.class_type != "ADMIN"
            or teaching_class.source_type != "TEACHING_TASK"
            or int(teaching_class.source_id or 0) != int(task.id)
            or teaching_class.roster_status != "LOCKED"):
        raise AppException("DATA_CONFLICT", "教学班不是未使用的任务自动投影，不能作废")
    if teacher_count or consumer_count:
        raise AppException("DATA_CONFLICT", "教学班已分配教师或已被正式业务消费，不能作废")
    if len(roster_versions) != 1:
        raise AppException("DATA_CONFLICT", "教学班名单已有后续版本或缺少初始版本，不能作废")
    version = roster_versions[0]
    if (version.is_deleted or int(version.id) != int(teaching_class.current_roster_version_id or 0)
            or int(version.version_no or 0) != 1
            or version.source_type != "ADMIN_CLASS"
            or int(version.source_id or 0) != int(task.class_id or 0)
            or version.status != "LOCKED"
            or int(teaching_class.current_roster_version_no or 0) != 1
            or len(roster_members) != int(version.member_count or 0)
            or any(member.is_deleted or member.status != "ACTIVE" or member.roster_version_id != version.id
                   or member.source_type != "ADMIN_CLASS" for member in roster_members)):
        raise AppException("DATA_CONFLICT", "教学班名单已被调整或使用，不能作废")


def void_draft_task(task_id, user, reason: str) -> dict:
    """由当前开课学院责任人逻辑作废无下游依赖的误生成草稿任务。"""
    from app.models import (AaAttendanceSession, AaEvaluationResult, AaEvaluationTask, AaExamCourse,
                            AaGradeTask, AaRosterConsumerSnapshot, AaScheduleChange, AaScheduleItem,
                            AaSelectionCourse, AaTeachingClass, AaTeachingClassMember,
                            AaTeachingClassRosterVersion, AaTeachingClassTeacher, AaTeachingTask,
                            AaTextbookSelection)
    from .academic_affairs_task_service import _require_college_task_action

    cleaned_reason = str(reason or "").strip()
    if len(cleaned_reason) < 5 or len(cleaned_reason) > 500:
        raise AppException("VALIDATION_ERROR", "作废原因须为 5 至 500 个字")
    with session() as db:
        task = db.scalar(select(AaTeachingTask).where(
            AaTeachingTask.id == int(task_id), AaTeachingTask.tenant_id == _tid(),
            AaTeachingTask.is_deleted.is_(False),
        ))
        if not task:
            raise not_found("教学任务不存在")
        # manage scope 同时校验本院范围、当前责任人、权限、可写学期及草稿阶段。
        batch = _require_college_task_action(db, task, user, "manage")
        db.refresh(task, with_for_update=True)
        if task.is_deleted or task.batch_id != batch.id:
            raise AppException("APPROVAL_VERSION_CONFLICT", "任务已变化，请刷新后核对")
        teaching_class = db.query(AaTeachingClass).filter(
            AaTeachingClass.tenant_id == _tid(), AaTeachingClass.teaching_task_id == task.id,
            AaTeachingClass.is_deleted.is_(False),
        ).populate_existing().with_for_update().first()
        roster_versions = []
        roster_members = []
        class_teacher_count = 0
        class_consumer_count = 0
        if teaching_class:
            roster_versions = db.scalars(select(AaTeachingClassRosterVersion).where(
                AaTeachingClassRosterVersion.tenant_id == _tid(),
                AaTeachingClassRosterVersion.teaching_class_id == teaching_class.id,
            ).order_by(AaTeachingClassRosterVersion.version_no).with_for_update()).all()
            roster_members = db.scalars(select(AaTeachingClassMember).where(
                AaTeachingClassMember.tenant_id == _tid(),
                AaTeachingClassMember.teaching_class_id == teaching_class.id,
            ).order_by(AaTeachingClassMember.id)).all()
            class_teacher_count = int(db.scalar(select(AaTeachingClassTeacher.id).where(
                AaTeachingClassTeacher.tenant_id == _tid(),
                AaTeachingClassTeacher.teaching_class_id == teaching_class.id,
            ).limit(1)) is not None)
            class_consumer_count = int(db.scalar(select(AaRosterConsumerSnapshot.id).where(
                AaRosterConsumerSnapshot.tenant_id == _tid(),
                AaRosterConsumerSnapshot.teaching_class_id == teaching_class.id,
            ).limit(1)) is not None)
        _validate_auto_draft_teaching_class(
            task, teaching_class, roster_versions, roster_members,
            class_teacher_count, class_consumer_count,
        )
        dependent_counts = {
            "schedule": int(db.scalar(select(AaScheduleItem.id).where(
                AaScheduleItem.tenant_id == _tid(), AaScheduleItem.task_id == task.id,
                AaScheduleItem.is_deleted.is_(False),
            ).limit(1)) is not None),
            "selection": int(db.scalar(select(AaSelectionCourse.id).where(
                AaSelectionCourse.tenant_id == _tid(), AaSelectionCourse.teaching_task_id == task.id,
                AaSelectionCourse.is_deleted.is_(False),
            ).limit(1)) is not None),
            "grade": int(db.scalar(select(AaGradeTask.id).where(
                AaGradeTask.tenant_id == _tid(), AaGradeTask.teaching_task_id == task.id,
                AaGradeTask.is_deleted.is_(False),
            ).limit(1)) is not None),
            "scheduleChange": int(db.scalar(select(AaScheduleChange.id).where(
                AaScheduleChange.tenant_id == _tid(), AaScheduleChange.task_id == task.id,
                AaScheduleChange.is_deleted.is_(False),
            ).limit(1)) is not None),
            "examCourse": int(db.scalar(select(AaExamCourse.id).where(
                AaExamCourse.tenant_id == _tid(), AaExamCourse.teaching_task_id == task.id,
                AaExamCourse.is_deleted.is_(False),
            ).limit(1)) is not None),
            "textbookSelection": int(db.scalar(select(AaTextbookSelection.id).where(
                AaTextbookSelection.tenant_id == _tid(), AaTextbookSelection.task_id == task.id,
                AaTextbookSelection.is_deleted.is_(False),
            ).limit(1)) is not None),
            "evaluationTask": int(db.scalar(select(AaEvaluationTask.id).where(
                AaEvaluationTask.tenant_id == _tid(), AaEvaluationTask.teaching_task_id == task.id,
                AaEvaluationTask.is_deleted.is_(False),
            ).limit(1)) is not None),
            "evaluationResult": int(db.scalar(select(AaEvaluationResult.id).where(
                AaEvaluationResult.tenant_id == _tid(), AaEvaluationResult.teaching_task_id == task.id,
                AaEvaluationResult.is_deleted.is_(False),
            ).limit(1)) is not None),
            "attendanceSession": int(db.scalar(select(AaAttendanceSession.id).where(
                AaAttendanceSession.tenant_id == _tid(), AaAttendanceSession.teaching_task_id == task.id,
                AaAttendanceSession.is_deleted.is_(False),
            ).limit(1)) is not None),
            "rosterConsumer": int(db.scalar(select(AaRosterConsumerSnapshot.id).where(
                AaRosterConsumerSnapshot.tenant_id == _tid(), AaRosterConsumerSnapshot.teaching_task_id == task.id,
                AaRosterConsumerSnapshot.is_deleted.is_(False),
            ).limit(1)) is not None),
        }
        _validate_draft_task_voidable(task, batch, dependent_counts)
        if teaching_class:
            teaching_class.status = "ARCHIVED"
            _audit(db, "AA_TEACHING_CLASS", teaching_class.id, "ARCHIVE_AUTO_DRAFT_VOID",
                   f"taskId={task.id};initialRosterVersionId={teaching_class.current_roster_version_id}")
        task.is_deleted = True
        _audit(db, "AA_TASK", task.id, "VOID_DRAFT", cleaned_reason)
        db.flush()
        result = {"taskId": str(task.id), "batchId": str(batch.id), "isDeleted": True,
                  "status": "VOIDED", "reason": cleaned_reason}
        db.commit()
        return result


def _term_id_of(db, batch_id) -> int:
    from app.models import AaTeachingTaskBatch
    b = db.get(AaTeachingTaskBatch, int(batch_id))
    return b.term_id if b else 0


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


def list_all_tasks(user, batch_id=None, course_id=None, status=None, mergeable=False, mine=False,
                   page=1, page_size=50):
    """跨批次教学任务列表；mine=True 时仅返回本人稳定 teacher_key 命中的任务。"""
    from app.models import AaTeachingTask
    with session() as db:
        conds = [AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False)]
        if batch_id:
            conds.append(AaTeachingTask.batch_id == int(batch_id))
        if course_id:
            conds.append(AaTeachingTask.course_id == int(course_id))
        if status:
            conds.append(AaTeachingTask.status == status)
        if mergeable:
            conds.append(AaTeachingTask.status.in_(_PRE_CONFIRM_STATUSES))
            conds.append(AaTeachingTask.is_merged.is_(False))
            conds.append(AaTeachingTask.merged_into_id.is_(None))
        rows = db.scalars(select(AaTeachingTask).where(*conds).order_by(
            AaTeachingTask.batch_id.desc(), AaTeachingTask.course_id, AaTeachingTask.id)).all()
        if mine:
            keys = _user_keys(user)
            rows = [t for t in rows if t.teacher_key and t.teacher_key in keys]
        out = [_task_row(t) for t in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


# ═══════════ 统计 ═══════════

_DONE_TASK_STATUSES = ("TEACHER_CONFIRMED", "READY")
_TERMINAL_ASSIGN_STATUSES = ("ASSIGNED", "TEACHER_CONFIRMED", "READY")


def get_task_stats(user, term_id=None) -> dict:
    """批次/任务状态分布 + 分配率/教师确认率；剔除 MERGED 避免重复计数。"""
    from app.models import AaTeachingTask, AaTeachingTaskBatch, AaTerm
    with session() as db:
        b_conds = [AaTeachingTaskBatch.tenant_id == _tid(), AaTeachingTaskBatch.is_deleted.is_(False)]
        if term_id:
            b_conds.append(AaTeachingTaskBatch.term_id == int(term_id))
        batches = db.scalars(select(AaTeachingTaskBatch).where(*b_conds)).all()
        batch_ids = [b.id for b in batches]
        batch_by_status: dict[str, int] = {}
        for b in batches:
            batch_by_status[b.status] = batch_by_status.get(b.status, 0) + 1
        t_conds = [AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
                   AaTeachingTask.status != "MERGED"]
        if batch_ids:
            t_conds.append(AaTeachingTask.batch_id.in_(batch_ids))
        elif term_id:
            t_conds.append(AaTeachingTask.batch_id.in_([-1]))
        tasks = db.scalars(select(AaTeachingTask).where(*t_conds)).all()
        task_by_status: dict[str, int] = {}
        for t in tasks:
            task_by_status[t.status] = task_by_status.get(t.status, 0) + 1
        task_total = len(tasks)
        assigned_n = sum(1 for t in tasks if t.status in _TERMINAL_ASSIGN_STATUSES)
        confirmed_n = sum(1 for t in tasks if t.status in _DONE_TASK_STATUSES)
        rejected_n = sum(1 for t in tasks if t.status == "REJECTED_BY_TEACHER")
        merged_n = db.scalar(select(func.count()).select_from(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
            AaTeachingTask.status == "MERGED",
            AaTeachingTask.batch_id.in_(batch_ids) if batch_ids else AaTeachingTask.batch_id.in_([-1]))) or 0

        def _rate(n, d):
            return round(n * 100.0 / d, 1) if d else 0.0

        by_term: dict[int, dict] = {}
        for b in batches:
            e = by_term.setdefault(b.term_id, {"termId": str(b.term_id), "batchCount": 0,
                                               "taskTotal": 0, "confirmedTotal": 0})
            e["batchCount"] += 1
        batch_index = {b.id: b for b in batches}
        for t in tasks:
            b = batch_index.get(t.batch_id)
            if not b:
                continue
            e = by_term.get(b.term_id)
            if not e:
                continue
            e["taskTotal"] += 1
            if t.status in _DONE_TASK_STATUSES:
                e["confirmedTotal"] += 1
        term_labels = {}
        if by_term:
            for tr in db.scalars(select(AaTerm).where(
                    AaTerm.tenant_id == _tid(), AaTerm.id.in_(list(by_term.keys())))).all():
                term_labels[tr.id] = f"{tr.year_code} 第{tr.term_no}学期"
        by_term_list = []
        for tid, e in by_term.items():
            e["termLabel"] = term_labels.get(tid, f"学期{tid}")
            e["confirmRate"] = _rate(e["confirmedTotal"], e["taskTotal"])
            by_term_list.append(e)
        by_term_list.sort(key=lambda x: x["termId"], reverse=True)
        return {
            "batchTotal": len(batches), "batchByStatus": batch_by_status,
            "taskTotal": task_total, "taskByStatus": task_by_status, "mergedCount": merged_n,
            "assignRate": {"numerator": assigned_n, "denominator": task_total, "rate": _rate(assigned_n, task_total)},
            "teacherConfirmRate": {"numerator": confirmed_n,
                                   "denominator": assigned_n + rejected_n,
                                   "rate": _rate(confirmed_n, assigned_n + rejected_n)},
            "byTerm": by_term_list,
        }
