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

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

_TEACH_WEEKS = 18  # 默认学期教学周（真实：应读校历，V1 取常规 18 周）

# 处于「已分配教师之前」的可合并/可拆分阶段（教师确认后禁止改动教学班组成，需先由教师/学院退回）
_PRE_CONFIRM_STATUSES = ("PENDING_ASSIGN", "ASSIGNED")


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _user_keys(user) -> set[str]:
    """派生当前用户可能的教师标识键（userId/登录名/姓名），用于「教师任务确认」按本人授课范围收敛。
    与 academic_affairs_grade_service._user_keys 同构（教务域内小工具函数按模块各自持有，不跨文件耦合）。"""
    u = user or {}
    uid = str(u.get("userId") or "")
    login = u.get("loginName") or ""
    name = u.get("realName") or ""
    return {k for k in (uid, login, name, uid[2:] if uid.startswith("u_") else "") if k}


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
    """确定性教学班代码：学期+课程代码+行政班 id（org_service.list_teaching_classes 按此去重汇总）。"""
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
        guard_term_writable(db, term_id)  # 归档11卡§6.2：已归档学期不应重新生成教学任务
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
                    ccode = course.course_code if course else ""
                    db.add(AaTeachingTask(
                        tenant_id=_tid(), batch_id=batch.id, course_id=pc.course_id,
                        course_code=ccode, course_name=course.course_name if course else "",
                        class_id=bd.class_id,
                        teaching_class_code=_teaching_class_code(term_id, ccode, bd.class_id),
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
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        t = db.get(AaTeachingTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("教学任务不存在")
        guard_term_writable(db, _term_id_of(db, t.batch_id))  # 归档11卡§6.2：已归档学期的教学任务不应再调整分配
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


_REVIEW_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN", "COLLEGE_ADMIN"}  # 教务处/学校/学院管理员：代管不受本人授课范围收敛


def _check_teacher_scope(t, user) -> None:
    """任课教师仅能确认/退回本人 teacher_key 归属的任务；管理角色不受收敛。
    teacher_key 未回填时（历史分配未填工号）暂不拦截，避免误伤既有数据。"""
    role = (user.get("currentRoleCode") or "").upper()
    if role in _REVIEW_ROLES:
        return
    if not t.teacher_key:
        return
    if t.teacher_key not in _user_keys(user):
        raise AppException("NO_DATA_SCOPE", "该教学任务不在您的授课范围内")


def teacher_act(task_id, user, action, reason="") -> dict:
    """教师确认/退回教学任务（仅本人授课范围，管理角色代管不受限）。"""
    action = (action or "").upper()
    with session() as db:
        from app.models import AaTeachingTask
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        t = db.get(AaTeachingTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("教学任务不存在")
        guard_term_writable(db, _term_id_of(db, t.batch_id))  # 归档11卡§6.2：已归档学期不应再确认/退回教学任务
        _check_teacher_scope(t, user)
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
    """批内待分配/被教师退回任务数（MERGED 已并入他行不计，不阻断提交/确认）。"""
    from app.models import AaTeachingTask
    return db.scalar(select(func.count()).select_from(AaTeachingTask).where(
        AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id == int(batch_id),
        AaTeachingTask.status.in_(["PENDING_ASSIGN", "REJECTED_BY_TEACHER"]),
        AaTeachingTask.is_deleted.is_(False))) or 0


def submit_batch(batch_id, user) -> dict:
    """批次提交审核：要求所有任务已分配（无待分配/被教师退回）。历史契约：DRAFT/COLLEGE_CONFIRMED/
    TEACHER_CONFIRMED 均可一步直提 APPROVED（不变，TT1/TT4 测试基线）。"""
    with session() as db:
        from app.models import AaTeachingTaskBatch
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        b = db.get(AaTeachingTaskBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("任务批次不存在")
        guard_term_writable(db, b.term_id)  # 归档11卡§6.2：已归档学期不应再提交教学任务批次
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


# ═══════════ 教学任务确认（教务两级：学院核对确认 → 教务终审，Tier1 新增）═══════════

def college_confirm_batch(batch_id, user) -> dict:
    """学院核对确认：DRAFT→COLLEGE_CONFIRMED（要求批内任务均已分配教师，同 submit 校验口径）。"""
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
    """教务终审：COLLEGE_CONFIRMED→APPROVED（批内 TEACHER_CONFIRMED 任务同步置 READY，进入排课资源池）
    或 →RETURNED（原因必填≥5字，退回学院重新核对）。"""
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


# ═══════════ 合班 / 拆班（Tier1 新增，教师确认前可逆）═══════════

def merge_tasks(body, user) -> dict:
    """合班：同批次、同课程的 2+ 条待分配/已分配任务合并为一条 survivor（首个 taskId），其余置 MERGED。"""
    task_ids = list(dict.fromkeys(int(x) for x in (getattr(body, "taskIds", None) or [])))  # 去重保序
    if len(task_ids) < 2:
        raise AppException("VALIDATION_ERROR", "合班至少需选择 2 条教学任务")
    note = (getattr(body, "note", None) or "").strip()
    with session() as db:
        from app.models import AaTeachingTask
        rows = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.id.in_(task_ids),
            AaTeachingTask.is_deleted.is_(False))).all()
        if len(rows) != len(set(task_ids)):
            raise not_found("部分教学任务不存在")
        by_id = {t.id: t for t in rows}
        ordered = [by_id[i] for i in task_ids]
        survivor, members = ordered[0], ordered[1:]
        batch_id, course_id = survivor.batch_id, survivor.course_id
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
    """拆班：还原 merge_tasks 前状态——survivor 自身字段回填快照值，成员行回到 PENDING_ASSIGN。"""
    with session() as db:
        from app.models import AaTeachingTask
        t = db.get(AaTeachingTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("教学任务不存在")
        if not t.is_merged or not t.merge_snapshot_json:
            raise AppException("DATA_CONFLICT", "该任务非合班 survivor，无法拆班")
        if t.status not in _PRE_CONFIRM_STATUSES:
            raise AppException("DATA_CONFLICT", f"任务当前状态（{t.status}）不可拆班，需先撤回教师确认")
        snap = json.loads(t.merge_snapshot_json)
        member_ids = snap.get("memberTaskIds") or []
        members = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.id.in_(member_ids),
            AaTeachingTask.is_deleted.is_(False))).all() if member_ids else []
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


# ═══════════ 教学任务调整（管理员更正，续工新增）═══════════

_TEACHER_FIELDS = ("teacherId", "teacherKey", "teacherName")


def adjust_task(task_id, user, body) -> dict:
    """教学任务调整（教务管理员更正）：局部更新教师/周学时/总学时/起止周/预计人数，理由必填+审计。

    与「任课教师分配」(assign_teacher，面向 PENDING_ASSIGN/ASSIGNED/REJECTED_BY_TEACHER 的初始分配工作
    队列、整体覆盖式写入教师字段) 不同：本操作面向任一非终止态任务（含 TEACHER_CONFIRMED/READY 等已过初
    始分配阶段仍需更正的场景）。按「新值是否真的不同于当前值」判定字段是否变更（而非只看请求是否携带该
    字段）——前端表单会回填当前值一并提交，若按"是否携带"判定会把纯粹重提交也当作变更，误触发下面教师
    变更即退回重新确认的规则。变更教师身份时强制退回 ASSIGNED 要求重新确认，避免旧确认状态与新教师身份
    不一致地残留；仅调整学时/周次/人数不强制重新确认。
    已生成课表项(t_aa_schedule_item)的任务不可调整——课表项固化了教师/周次等信息，直接改任务会与课表
    产生静默不一致，须先在排课模块处理（作废/改排）对应课表项，再回到本操作调整任务。"""
    from app.models import AaScheduleItem, AaTeachingTask
    from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
    reason = (getattr(body, "reason", None) or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "调整原因必填且不少于 5 字")
    with session() as db:
        t = db.get(AaTeachingTask, int(task_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("教学任务不存在")
        guard_term_writable(db, _term_id_of(db, t.batch_id))  # 归档11卡§6.2：已归档学期不应再调整教学任务
        if t.status == "MERGED":
            raise AppException("DATA_CONFLICT", "该任务已合班并入其他教学班，请先对合班 survivor 任务拆班后再调整")
        scheduled = db.scalar(select(func.count()).select_from(AaScheduleItem).where(
            AaScheduleItem.tenant_id == _tid(), AaScheduleItem.task_id == t.id,
            AaScheduleItem.is_deleted.is_(False))) or 0
        if scheduled:
            raise AppException("DATA_CONFLICT", "该任务已生成课表项，请先在排课管理调整/作废对应课表项后再调整教学任务")

        changed: list[str] = []

        def _apply(field: str, attr: str, new_v) -> None:
            """仅当请求携带该字段(非 None)且解析后的新值确实不同于当前值时才写入并记入 changed。"""
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

        teacher_touched = any(f in changed for f in _TEACHER_FIELDS)
        if teacher_touched:
            t.status = "ASSIGNED"
            t.confirm_at = None
            t.reject_reason = None

        _audit(db, "AA_TASK", t.id, "ADJUST", f"fields={changed} reason={reason}")
        db.commit()
        db.refresh(t)
        return _task_row(t)


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
    """跨批次教学任务列表（Tier1 新增）——供「任课教师分配/合班拆班/教师任务确认」全局工作队列页复用。
    mergeable=True：仅返回教师确认前、尚未参与过合班的任务（合班候选池，前端按 courseId+batchId 分组勾选）。
    mine=True：仅返回按 _user_keys 命中本人 teacher_key 的任务（管理角色传 mine 时同样按本人身份收敛，
    如需代管全部请不传 mine，另走 batch/course 过滤——与 teacher_act 的管理角色豁免是两回事，
    这里是「列表默认视角」而非越权校验，越权仍在写操作 _check_teacher_scope 兜底）。"""
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


# ═══════════ 统计（Tier1 新增）═══════════

_DONE_TASK_STATUSES = ("TEACHER_CONFIRMED", "READY")
_TERMINAL_ASSIGN_STATUSES = ("ASSIGNED", "TEACHER_CONFIRMED", "READY")


def get_task_stats(user, term_id=None) -> dict:
    """教学任务统计（Tier1 新增）：批次/任务状态分布 + 分配率/教师确认率 + 按学期拆分。
    统计口径剔除 MERGED（已并入他行的非独立教学单元），避免重复计数。"""
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
        elif term_id:  # 指定学期但无批次：任务数必为 0，短路避免误查全量
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
        for t in tasks:
            b = next((x for x in batches if x.id == t.batch_id), None)
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
