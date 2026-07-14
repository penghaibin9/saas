"""13B 选课管理 service（SM-09 冻结状态机）。

三层：批次头(6态) → 课程供给(容量行锁) → 学生选课记录(4态)。
- 批次：建/发布/开选/截止/低人数课程取消/锁定名单/归档，时间窗到达由定时任务迁移。
- 学生：可选课程+实时余量 / 选课(八条校验+行锁扣减防超卖) / 退课 / 补选指引。
- 教务处：人工调整(LOCKED 后退课，原因≥5字) / 名单(教师按授课关系收敛) / 冲突报表 / 统计。

复用：AaCourse/AaTeachingTask/AaScheduleItem（课表冲突）/StudentProfile.student_status（SUSPENDED 拦截，
只读，不平行建表）/AffairsAuditTrail（审计）/get_config_json（规则兜底，不用误判为已启用的 feature_enabled）。
数据范围复用 affairs_security.build_affairs_context（TENANT_ALL/COLLEGE）。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import and_, func, select

from app.core.affairs_security import _derive_keys, build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

# ── 状态常量 ──
_BATCH_DRAFT, _BATCH_PUBLISHED, _BATCH_OPEN = "DRAFT", "PUBLISHED", "OPEN"
_BATCH_CLOSED, _BATCH_LOCKED, _BATCH_ARCHIVED = "CLOSED", "LOCKED", "ARCHIVED"
_REC_SELECTED, _REC_DROPPED = "SELECTED", "DROPPED"
_REC_COURSE_CANCELLED, _REC_LOCKED = "COURSE_CANCELLED", "LOCKED"
_COURSE_OPEN, _COURSE_CANCELLED = "OPEN", "COURSE_CANCELLED"


def _conflict(msg: str) -> AppException:
    return AppException("DATA_CONFLICT", msg)


def _invalid(msg: str) -> AppException:
    # 非法状态转移统一 409（本项目 INVALID_STATE 未注册，显式指定 http_status 对齐 DATA_CONFLICT 语义）
    return AppException("DATA_CONFLICT", msg, http_status=409)


def _op() -> str:
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or "")


def _role() -> str:
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, biz_id, action, detail="", before="", after=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_SELECTION", biz_id=biz_id,
                             action=action, operator=_op(), role_name=_role(),
                             detail=detail[:990], before_val=before[:990], after_val=after[:990],
                             occurred_at=datetime.utcnow()))


def _rule(db, batch, key, default):
    """批次规则优先 rule_json，其次 ACAD_RULE 配置，最后显式默认值（不误判未注册开关为已启用）。"""
    try:
        if batch.rule_json:
            j = json.loads(batch.rule_json)
            if key in j and j[key] is not None:
                return j[key]
    except (ValueError, TypeError):
        pass
    from app.services.platform_service import get_config_json
    cfg = get_config_json(_tid(), "ACAD_RULE", "selection")
    if isinstance(cfg, dict) and cfg.get(key) is not None:
        return cfg[key]
    return default


# ══════════════ 数据范围 ══════════════

def _ctx(user, db):
    return build_affairs_context(user, db)


def _is_school_scope(ctx) -> bool:
    return ctx.scope_type == "TENANT_ALL"


def _require_manage_scope(ctx):
    """写操作要求全校范围（教务处）。学院教务员只读。"""
    if not _is_school_scope(ctx):
        raise no_data_scope("仅教务处可管理选课批次")


# ══════════════ 批次 ══════════════

def _batch_dto(b) -> dict:
    return {"batchId": str(b.id), "termId": str(b.term_id) if b.term_id else None,
            "batchName": b.batch_name, "selectStartAt": _iso(b.select_start_at),
            "selectEndAt": _iso(b.select_end_at), "status": b.status,
            "applyScope": json.loads(b.apply_scope_json) if b.apply_scope_json else None,
            "rule": json.loads(b.rule_json) if b.rule_json else None,
            "remark": b.remark, "lockedAt": _iso(b.locked_at)}


def _get_batch(db, batch_id):
    from app.models import AaSelectionBatch
    b = db.query(AaSelectionBatch).filter(
        AaSelectionBatch.id == batch_id, AaSelectionBatch.tenant_id == _tid(),
        AaSelectionBatch.is_deleted.is_(False)).first()
    if not b:
        raise not_found("选课批次不存在")
    return b


def create_batch(user, body) -> dict:
    from app.models import AaSelectionBatch
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        name = (getattr(body, "batchName", None) or "").strip()
        if not name:
            raise AppException("VALIDATION_ERROR", "批次名称必填")
        b = AaSelectionBatch(
            tenant_id=_tid(), batch_name=name,
            term_id=int(body.termId) if getattr(body, "termId", None) else None,
            select_start_at=_parse_dt(getattr(body, "selectStartAt", None)),
            select_end_at=_parse_dt(getattr(body, "selectEndAt", None)),
            apply_scope_json=json.dumps(body.applyScope, ensure_ascii=False) if getattr(body, "applyScope", None) else None,
            rule_json=json.dumps(body.rule, ensure_ascii=False) if getattr(body, "rule", None) else None,
            remark=getattr(body, "remark", None), status=_BATCH_DRAFT)
        db.add(b)
        db.flush()
        _audit(db, b.id, "SELECTION_BATCH_CREATE", f"建批次 {name}")
        db.commit()
        return _batch_dto(b)


def _parse_dt(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        return None


def list_batches(user, status=None, term_id=None, page=1, page_size=20):
    from app.models import AaSelectionBatch
    with session() as db:
        ctx = _ctx(user, db)
        q = select(AaSelectionBatch).where(
            AaSelectionBatch.tenant_id == _tid(), AaSelectionBatch.is_deleted.is_(False))
        if status:
            q = q.where(AaSelectionBatch.status == status)
        if term_id:
            q = q.where(AaSelectionBatch.term_id == int(term_id))
        # 学院教务员 COLLEGE：仅看本院有课程供给的批次（简化：本期先全量只读，范围收敛在名单/统计层）
        rows = db.execute(q.order_by(AaSelectionBatch.id.desc())).scalars().all()
        total = len(rows)
        page_rows = rows[(page - 1) * page_size: page * page_size]
        return [_batch_dto(b) for b in page_rows], total


def get_batch(user, batch_id):
    with session() as db:
        _ctx(user, db)
        b = _get_batch(db, batch_id)
        return _batch_dto(b)


def publish_batch(user, batch_id) -> dict:
    from app.models import AaSelectionCourse
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        b = _get_batch(db, batch_id)
        if b.status != _BATCH_DRAFT:
            raise _invalid(f"仅 DRAFT 批次可发布，当前 {b.status}")
        cnt = db.query(func.count(AaSelectionCourse.id)).filter(
            AaSelectionCourse.batch_id == b.id, AaSelectionCourse.tenant_id == _tid(),
            AaSelectionCourse.is_deleted.is_(False)).scalar()
        if not cnt:
            raise AppException("VALIDATION_ERROR", "批次未配置任何可选课程，不可发布")
        b.status = _BATCH_PUBLISHED
        _audit(db, b.id, "SELECTION_BATCH_PUBLISH", "发布批次")
        db.commit()
        return _batch_dto(b)


def open_batch(user, batch_id) -> dict:
    """教务处手动开选（PUBLISHED→OPEN）；定时任务亦复用同一迁移。"""
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        b = _get_batch(db, batch_id)
        if b.status != _BATCH_PUBLISHED:
            raise _invalid(f"仅 PUBLISHED 批次可开选，当前 {b.status}")
        b.status = _BATCH_OPEN
        _audit(db, b.id, "SELECTION_BATCH_OPEN", "开选")
        db.commit()
        return _batch_dto(b)


def close_batch(user, batch_id) -> dict:
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        b = _get_batch(db, batch_id)
        if b.status != _BATCH_OPEN:
            raise _invalid(f"仅 OPEN 批次可截止，当前 {b.status}")
        b.status = _BATCH_CLOSED
        _audit(db, b.id, "SELECTION_BATCH_CLOSE", "截止选课")
        db.commit()
        return _batch_dto(b)


def lock_batch(user, batch_id) -> dict:
    """CLOSED→LOCKED：生成正式名单，选课记录 SELECTED→LOCKED（幂等）。"""
    from app.models import AaSelectionRecord
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        b = _get_batch(db, batch_id)
        if b.status == _BATCH_LOCKED:
            return _batch_dto(b)
        if b.status != _BATCH_CLOSED:
            raise _invalid(f"仅 CLOSED 批次可锁定，当前 {b.status}")
        db.query(AaSelectionRecord).filter(
            AaSelectionRecord.batch_id == b.id, AaSelectionRecord.tenant_id == _tid(),
            AaSelectionRecord.status == _REC_SELECTED).update(
            {AaSelectionRecord.status: _REC_LOCKED}, synchronize_session=False)
        b.status = _BATCH_LOCKED
        b.locked_at = datetime.utcnow()
        _audit(db, b.id, "SELECTION_BATCH_LOCK", "锁定名单")
        db.commit()
        return _batch_dto(b)


def archive_batch(user, batch_id) -> dict:
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        b = _get_batch(db, batch_id)
        if b.status == _BATCH_ARCHIVED:
            return _batch_dto(b)
        if b.status != _BATCH_LOCKED:
            raise _invalid(f"仅 LOCKED 批次可归档，当前 {b.status}")
        b.status = _BATCH_ARCHIVED
        _audit(db, b.id, "SELECTION_BATCH_ARCHIVE", "归档")
        db.commit()
        return _batch_dto(b)


def save_rule(user, batch_id, rule) -> dict:
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        b = _get_batch(db, batch_id)
        if b.status not in (_BATCH_DRAFT, _BATCH_PUBLISHED):
            raise _invalid("仅 DRAFT/PUBLISHED 批次可改规则")
        b.rule_json = json.dumps(rule, ensure_ascii=False) if rule else None
        _audit(db, b.id, "SELECTION_RULE_UPDATE", "保存选课规则")
        db.commit()
        return _batch_dto(b)


# ══════════════ 课程供给 ══════════════

def _course_dto(c) -> dict:
    remain = max(0, (c.capacity or 0) - (c.selected_count or 0))
    return {"selectionCourseId": str(c.id), "batchId": str(c.batch_id),
            "courseId": str(c.course_id), "courseName": c.course_name,
            "teachingTaskId": str(c.teaching_task_id) if c.teaching_task_id else None,
            "teacherKey": c.teacher_key, "teacherName": c.teacher_name,
            "credit": float(c.credit) if c.credit is not None else None,
            "capacity": c.capacity, "minCapacity": c.min_capacity,
            "selectedCount": c.selected_count, "remain": remain, "status": c.status}


def _get_course(db, course_id):
    from app.models import AaSelectionCourse
    c = db.query(AaSelectionCourse).filter(
        AaSelectionCourse.id == course_id, AaSelectionCourse.tenant_id == _tid(),
        AaSelectionCourse.is_deleted.is_(False)).first()
    if not c:
        raise not_found("可选课程供给项不存在")
    return c


def add_course(user, batch_id, body) -> dict:
    from app.models import AaCourse, AaSelectionCourse, AaTeachingTask
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        b = _get_batch(db, batch_id)
        if b.status not in (_BATCH_DRAFT, _BATCH_PUBLISHED):
            raise _invalid("仅 DRAFT/PUBLISHED 批次可增课程")
        cid = int(body.courseId)
        course = db.query(AaCourse).filter(
            AaCourse.id == cid, AaCourse.tenant_id == _tid()).first()
        if not course:
            raise not_found("课程不存在")
        tt_id = int(body.teachingTaskId) if getattr(body, "teachingTaskId", None) else None
        tkey = tname = None
        if tt_id:
            tt = db.query(AaTeachingTask).filter(
                AaTeachingTask.id == tt_id, AaTeachingTask.tenant_id == _tid()).first()
            if tt:
                tkey, tname = tt.teacher_key, tt.teacher_name
        dup = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.tenant_id == _tid(), AaSelectionCourse.batch_id == b.id,
            AaSelectionCourse.course_id == cid,
            AaSelectionCourse.teaching_task_id == tt_id,
            AaSelectionCourse.is_deleted.is_(False)).first()
        if dup:
            raise AppException("VALIDATION_ERROR", "该课程(教学班)已在本批次")
        c = AaSelectionCourse(
            tenant_id=_tid(), batch_id=b.id, course_id=cid,
            course_name=getattr(course, "course_name", None) or getattr(course, "name", None),
            teaching_task_id=tt_id, teacher_key=tkey, teacher_name=tname,
            credit=getattr(course, "credit", None),
            capacity=int(getattr(body, "capacity", 0) or 0),
            min_capacity=int(getattr(body, "minCapacity", 0) or 0),
            selected_count=0, status=_COURSE_OPEN)
        db.add(c)
        db.flush()
        _audit(db, b.id, "SELECTION_COURSE_ADD", f"增课程 {c.course_name}")
        db.commit()
        return _course_dto(c)


def list_courses(user, batch_id, page=1, page_size=50):
    from app.models import AaSelectionCourse
    with session() as db:
        _ctx(user, db)
        _get_batch(db, batch_id)
        rows = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.batch_id == batch_id, AaSelectionCourse.tenant_id == _tid(),
            AaSelectionCourse.is_deleted.is_(False)).order_by(AaSelectionCourse.id).all()
        total = len(rows)
        return [_course_dto(c) for c in rows[(page - 1) * page_size: page * page_size]], total


def update_course(user, course_id, body) -> dict:
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        c = _get_course(db, course_id)
        b = _get_batch(db, c.batch_id)
        if b.status in (_BATCH_LOCKED, _BATCH_ARCHIVED):
            raise _invalid("批次已锁定，不可改课程容量/规则")
        if getattr(body, "capacity", None) is not None:
            cap = int(body.capacity)
            if cap < (c.selected_count or 0):
                raise AppException("VALIDATION_ERROR", f"容量不可小于已选人数 {c.selected_count}")
            c.capacity = cap
        if getattr(body, "minCapacity", None) is not None:
            c.min_capacity = int(body.minCapacity)
        _audit(db, b.id, "SELECTION_COURSE_UPDATE", f"改课程 {c.course_name} 容量/下限")
        db.commit()
        return _course_dto(c)


def cancel_course(user, course_id) -> dict:
    """人工取消开课（人数不足）：课程 COURSE_CANCELLED，其 SELECTED 记录批量置 COURSE_CANCELLED（幂等）。"""
    from app.models import AaSelectionRecord
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        c = _get_course(db, course_id)
        b = _get_batch(db, c.batch_id)
        if b.status != _BATCH_CLOSED:
            raise _invalid("仅 CLOSED 批次可取消低人数课程")
        if c.status == _COURSE_CANCELLED:
            return _course_dto(c)
        c.status = _COURSE_CANCELLED
        db.query(AaSelectionRecord).filter(
            AaSelectionRecord.selection_course_id == c.id, AaSelectionRecord.tenant_id == _tid(),
            AaSelectionRecord.status == _REC_SELECTED).update(
            {AaSelectionRecord.status: _REC_COURSE_CANCELLED}, synchronize_session=False)
        _audit(db, b.id, "SELECTION_COURSE_CANCEL", f"取消开课 {c.course_name}(人数不足)")
        db.commit()
        return _course_dto(c)


# ══════════════ 学生选课/退课 ══════════════

def _student_from_token():
    ctx = get_current_user_ctx() or {}
    sid = ctx.get("studentId") or ctx.get("userId")
    return ctx, sid


def _load_student(db, student_no=None, student_id=None):
    from app.models import StudentProfile
    q = db.query(StudentProfile).filter(StudentProfile.tenant_id == _tid(),
                                        StudentProfile.is_deleted.is_(False))
    if student_no:
        q = q.filter(StudentProfile.student_no == student_no)
    elif student_id and str(student_id).isdigit():
        q = q.filter(StudentProfile.id == int(student_id))
    return q.first()


def student_courses(user, batch_id=None):
    """学生端：OPEN 批次可选课程 + 实时余量。"""
    from app.models import AaSelectionBatch, AaSelectionCourse
    with session() as db:
        q = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.tenant_id == _tid(), AaSelectionBatch.status == _BATCH_OPEN,
            AaSelectionBatch.is_deleted.is_(False))
        if batch_id:
            q = q.filter(AaSelectionBatch.id == int(batch_id))
        batches = q.all()
        out = []
        for b in batches:
            courses = db.query(AaSelectionCourse).filter(
                AaSelectionCourse.batch_id == b.id, AaSelectionCourse.tenant_id == _tid(),
                AaSelectionCourse.status == _COURSE_OPEN,
                AaSelectionCourse.is_deleted.is_(False)).all()
            out.append({"batch": _batch_dto(b), "courses": [_course_dto(c) for c in courses]})
        return out


def _passed_course_names(db, student):
    """学生已通过(PASSED)的课程名集合（用于④先修/⑧重修判定）。"""
    from app.models import AcademicGrade, AcademicStudent
    acad = db.query(AcademicStudent).filter(AcademicStudent.tenant_id == _tid(),
                                            AcademicStudent.student_id == student.id).first()
    if not acad:
        return set()
    rows = db.query(AcademicGrade).filter(AcademicGrade.tenant_id == _tid(),
                                          AcademicGrade.acad_student_id == acad.id,
                                          AcademicGrade.pass_status == "PASSED",
                                          AcademicGrade.record_status == "ACTIVE").all()
    return {r.course_name for r in rows}


def _task_slots(db, teaching_task_id):
    """教学任务在已发布课表中的时段（供⑤课表冲突检测）。"""
    from app.models import AaScheduleItem
    if not teaching_task_id:
        return []
    rows = db.query(AaScheduleItem).filter(AaScheduleItem.tenant_id == _tid(),
                                           AaScheduleItem.task_id == teaching_task_id,
                                           AaScheduleItem.status == "EFFECTIVE",
                                           AaScheduleItem.is_deleted.is_(False)).all()
    return [(i.weekday, i.slot_no, i.start_week, i.end_week, i.week_parity) for i in rows]


def _validate_enroll(db, batch, course, student, my_records, add_credit):
    """选课八条校验（全部落地；返回 None 表示通过，否则抛异常）。
    ① 批次 OPEN ② 适用范围 ③ 未修过(本批次重复) ④ 先修课程 ⑤ 课表时间冲突 ⑥ 学分上限 ⑦ 容量(行锁) ⑧ 重修规则 + SUSPENDED 学籍。"""
    from app.models import AaCourse, AaSelectionCourse
    from app.modules.academic_affairs.services.academic_affairs_schedule_service import _weeks_overlap
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled
    # SUSPENDED/非在籍 → 403
    if not is_enrolled(getattr(student, "student_status", None)):
        raise no_data_scope("当前学籍状态不可选课")
    # ① 批次 OPEN
    if batch.status != _BATCH_OPEN:
        raise _invalid("不在选课时间内")
    # ② 适用范围
    if batch.apply_scope_json:
        try:
            scope = json.loads(batch.apply_scope_json)
        except ValueError:
            scope = {}
        if scope:
            ok_grade = (not scope.get("grades")) or (student.grade in scope["grades"])
            ok_major = (not scope.get("majorIds")) or (str(student.major_id) in [str(x) for x in scope["majorIds"]])
            ok_class = (not scope.get("classIds")) or (str(student.class_id) in [str(x) for x in scope["classIds"]])
            if not (ok_grade and ok_major and ok_class):
                raise AppException("VALIDATION_ERROR", "不在本批次适用范围内")
    # ③ 未修过该课程（同批次内已有 SELECTED/LOCKED 到同 course_id）
    for r in my_records:
        if r.course_id == course.course_id and r.status in (_REC_SELECTED, _REC_LOCKED):
            raise _conflict("已选过该课程")
    passed = _passed_course_names(db, student)
    tb = db.query(AaCourse).filter(AaCourse.id == course.course_id, AaCourse.tenant_id == _tid()).first()
    # ⑧ 重修规则：非重修生已通过该课程不可再选（V1 选课无重修上下文，一律拦已通过课程）
    if tb and tb.course_name in passed:
        raise AppException("VALIDATION_ERROR", "该课程已通过，不可再选（重修请走重修报名）")
    # ④ 先修课程：课程 prerequisite_codes_json 中所有先修课须已通过
    if tb and tb.prerequisite_codes_json:
        try:
            pre_codes = json.loads(tb.prerequisite_codes_json) or []
        except ValueError:
            pre_codes = []
        if pre_codes:
            pre_names = {c.course_name for c in db.query(AaCourse).filter(
                AaCourse.tenant_id == _tid(), AaCourse.course_code.in_([str(x) for x in pre_codes])).all()}
            missing = pre_names - passed
            if missing:
                raise AppException("VALIDATION_ERROR", f"未满足先修课程要求：{', '.join(sorted(missing))}")
    # ⑤ 课表时间冲突：目标课程时段 vs 本批次已选课程时段
    target_slots = _task_slots(db, course.teaching_task_id)
    if target_slots:
        sel_course_ids = [r.selection_course_id for r in my_records if r.status in (_REC_SELECTED, _REC_LOCKED)]
        if sel_course_ids:
            my_tasks = db.query(AaSelectionCourse.teaching_task_id).filter(
                AaSelectionCourse.id.in_(sel_course_ids), AaSelectionCourse.tenant_id == _tid()).all()
            for (tt_id,) in my_tasks:
                for (w1, s1, sw1, ew1, p1) in _task_slots(db, tt_id):
                    for (w2, s2, sw2, ew2, p2) in target_slots:
                        if w1 == w2 and s1 == s2 and _weeks_overlap(sw1, ew1, p1, sw2, ew2, p2):
                            raise _conflict(f"与已选课程上课时间冲突（周{w1}第{s1}节）")
    # ⑥ 学分上限
    max_credits = _rule(db, batch, "maxCredits", 0)
    if max_credits and max_credits > 0:
        cur = sum(float(r.credit or 0) for r in my_records if r.status in (_REC_SELECTED, _REC_LOCKED))
        if cur + add_credit > float(max_credits):
            raise AppException("VALIDATION_ERROR", f"超过本批次选课学分上限 {max_credits}")
    # ⑦ 容量在 enroll() 内以行锁原子扣减
    return None


def student_enroll(user, body) -> dict:
    """学生选课：八条校验 + 行锁原子扣减防超卖。复用同一行(D-09)。"""
    from app.models import AaSelectionCourse, AaSelectionRecord
    ctx, sid = _student_from_token()
    with session() as db:
        student = _load_student(db, student_no=ctx.get("studentNo"), student_id=sid)
        if not student:
            raise not_found("学生档案不存在")
        c = _get_course(db, int(body.selectionCourseId))
        if c.status != _COURSE_OPEN:
            raise _invalid("该课程不可选（已取消开课）")
        b = _get_batch(db, c.batch_id)
        my = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.batch_id == b.id, AaSelectionRecord.tenant_id == _tid(),
            AaSelectionRecord.student_id == student.id).all()
        _validate_enroll(db, b, c, student, my, float(c.credit or 0))
        # 行锁原子扣减：selected_count < capacity 时 +1，受影响行数=0 → 容量满
        upd = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == c.id, AaSelectionCourse.tenant_id == _tid(),
            AaSelectionCourse.selected_count < AaSelectionCourse.capacity).update(
            {AaSelectionCourse.selected_count: AaSelectionCourse.selected_count + 1},
            synchronize_session=False)
        if not upd:
            db.rollback()
            raise _conflict("课程容量已满")
        # 复用同一行：DROPPED/COURSE_CANCELLED 记录复选
        existing = next((r for r in my if r.selection_course_id == c.id), None)
        if existing:
            existing.status = _REC_SELECTED
            existing.enrolled_at = datetime.utcnow()
            existing.dropped_at = None
            existing.re_enroll = True
            rec = existing
        else:
            rec = AaSelectionRecord(
                tenant_id=_tid(), batch_id=b.id, selection_course_id=c.id,
                course_id=c.course_id, course_name=c.course_name, credit=c.credit,
                student_id=student.id, student_no=student.student_no, student_name=student.real_name,
                enrolled_at=datetime.utcnow(), status=_REC_SELECTED)
            db.add(rec)
        db.flush()
        _audit(db, rec.id, "SELECTION_ENROLL",
               f"选课 {c.course_name}" + ("(复选)" if existing else ""))
        db.commit()
        return {"recordId": str(rec.id), "selectionCourseId": str(c.id),
                "courseName": c.course_name, "status": rec.status}


def student_drop(user, body) -> dict:
    """学生退课：批次 OPEN 且记录 SELECTED；释放容量。"""
    from app.models import AaSelectionCourse, AaSelectionRecord
    ctx, sid = _student_from_token()
    with session() as db:
        student = _load_student(db, student_no=ctx.get("studentNo"), student_id=sid)
        if not student:
            raise not_found("学生档案不存在")
        c = _get_course(db, int(body.selectionCourseId))
        b = _get_batch(db, c.batch_id)
        if b.status != _BATCH_OPEN:
            raise _invalid("不在选课时间内，不可退课")
        rec = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.selection_course_id == c.id, AaSelectionRecord.tenant_id == _tid(),
            AaSelectionRecord.student_id == student.id).first()
        if not rec or rec.status != _REC_SELECTED:
            raise _invalid("无可退课的选课记录")
        rec.status = _REC_DROPPED
        rec.dropped_at = datetime.utcnow()
        db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == c.id, AaSelectionCourse.tenant_id == _tid(),
            AaSelectionCourse.selected_count > 0).update(
            {AaSelectionCourse.selected_count: AaSelectionCourse.selected_count - 1},
            synchronize_session=False)
        _audit(db, rec.id, "SELECTION_DROP", f"退课 {c.course_name}")
        db.commit()
        return {"recordId": str(rec.id), "status": rec.status}


def my_selections(user, batch_id=None):
    """学生查看本人选课记录。"""
    from app.models import AaSelectionRecord
    ctx, sid = _student_from_token()
    with session() as db:
        student = _load_student(db, student_no=ctx.get("studentNo"), student_id=sid)
        if not student:
            return []
        q = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _tid(), AaSelectionRecord.student_id == student.id,
            AaSelectionRecord.is_deleted.is_(False))
        if batch_id:
            q = q.filter(AaSelectionRecord.batch_id == int(batch_id))
        return [_record_dto(r) for r in q.order_by(AaSelectionRecord.id.desc()).all()]


def adjust_record(user, record_id, reason) -> dict:
    """教务处 LOCKED 后人工调整（退课），原因≥5字，留痕。"""
    from app.models import AaSelectionCourse, AaSelectionRecord
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        reason = (reason or "").strip()
        if len(reason) < 5:
            raise AppException("VALIDATION_ERROR", "调整原因必填且不少于5字")
        rec = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.id == record_id, AaSelectionRecord.tenant_id == _tid()).first()
        if not rec:
            raise not_found("选课记录不存在")
        if rec.status != _REC_LOCKED:
            raise _invalid("仅 LOCKED 记录可人工调整")
        rec.status = _REC_DROPPED
        rec.dropped_at = datetime.utcnow()
        rec.adjust_reason = reason
        db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == rec.selection_course_id, AaSelectionCourse.tenant_id == _tid(),
            AaSelectionCourse.selected_count > 0).update(
            {AaSelectionCourse.selected_count: AaSelectionCourse.selected_count - 1},
            synchronize_session=False)
        _audit(db, rec.id, "SELECTION_RECORD_ADJUST", f"人工调整退课：{reason}")
        db.commit()
        return {"recordId": str(rec.id), "status": rec.status}


def _record_dto(r) -> dict:
    return {"recordId": str(r.id), "batchId": str(r.batch_id),
            "selectionCourseId": str(r.selection_course_id),
            "courseId": str(r.course_id) if r.course_id else None, "courseName": r.course_name,
            "credit": float(r.credit) if r.credit is not None else None,
            "studentId": str(r.student_id), "studentNo": r.student_no, "studentName": r.student_name,
            "enrolledAt": _iso(r.enrolled_at), "status": r.status, "reEnroll": r.re_enroll,
            "adjustReason": r.adjust_reason}


# ══════════════ 名单（教师授课关系收敛） / 统计 ══════════════

def course_roster(user, course_id, page=1, page_size=50):
    from app.models import AaSelectionRecord
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_course(db, course_id)
        # 任课教师只读本人授课班：业务关系校验（非行政数据范围，键由 user 派生，非 ctx 属性）
        if ctx.scope_type not in ("COLLEGE", "TENANT_ALL"):
            keys = _derive_keys(user)
            if not c.teacher_key or c.teacher_key not in keys:
                raise no_data_scope("非本人授课教学班，无权查看名单")
        rows = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.selection_course_id == course_id, AaSelectionRecord.tenant_id == _tid(),
            AaSelectionRecord.status.in_([_REC_SELECTED, _REC_LOCKED]),
            AaSelectionRecord.is_deleted.is_(False)).order_by(AaSelectionRecord.student_no).all()
        total = len(rows)
        return [_record_dto(r) for r in rows[(page - 1) * page_size: page * page_size]], total


def batch_stats(user, batch_id) -> dict:
    from app.models import AaSelectionCourse, AaSelectionRecord
    with session() as db:
        _ctx(user, db)
        b = _get_batch(db, batch_id)
        courses = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.batch_id == b.id, AaSelectionCourse.tenant_id == _tid(),
            AaSelectionCourse.is_deleted.is_(False)).all()
        total_cap = sum(c.capacity or 0 for c in courses)
        total_sel = sum(c.selected_count or 0 for c in courses)
        low = [c for c in courses if c.status == _COURSE_OPEN and (c.selected_count or 0) < (c.min_capacity or 0)]
        full = [c for c in courses if (c.selected_count or 0) >= (c.capacity or 0) and (c.capacity or 0) > 0]
        rec_total = db.query(func.count(AaSelectionRecord.id)).filter(
            AaSelectionRecord.batch_id == b.id, AaSelectionRecord.tenant_id == _tid(),
            AaSelectionRecord.status.in_([_REC_SELECTED, _REC_LOCKED])).scalar()
        return {"batchId": str(b.id), "status": b.status, "courseCount": len(courses),
                "totalCapacity": total_cap, "totalSelected": total_sel,
                "fillRate": round(total_sel / total_cap, 4) if total_cap else 0,
                "lowEnrollCount": len(low), "fullCount": len(full),
                "recordCount": rec_total,
                "lowEnrollCourses": [_course_dto(c) for c in low]}


def run_time_tick(user):
    """定时任务触发点：PUBLISHED 且到开选时间→OPEN；OPEN 且到截止时间→CLOSED（幂等，供 cron/调度调用）。"""
    from app.models import AaSelectionBatch
    with session() as db:
        _require_manage_scope(_ctx(user, db))
        now = datetime.utcnow()
        opened = closed = 0
        pub = db.query(AaSelectionBatch).filter(AaSelectionBatch.tenant_id == _tid(),
                                                AaSelectionBatch.status == _BATCH_PUBLISHED,
                                                AaSelectionBatch.select_start_at.isnot(None),
                                                AaSelectionBatch.select_start_at <= now,
                                                AaSelectionBatch.is_deleted.is_(False)).all()
        for b in pub:
            b.status = _BATCH_OPEN
            _audit(db, b.id, "SELECTION_BATCH_AUTO_OPEN", "定时开选")
            opened += 1
        opn = db.query(AaSelectionBatch).filter(AaSelectionBatch.tenant_id == _tid(),
                                                AaSelectionBatch.status == _BATCH_OPEN,
                                                AaSelectionBatch.select_end_at.isnot(None),
                                                AaSelectionBatch.select_end_at <= now,
                                                AaSelectionBatch.is_deleted.is_(False)).all()
        for b in opn:
            b.status = _BATCH_CLOSED
            _audit(db, b.id, "SELECTION_BATCH_AUTO_CLOSE", "定时截止")
            closed += 1
        db.commit()
        return {"opened": opened, "closed": closed, "tickAt": now.isoformat()}


def reselect_guide(user, batch_id):
    """补选指引：CLOSED 批次里被取消开课的课程 + 仍有余量的课程。"""
    from app.models import AaSelectionCourse
    with session() as db:
        _ctx(user, db)
        b = _get_batch(db, batch_id)
        if b.status != _BATCH_CLOSED:
            raise _invalid("仅 CLOSED 批次有补选指引")
        courses = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.batch_id == b.id, AaSelectionCourse.tenant_id == _tid(),
            AaSelectionCourse.is_deleted.is_(False)).all()
        cancelled = [_course_dto(c) for c in courses if c.status == _COURSE_CANCELLED]
        available = [_course_dto(c) for c in courses
                     if c.status == _COURSE_OPEN and (c.selected_count or 0) < (c.capacity or 0)]
        return {"batchId": str(b.id), "cancelledCourses": cancelled, "availableCourses": available}
