"""13B 考务管理 service（SM-10）。

批次(6态)→考试课程(3态,学院确认)→考场/座位/监考/巡考编排(冲突检测)→发布→考后异常登记→归档；
缓考(8态四级审批 辅导员→任课教师→学院→教务处)。域级审计走模块自有 t_aa_exam_audit_trail。

复用：AaTeachingTask（考试课程来源）/StudentProfile/AffairsAuditTrail 不用（改用本模块 AaExamAuditTrail）/
build_affairs_context（学院范围）/is_enrolled（缓考前置）/_derive_keys（教师授课/监考关系）。
"""
from __future__ import annotations

import json
import random
from datetime import datetime

from app.core.affairs_security import _derive_keys, build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

# 批次 6 态
_B_DRAFT, _B_CONFIRMED, _B_ARRANGED = "DRAFT", "COURSE_CONFIRMED", "ARRANGED"
_B_PUBLISHED, _B_FINISHED, _B_ARCHIVED = "PUBLISHED", "FINISHED", "ARCHIVED"
# 缓考 8 态
_D_SUBMITTED, _D_COUNSELOR, _D_TEACHER = "SUBMITTED", "COUNSELOR_REVIEW", "TEACHER_CONFIRM"
_D_COLLEGE, _D_FINAL = "COLLEGE_REVIEW", "ACADEMIC_FINAL"
_D_APPROVED, _D_RETURNED, _D_REJECTED = "APPROVED", "RETURNED", "REJECTED"
_DEFER_CHAIN = {_D_COUNSELOR: _D_TEACHER, _D_TEACHER: _D_COLLEGE, _D_COLLEGE: _D_FINAL, _D_FINAL: _D_APPROVED}


def _resolve_classroom_id(db, text):
    """人工建考场只填 classroom_text（纯文本），若不回填 classroom_id，自动排考引擎按
    classroom_id.isnot(None) 建占用索引时会把人工考场整体过滤掉，导致同一间教室被再排给另一场
    考试——这里按教室字典显示名（room_name，或 building_name+room_code）精确匹配回填，匹配不上
    则保持 None（无法感知冲突，与此前行为一致，不是新增风险）。"""
    text = (text or "").strip()
    if not text:
        return None
    from app.models import AaClassroom
    rows = db.query(AaClassroom).filter(AaClassroom.tenant_id == _tid(),
                                        AaClassroom.is_deleted.is_(False)).all()
    for r in rows:
        label = (r.room_name or "").strip() or f"{r.building_name}{r.room_code}"
        if label == text:
            return r.id
    return None


def _conflict(msg):
    return AppException("DATA_CONFLICT", msg, http_status=409)


def _invalid(msg):
    return AppException("DATA_CONFLICT", msg, http_status=409)


def _bad(msg):
    return AppException("VALIDATION_ERROR", msg)


def _archived_readonly():
    return AppException("ARCHIVED_READONLY", "批次已归档，不可写操作", http_status=409)


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, biz_type, biz_id, action, detail="", before="", after=""):
    from app.models import AaExamAuditTrail
    db.add(AaExamAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=biz_id, action=action,
                            operator=_op(), role_name=_role(), detail=detail[:990],
                            before_val=before[:990], after_val=after[:990], occurred_at=datetime.utcnow()))


def _ctx(user, db):
    return build_affairs_context(user, db)


def _is_school(ctx):
    return ctx.scope_type == "TENANT_ALL"


def _require_school(ctx):
    if not _is_school(ctx):
        raise no_data_scope("仅教务处可执行该操作")


# ══════════ 批次 ══════════

def _batch_dto(b):
    return {"batchId": str(b.id), "batchName": b.batch_name, "termId": str(b.term_id) if b.term_id else None,
            "examType": b.exam_type, "examWeekStart": b.exam_week_start, "examWeekEnd": b.exam_week_end,
            "status": b.status, "publishedAt": _iso(b.published_at),
            "collegeScope": json.loads(b.college_scope_json) if b.college_scope_json else None}


def _get_batch(db, bid):
    from app.models import AaExamBatch
    b = db.query(AaExamBatch).filter(AaExamBatch.id == bid, AaExamBatch.tenant_id == _tid(),
                                     AaExamBatch.is_deleted.is_(False)).first()
    if not b:
        raise not_found("考试批次不存在")
    return b


def _ensure_not_archived(b):
    """12号卡「考务归档」统一后置校验：ARCHIVED 批次任何写操作 → 409。供04-09号卡全部写函数复用，避免逐处漏判。"""
    if b.status == _B_ARCHIVED:
        raise _archived_readonly()


def create_batch(user, body):
    from app.models import AaExamBatch
    with session() as db:
        _require_school(_ctx(user, db))
        name = (getattr(body, "batchName", None) or "").strip()
        if not name:
            raise _bad("批次名称必填")
        b = AaExamBatch(tenant_id=_tid(), batch_name=name,
                        term_id=int(body.termId) if getattr(body, "termId", None) else None,
                        exam_type=getattr(body, "examType", None) or "FINAL",
                        exam_week_start=getattr(body, "examWeekStart", None),
                        exam_week_end=getattr(body, "examWeekEnd", None),
                        college_scope_json=json.dumps(body.collegeScope, ensure_ascii=False) if getattr(body, "collegeScope", None) else None,
                        status=_B_DRAFT)
        db.add(b); db.flush()
        _audit(db, "EXAM_BATCH", b.id, "EXAM_BATCH_CREATE", f"建考试批次 {name}")
        db.commit()
        return _batch_dto(b)


def list_batches(user, status=None, page=1, page_size=20):
    from app.models import AaExamBatch
    with session() as db:
        _ctx(user, db)
        q = db.query(AaExamBatch).filter(AaExamBatch.tenant_id == _tid(), AaExamBatch.is_deleted.is_(False))
        if status:
            q = q.filter(AaExamBatch.status == status)
        rows = q.order_by(AaExamBatch.id.desc()).all()
        total = len(rows)
        return [_batch_dto(b) for b in rows[(page - 1) * page_size: page * page_size]], total


def get_batch(user, bid):
    with session() as db:
        _ctx(user, db)
        return _batch_dto(_get_batch(db, bid))


def add_exam_course(user, bid, body):
    """从教学任务带出考试课程（V1：按 teachingTaskId 手工圈定）。"""
    from app.models import AaExamCourse, AaTeachingTask, AaTeachingTaskBatch
    with session() as db:
        ctx = _ctx(user, db)
        _require_school(ctx)  # 圈课由教务处发起
        b = _get_batch(db, bid)
        if b.status != _B_DRAFT:
            raise _invalid("仅 DRAFT 批次可圈定课程")
        tt_id = int(body.teachingTaskId)
        tt = db.query(AaTeachingTask).filter(AaTeachingTask.id == tt_id, AaTeachingTask.tenant_id == _tid()).first()
        if not tt:
            raise not_found("教学任务不存在")
        # college_id 来自教学任务批次（施工卡 D-09：范围过滤冗余落 college_id）
        ttb = db.query(AaTeachingTaskBatch).filter(AaTeachingTaskBatch.id == tt.batch_id,
                                                   AaTeachingTaskBatch.tenant_id == _tid()).first()
        college_id = ttb.college_id if ttb else None
        dup = db.query(AaExamCourse).filter(AaExamCourse.tenant_id == _tid(), AaExamCourse.batch_id == b.id,
                                            AaExamCourse.teaching_task_id == tt_id,
                                            AaExamCourse.is_deleted.is_(False)).first()
        if dup:
            raise _bad("该教学任务已在本批次")
        c = AaExamCourse(tenant_id=_tid(), batch_id=b.id, teaching_task_id=tt_id,
                         course_id=getattr(tt, "course_id", None),
                         course_name=getattr(tt, "course_name", None),
                         class_id=getattr(tt, "class_id", None),
                         class_name=getattr(tt, "teaching_class_name", None),
                         college_id=college_id,
                         teacher_key=getattr(tt, "teacher_key", None), teacher_name=getattr(tt, "teacher_name", None),
                         status="PENDING_CONFIRM")
        db.add(c); db.flush()
        _audit(db, "EXAM_COURSE", c.id, "EXAM_COURSE_ADD", f"圈定课程 {c.course_name}")
        db.commit()
        return _course_dto(c)


def _course_dto(c):
    return {"examCourseId": str(c.id), "batchId": str(c.batch_id),
            "teachingTaskId": str(c.teaching_task_id) if c.teaching_task_id else None,
            "courseName": c.course_name, "classId": str(c.class_id) if c.class_id else None,
            "className": c.class_name, "collegeId": str(c.college_id) if c.college_id else None,
            "teacherKey": c.teacher_key, "teacherName": c.teacher_name,
            "examDate": c.exam_date, "startTime": c.start_time, "endTime": c.end_time,
            "durationMinutes": c.duration_minutes, "status": c.status}


def _get_course(db, cid):
    from app.models import AaExamCourse
    c = db.query(AaExamCourse).filter(AaExamCourse.id == cid, AaExamCourse.tenant_id == _tid(),
                                      AaExamCourse.is_deleted.is_(False)).first()
    if not c:
        raise not_found("考试课程不存在")
    return c


def _check_college_scope(ctx, college_id):
    """学院教务员按 college_id 收敛（复用 build_affairs_context）。教务处全放行。"""
    if _is_school(ctx):
        return
    allowed = getattr(ctx, "college_ids", None) or set()
    if ctx.scope_type == "COLLEGE" and college_id and int(college_id) in allowed:
        return
    raise no_data_scope("该课程不在您的学院范围内")


def list_courses(user, bid, page=1, page_size=100):
    from app.models import AaExamCourse
    with session() as db:
        ctx = _ctx(user, db)
        _get_batch(db, bid)
        q = db.query(AaExamCourse).filter(AaExamCourse.batch_id == bid, AaExamCourse.tenant_id == _tid(),
                                          AaExamCourse.status != "REMOVED", AaExamCourse.is_deleted.is_(False))
        rows = q.order_by(AaExamCourse.id).all()
        # 学院教务员只看本院
        if not _is_school(ctx):
            allowed = getattr(ctx, "college_ids", None) or set()
            rows = [c for c in rows if c.college_id and int(c.college_id) in allowed]
        total = len(rows)
        return [_course_dto(c) for c in rows[(page - 1) * page_size: page * page_size]], total


def confirm_course(user, cid, action):
    """学院确认/退回考试课程（本学院范围）。"""
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_course(db, cid)
        _check_college_scope(ctx, c.college_id)
        if c.status != "PENDING_CONFIRM":
            raise _invalid("仅待确认课程可操作")
        c.status = "CONFIRMED" if action == "CONFIRM" else "REMOVED"
        _audit(db, "EXAM_COURSE", c.id, "EXAM_COURSE_CONFIRM", f"{action} {c.course_name}")
        db.commit()
        return _course_dto(c)


def set_course_schedule(user, cid, body):
    """设置考试时间/时长。"""
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_course(db, cid)
        _check_college_scope(ctx, c.college_id)
        c.exam_date = getattr(body, "examDate", None) or c.exam_date
        c.start_time = getattr(body, "startTime", None) or c.start_time
        c.end_time = getattr(body, "endTime", None) or c.end_time
        c.duration_minutes = getattr(body, "durationMinutes", None) or c.duration_minutes
        _audit(db, "EXAM_COURSE", c.id, "EXAM_COURSE_SCHEDULE", f"设时间 {c.exam_date} {c.start_time}")
        db.commit()
        return _course_dto(c)


def confirm_batch_courses(user, bid):
    """批次课程全部确认后推进 DRAFT→COURSE_CONFIRMED。"""
    from app.models import AaExamCourse
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status != _B_DRAFT:
            raise _invalid("仅 DRAFT 批次可推进")
        courses = db.query(AaExamCourse).filter(AaExamCourse.batch_id == b.id, AaExamCourse.tenant_id == _tid(),
                                                AaExamCourse.status != "REMOVED", AaExamCourse.is_deleted.is_(False)).all()
        if not courses:
            raise _bad("批次无有效考试课程")
        pend = [c for c in courses if c.status != "CONFIRMED"]
        if pend:
            raise _invalid(f"尚有 {len(pend)} 门课程未确认")
        b.status = _B_CONFIRMED
        _audit(db, "EXAM_BATCH", b.id, "EXAM_BATCH_CONFIRM", "课程确认完成")
        db.commit()
        return _batch_dto(b)


# ══════════ 考场 / 座位 ══════════

def _room_dto(r):
    return {"examRoomId": str(r.id), "examCourseId": str(r.exam_course_id), "roomSeq": r.room_seq,
            "classroomText": r.classroom_text, "capacity": r.capacity, "plannedCount": r.planned_count,
            "seatMode": r.seat_mode, "status": r.status}


def add_room(user, cid, body):
    from app.models import AaExamRoom
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_course(db, cid)
        _check_college_scope(ctx, c.college_id)
        b = _get_batch(db, c.batch_id)
        _ensure_not_archived(b)
        if b.status != _B_CONFIRMED:
            raise _invalid("仅 COURSE_CONFIRMED 阶段可编排考场")
        seq = (db.query(AaExamRoom).filter(AaExamRoom.exam_course_id == c.id, AaExamRoom.tenant_id == _tid(),
                                           AaExamRoom.is_deleted.is_(False)).count()) + 1
        classroom_text = getattr(body, "classroomText", None)
        r = AaExamRoom(tenant_id=_tid(), exam_course_id=c.id, room_seq=seq,
                       classroom_text=classroom_text, classroom_id=_resolve_classroom_id(db, classroom_text),
                       capacity=int(getattr(body, "capacity", 0) or 0),
                       seat_mode=getattr(body, "seatMode", None) or "SEQUENTIAL", status="ACTIVE")
        db.add(r); db.flush()
        _audit(db, "EXAM_ROOM", r.id, "EXAM_ROOM_ADD", f"考场{seq} {r.classroom_text}")
        db.commit()
        return _room_dto(r)


def list_rooms(user, cid):
    from app.models import AaExamRoom
    with session() as db:
        _ctx(user, db)
        rows = db.query(AaExamRoom).filter(AaExamRoom.exam_course_id == cid, AaExamRoom.tenant_id == _tid(),
                                           AaExamRoom.is_deleted.is_(False)).order_by(AaExamRoom.room_seq).all()
        return [_room_dto(r) for r in rows]


def assign_seats(user, room_id, student_ids):
    """按 seat_mode 一键铺位（SEQUENTIAL 按学号 / RANDOM 随机）。容量校验。"""
    from app.models import AaExamRoom, AaExamRoomStudent, StudentProfile
    with session() as db:
        ctx = _ctx(user, db)
        r = db.query(AaExamRoom).filter(AaExamRoom.id == room_id, AaExamRoom.tenant_id == _tid()).first()
        if not r:
            raise not_found("考场不存在")
        c = _get_course(db, r.exam_course_id)
        _check_college_scope(ctx, c.college_id)
        _ensure_not_archived(_get_batch(db, c.batch_id))
        sids = [int(x) for x in student_ids if str(x).isdigit()]
        if len(sids) > r.capacity:
            raise _conflict(f"考生数 {len(sids)} 超过考场容量 {r.capacity}")
        students = db.query(StudentProfile).filter(StudentProfile.tenant_id == _tid(),
                                                   StudentProfile.id.in_(sids)).all() if sids else []
        smap = {s.id: s for s in students}
        ordered = sorted(sids, key=lambda i: (smap[i].student_no if i in smap else str(i)))
        if r.seat_mode == "RANDOM":
            # 用 student_id 派生的确定性顺序（脚本环境禁用 Math.random；此处后端可用 random，但避免不可复现，用排序扰动）
            ordered = sorted(sids, key=lambda i: hash((i, r.id)))
        # 清旧座位
        db.query(AaExamRoomStudent).filter(AaExamRoomStudent.exam_room_id == r.id,
                                           AaExamRoomStudent.tenant_id == _tid()).delete(synchronize_session=False)
        for seat, sid in enumerate(ordered, start=1):
            s = smap.get(sid)
            db.add(AaExamRoomStudent(tenant_id=_tid(), exam_room_id=r.id, exam_course_id=c.id, student_id=sid,
                                     student_no=s.student_no if s else None, student_name=s.real_name if s else None,
                                     seat_no=seat, admission_no=f"{c.id}{seat:04d}", attendance_status="NOT_STARTED"))
        r.planned_count = len(ordered)
        _audit(db, "EXAM_ROOM", r.id, "EXAM_SEAT_ASSIGN", f"{r.seat_mode} 铺位 {len(ordered)} 人")
        db.commit()
        return {"examRoomId": str(r.id), "seatCount": len(ordered), "seatMode": r.seat_mode}


def room_seats(user, room_id):
    from app.models import AaExamRoomStudent
    with session() as db:
        _ctx(user, db)
        rows = db.query(AaExamRoomStudent).filter(AaExamRoomStudent.exam_room_id == room_id,
                                                  AaExamRoomStudent.tenant_id == _tid()).order_by(AaExamRoomStudent.seat_no).all()
        return [{"seatNo": s.seat_no, "studentId": str(s.student_id), "studentNo": s.student_no,
                 "studentName": s.student_name, "admissionNo": s.admission_no,
                 "attendanceStatus": s.attendance_status} for s in rows]


# ══════════ 监考（冲突检测）══════════

def _course_time(db, exam_course_id):
    c = _get_course(db, exam_course_id)
    return c.exam_date, c.start_time, c.end_time


def _time_overlap(d1, s1, e1, d2, s2, e2):
    if not d1 or not d2 or d1 != d2:
        return False
    s1, e1, s2, e2 = s1 or "", e1 or "", s2 or "", e2 or ""
    return s1 < (e2 or "99:99") and s2 < (e1 or "99:99")


def assign_invigilator(user, room_id, teacher_key, teacher_name, role="ASSISTANT"):
    """指定监考，同教师同时段冲突 → 409。"""
    from app.models import AaExamInvigilator, AaExamRoom
    with session() as db:
        ctx = _ctx(user, db)
        r = db.query(AaExamRoom).filter(AaExamRoom.id == room_id, AaExamRoom.tenant_id == _tid()).first()
        if not r:
            raise not_found("考场不存在")
        c = _get_course(db, r.exam_course_id)
        _check_college_scope(ctx, c.college_id)
        _ensure_not_archived(_get_batch(db, c.batch_id))
        d0, s0, e0 = c.exam_date, c.start_time, c.end_time
        # 该教师已有的所有监考场次时间
        existing = db.query(AaExamInvigilator).filter(AaExamInvigilator.tenant_id == _tid(),
                                                      AaExamInvigilator.teacher_key == teacher_key,
                                                      AaExamInvigilator.is_deleted.is_(False)).all()
        for inv in existing:
            er = db.query(AaExamRoom).filter(AaExamRoom.id == inv.exam_room_id, AaExamRoom.tenant_id == _tid()).first()
            if not er or er.id == r.id:
                continue
            ec = db.query(_course_cls()).filter_by(id=er.exam_course_id, tenant_id=_tid()).first()
            if ec and _time_overlap(d0, s0, e0, ec.exam_date, ec.start_time, ec.end_time):
                raise _conflict(f"教师 {teacher_name or teacher_key} 该时段已有监考安排（冲突）")
        dup = db.query(AaExamInvigilator).filter(AaExamInvigilator.tenant_id == _tid(),
                                                 AaExamInvigilator.exam_room_id == r.id,
                                                 AaExamInvigilator.teacher_key == teacher_key,
                                                 AaExamInvigilator.is_deleted.is_(False)).first()
        if dup:
            raise _bad("该教师已在本考场监考")
        inv = AaExamInvigilator(tenant_id=_tid(), exam_room_id=r.id, teacher_key=teacher_key,
                                teacher_name=teacher_name, role=role, confirm_status="ASSIGNED")
        db.add(inv); db.flush()
        _audit(db, "EXAM_INVIGILATOR", inv.id, "EXAM_INVIGILATOR_ADD", f"监考 {teacher_name}")
        db.commit()
        return {"invigilatorId": str(inv.id), "examRoomId": str(r.id), "teacherKey": teacher_key, "role": role}


def _course_cls():
    from app.models import AaExamCourse
    return AaExamCourse


def list_invigilators(user, room_id):
    from app.models import AaExamInvigilator
    with session() as db:
        _ctx(user, db)
        rows = db.query(AaExamInvigilator).filter(AaExamInvigilator.exam_room_id == room_id,
                                                  AaExamInvigilator.tenant_id == _tid(),
                                                  AaExamInvigilator.is_deleted.is_(False)).all()
        return [{"invigilatorId": str(i.id), "teacherKey": i.teacher_key, "teacherName": i.teacher_name,
                 "role": i.role, "confirmStatus": i.confirm_status} for i in rows]


# ══════════ 巡考（同时段冲突检测） ══════════

def assign_patrol(user, batch_id, teacher_key, teacher_name, patrol_date, start_time, end_time, area_scope=None):
    """排巡考，同教师同日时段重叠 → 409（也与该教师监考撞则拒）。"""
    from app.models import AaExamInvigilator, AaExamPatrol, AaExamRoom
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, batch_id)
        _ensure_not_archived(b)
        # 巡考彼此冲突
        existing = db.query(AaExamPatrol).filter(AaExamPatrol.tenant_id == _tid(),
                                                 AaExamPatrol.teacher_key == teacher_key,
                                                 AaExamPatrol.is_deleted.is_(False)).all()
        for p in existing:
            if _time_overlap(patrol_date, start_time, end_time, p.patrol_date, p.start_time, p.end_time):
                raise _conflict(f"教师 {teacher_name or teacher_key} 该时段已有巡考安排（冲突）")
        # 与该教师监考撞（监考时间来自其考场对应课程）
        invs = db.query(AaExamInvigilator).filter(AaExamInvigilator.tenant_id == _tid(),
                                                  AaExamInvigilator.teacher_key == teacher_key,
                                                  AaExamInvigilator.is_deleted.is_(False)).all()
        for inv in invs:
            er = db.query(AaExamRoom).filter(AaExamRoom.id == inv.exam_room_id, AaExamRoom.tenant_id == _tid()).first()
            if not er:
                continue
            ec = db.query(_course_cls()).filter_by(id=er.exam_course_id, tenant_id=_tid()).first()
            if ec and _time_overlap(patrol_date, start_time, end_time, ec.exam_date, ec.start_time, ec.end_time):
                raise _conflict(f"教师 {teacher_name or teacher_key} 该时段有监考任务，不能同时巡考（冲突）")
        p = AaExamPatrol(tenant_id=_tid(), batch_id=b.id, teacher_key=teacher_key, teacher_name=teacher_name,
                         patrol_date=patrol_date, start_time=start_time, end_time=end_time,
                         area_scope_json=area_scope, status="ASSIGNED")
        db.add(p); db.flush()
        _audit(db, "EXAM_PATROL", p.id, "EXAM_PATROL_ADD", f"巡考 {teacher_name}")
        db.commit()
        return {"patrolId": str(p.id), "batchId": str(b.id), "teacherKey": teacher_key}


def list_patrols(user, batch_id):
    from app.models import AaExamPatrol
    with session() as db:
        _ctx(user, db)
        rows = db.query(AaExamPatrol).filter(AaExamPatrol.batch_id == batch_id, AaExamPatrol.tenant_id == _tid(),
                                             AaExamPatrol.is_deleted.is_(False)).all()
        return [{"patrolId": str(p.id), "teacherKey": p.teacher_key, "teacherName": p.teacher_name,
                 "patrolDate": p.patrol_date, "startTime": p.start_time, "endTime": p.end_time,
                 "status": p.status} for p in rows]


# ══════════ 发布 / 归档 ══════════

def _check_arrangement_complete(db, batch_id):
    """发布前编排完整性校验：每个 CONFIRMED 考试课程须有 考场+座位+至少1名监考。返回缺项清单。"""
    from app.models import (AaExamCourse, AaExamInvigilator, AaExamRoom, AaExamRoomStudent)
    courses = db.query(AaExamCourse).filter(AaExamCourse.batch_id == batch_id, AaExamCourse.tenant_id == _tid(),
                                            AaExamCourse.status == "CONFIRMED",
                                            AaExamCourse.is_deleted.is_(False)).all()
    problems = []
    for c in courses:
        rooms = db.query(AaExamRoom).filter(AaExamRoom.exam_course_id == c.id, AaExamRoom.tenant_id == _tid(),
                                            AaExamRoom.status == "ACTIVE", AaExamRoom.is_deleted.is_(False)).all()
        if not rooms:
            problems.append(f"{c.course_name}：无考场")
            continue
        room_ids = [r.id for r in rooms]
        seats = db.query(AaExamRoomStudent).filter(AaExamRoomStudent.exam_room_id.in_(room_ids),
                                                   AaExamRoomStudent.tenant_id == _tid()).count()
        if not seats:
            problems.append(f"{c.course_name}：未铺位")
        invig = db.query(AaExamInvigilator).filter(AaExamInvigilator.exam_room_id.in_(room_ids),
                                                   AaExamInvigilator.tenant_id == _tid(),
                                                   AaExamInvigilator.is_deleted.is_(False)).count()
        if not invig:
            problems.append(f"{c.course_name}：无监考")
    return courses, problems


def _notify_publish(db, batch, courses):
    """发布通知：给考生(座位记录学生)+监考教师各落一条 UnifiedMessage。"""
    from app.models import AaExamInvigilator, AaExamRoom, AaExamRoomStudent, UnifiedMessage
    sent = 0
    for c in courses:
        rooms = db.query(AaExamRoom.id).filter(AaExamRoom.exam_course_id == c.id, AaExamRoom.tenant_id == _tid()).all()
        rids = [r[0] for r in rooms]
        if not rids:
            continue
        for s in db.query(AaExamRoomStudent).filter(AaExamRoomStudent.exam_room_id.in_(rids),
                                                    AaExamRoomStudent.tenant_id == _tid()).all():
            db.add(UnifiedMessage(tenant_id=_tid(), receiver_id=s.student_id, source_module="academic_affairs",
                                  source_biz_id=c.id, title=f"考试通知：{c.course_name}",
                                  content=f"{c.exam_date or ''} {c.start_time or ''} 座位 {s.seat_no} 准考证 {s.admission_no}",
                                  message_type="EXAM_NOTICE", status="UNREAD"))
            sent += 1
    return sent


def publish_batch(user, bid):
    """ARRANGED→PUBLISHED：发布前编排完整性校验（每课程有考场+座位+监考，缺则409），发布后通知考生+监考。"""
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status not in (_B_CONFIRMED, _B_ARRANGED):
            raise _invalid(f"仅 COURSE_CONFIRMED/ARRANGED 批次可发布，当前 {b.status}")
        courses, problems = _check_arrangement_complete(db, b.id)
        if problems:
            raise _invalid("编排不完整，不可发布：" + "；".join(problems[:5]) + ("…" if len(problems) > 5 else ""))
        if not courses:
            raise _bad("批次无已确认考试课程")
        b.status = _B_PUBLISHED
        b.published_at = datetime.utcnow()
        sent = _notify_publish(db, b, courses)
        _audit(db, "EXAM_BATCH", b.id, "EXAM_BATCH_PUBLISH", f"发布，推送 {sent} 条考试通知")
        db.commit()
        return _batch_dto(b)


def finish_batch(user, bid):
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status != _B_PUBLISHED:
            raise _invalid("仅 PUBLISHED 批次可结束考试")
        b.status = _B_FINISHED
        _audit(db, "EXAM_BATCH", b.id, "EXAM_BATCH_FINISH", "考试结束")
        db.commit()
        return _batch_dto(b)


def archive_batch(user, bid):
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status == _B_ARCHIVED:
            return _batch_dto(b)
        if b.status != _B_FINISHED:
            raise _invalid("仅 FINISHED 批次可归档")
        b.status = _B_ARCHIVED
        _audit(db, "EXAM_BATCH", b.id, "EXAM_BATCH_ARCHIVE", "归档")
        db.commit()
        return _batch_dto(b)


# ══════════ 考场异常（缺考触发风险） ══════════

def record_incident(user, body):
    """登记缺考/违纪。批次须 PUBLISHED/FINISHED。同 course+student+type 重复登记走更新（幂等）。缺考置 risk_alert_sent 位。"""
    from app.models import AaExamIncident, AaExamRoomStudent
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_course(db, int(body.examCourseId))
        # 监考教师本场 或 教务处/学院
        if not _is_school(ctx):
            allowed = getattr(ctx, "college_ids", None) or set()
            teacher_keys = _derive_keys(user)
            is_college = ctx.scope_type == "COLLEGE" and c.college_id and int(c.college_id) in allowed
            is_invig = _is_invigilator_of_course(db, c.id, teacher_keys)
            if not (is_college or is_invig):
                raise no_data_scope("非本人监考场次/本学院，无权登记")
        b = _get_batch(db, c.batch_id)
        _ensure_not_archived(b)
        if b.status not in (_B_PUBLISHED, _B_FINISHED):
            raise _invalid("仅发布/结束后可登记考场异常")
        itype = body.incidentType
        sid = int(body.studentId)
        seat = db.query(AaExamRoomStudent).filter(AaExamRoomStudent.exam_course_id == c.id,
                                                  AaExamRoomStudent.student_id == sid,
                                                  AaExamRoomStudent.tenant_id == _tid()).first()
        exist = db.query(AaExamIncident).filter(AaExamIncident.tenant_id == _tid(),
                                                AaExamIncident.exam_course_id == c.id,
                                                AaExamIncident.student_id == sid,
                                                AaExamIncident.incident_type == itype).first()
        if exist:
            exist.description = getattr(body, "description", None) or exist.description
            exist.status = "ACTIVE"
            inc = exist
        else:
            inc = AaExamIncident(tenant_id=_tid(), exam_room_id=seat.exam_room_id if seat else None,
                                 exam_course_id=c.id, student_id=sid,
                                 student_no=seat.student_no if seat else None,
                                 student_name=seat.student_name if seat else None,
                                 incident_type=itype, description=getattr(body, "description", None),
                                 recorded_by=_op(), recorded_at=datetime.utcnow(),
                                 risk_alert_sent=(itype == "ABSENT"), status="ACTIVE")
            db.add(inc)
        if seat:
            seat.attendance_status = "ABSENT" if itype == "ABSENT" else "DISCIPLINE_VIOLATION"
        db.flush()
        # 缺考真联动学工风险预警：写 AffairsRiskRecord（引用不复制，幂等去重 by source_ref_id）
        if itype == "ABSENT":
            from app.models import AffairsRiskRecord
            dup = db.query(AffairsRiskRecord).filter(AffairsRiskRecord.tenant_id == _tid(),
                                                     AffairsRiskRecord.source == "EXAM_ABSENT",
                                                     AffairsRiskRecord.source_ref_id == inc.id).first()
            if not dup:
                db.add(AffairsRiskRecord(tenant_id=_tid(), student_id=sid, source="EXAM_ABSENT",
                                         source_ref_id=inc.id, risk_level="MEDIUM",
                                         title=f"考试缺考：{c.course_name or '课程'}",
                                         detail=f"批次 {b.batch_name} 课程 {c.course_name} 缺考，需辅导员跟进",
                                         status="NEW"))
                inc.risk_alert_sent = True
        _audit(db, "EXAM_INCIDENT", inc.id, "EXAM_INCIDENT_RECORD", f"{itype} 学生{sid}")
        db.commit()
        return {"incidentId": str(inc.id), "incidentType": itype, "riskAlertSent": inc.risk_alert_sent}


def _is_invigilator_of_course(db, exam_course_id, teacher_keys):
    from app.models import AaExamInvigilator, AaExamRoom
    rooms = db.query(AaExamRoom.id).filter(AaExamRoom.exam_course_id == exam_course_id,
                                           AaExamRoom.tenant_id == _tid()).all()
    rids = [r[0] for r in rooms]
    if not rids:
        return False
    q = db.query(AaExamInvigilator).filter(AaExamInvigilator.tenant_id == _tid(),
                                           AaExamInvigilator.exam_room_id.in_(rids),
                                           AaExamInvigilator.teacher_key.in_(list(teacher_keys) or [""])).first()
    return q is not None


def list_incidents(user, batch_id=None, page=1, page_size=50):
    from app.models import AaExamCourse, AaExamIncident
    with session() as db:
        _ctx(user, db)
        q = db.query(AaExamIncident).filter(AaExamIncident.tenant_id == _tid(),
                                            AaExamIncident.status == "ACTIVE")
        if batch_id:
            cids = [c[0] for c in db.query(AaExamCourse.id).filter(AaExamCourse.batch_id == int(batch_id),
                                                                   AaExamCourse.tenant_id == _tid()).all()]
            q = q.filter(AaExamIncident.exam_course_id.in_(cids or [0]))
        rows = q.order_by(AaExamIncident.id.desc()).all()
        total = len(rows)
        return [{"incidentId": str(i.id), "examCourseId": str(i.exam_course_id), "studentId": str(i.student_id),
                 "studentName": i.student_name, "incidentType": i.incident_type, "description": i.description,
                 "status": i.status} for i in rows[(page - 1) * page_size: page * page_size]], total


# ══════════ 缓考（8 态四级审批） ══════════

def my_exam_schedule(user, student_id) -> dict:
    """学生本人考试安排：已发布考试课程 + 本人考场座位/准考证。"""
    from app.models import AaExamBatch, AaExamCourse, AaExamRoom, AaExamRoomStudent
    with session() as db:
        _ctx(user, db)
        seats = db.query(AaExamRoomStudent).filter(
            AaExamRoomStudent.tenant_id == _tid(),
            AaExamRoomStudent.student_id == int(student_id),
            AaExamRoomStudent.is_deleted.is_(False),
        ).order_by(AaExamRoomStudent.id.desc()).all()
        if not seats:
            return {"hasData": False, "items": [], "note": "暂无已发布的个人考试安排"}
        items = []
        for s in seats:
            c = db.get(AaExamCourse, s.exam_course_id)
            if not c or c.is_deleted or c.tenant_id != _tid():
                continue
            b = db.get(AaExamBatch, c.batch_id) if c.batch_id else None
            # 仅已发布批次对学生可见（DRAFT/排考中不露）
            if b and (b.status or "") not in ("PUBLISHED", "CLOSED", "ARCHIVED"):
                continue
            room = db.get(AaExamRoom, s.exam_room_id)
            items.append({
                "examCourseId": str(c.id),
                "courseName": c.course_name or "",
                "className": c.class_name or "",
                "examDate": c.exam_date or "",
                "startTime": c.start_time or "",
                "endTime": c.end_time or "",
                "classroom": (room.classroom_text if room else "") or "",
                "seatNo": s.seat_no,
                "admissionNo": s.admission_no or "",
                "batchName": (b.batch_name if b else "") or "",
                "status": c.status or "",
            })
        return {"hasData": bool(items), "items": items, "total": len(items),
                "note": "" if items else "暂无已发布的个人考试安排"}


def _defer_dto(d):
    return {"deferId": str(d.id), "studentId": str(d.student_id), "studentName": d.student_name,
            "examCourseId": str(d.exam_course_id), "courseName": d.course_name,
            "reasonType": d.reason_type, "reason": d.reason, "status": d.status,
            "returnReason": d.return_reason, "applyAt": _iso(d.apply_at)}


def _exam_started(c):
    """课程是否已开考（exam_date+start_time 已过）。日期格式异常时保守判为未开考。"""
    if not c.exam_date:
        return False
    try:
        exam_dt = datetime.fromisoformat(f"{c.exam_date}T{(c.start_time or '00:00')}:00")
        return datetime.utcnow() >= exam_dt
    except ValueError:
        return False


def my_deferrable_courses(user, student_id):
    """本人已排考且未开考的考试课程（供学生小程序缓考申请选择，不展示完整考试安排/座位）。"""
    from app.models import AaDeferredExam, AaExamCourse, AaExamRoomStudent
    with session() as db:
        seats = db.query(AaExamRoomStudent.exam_course_id).filter(
            AaExamRoomStudent.tenant_id == _tid(), AaExamRoomStudent.student_id == student_id).distinct().all()
        cids = [c[0] for c in seats]
        if not cids:
            return []
        courses = db.query(AaExamCourse).filter(AaExamCourse.id.in_(cids), AaExamCourse.tenant_id == _tid(),
                                                 AaExamCourse.status != "REMOVED", AaExamCourse.is_deleted.is_(False)).all()
        active_defers = {d.exam_course_id for d in db.query(AaDeferredExam).filter(
            AaDeferredExam.tenant_id == _tid(), AaDeferredExam.student_id == student_id,
            AaDeferredExam.status.notin_([_D_REJECTED, _D_APPROVED]), AaDeferredExam.is_deleted.is_(False)).all()}
        return [{"examCourseId": str(c.id), "courseName": c.course_name, "examDate": c.exam_date,
                 "startTime": c.start_time, "endTime": c.end_time, "hasActiveDefer": c.id in active_defers}
                for c in courses if not _exam_started(c)]


def defer_apply(user, body):
    """学生申请缓考：目标课程未开考；无未终态记录。"""
    from app.models import AaDeferredExam, StudentProfile
    ctx = get_current_user_ctx() or {}
    with session() as db:
        s = db.query(StudentProfile).filter(StudentProfile.tenant_id == _tid(),
                                            StudentProfile.student_no == ctx.get("studentNo")).first()
        if not s:
            raise not_found("学生档案不存在")
        c = _get_course(db, int(body.examCourseId))
        if _exam_started(c):
            raise _bad("考试已开始，不可申请缓考")
        act = db.query(AaDeferredExam).filter(AaDeferredExam.tenant_id == _tid(),
                                              AaDeferredExam.student_id == s.id,
                                              AaDeferredExam.exam_course_id == c.id,
                                              AaDeferredExam.status.notin_([_D_REJECTED, _D_APPROVED]),
                                              AaDeferredExam.is_deleted.is_(False)).first()
        if act:
            raise _conflict("已有进行中的缓考申请")
        d = AaDeferredExam(tenant_id=_tid(), student_id=s.id, student_no=s.student_no, student_name=s.real_name,
                           exam_course_id=c.id, course_name=c.course_name,
                           reason_type=getattr(body, "reasonType", None), reason=getattr(body, "reason", None),
                           apply_at=datetime.utcnow(), current_node="COUNSELOR", status=_D_COUNSELOR)
        db.add(d); db.flush()
        _audit(db, "DEFERRED_EXAM", d.id, "DEFER_APPLY_SUBMIT", f"缓考申请 {c.course_name}")
        db.commit()
        return _defer_dto(d)


_NODE_STATUS = {"COUNSELOR": _D_COUNSELOR, "TEACHER": _D_TEACHER, "COLLEGE": _D_COLLEGE, "ACADEMIC": _D_FINAL}


def _check_defer_scope(user, db, ctx, d):
    """节点级角色+范围收敛（施工包 §9：辅导员限本人所带班级学生/任课教师限本人授课/学院限本学院/教务处全放行）。
    TENANT_ALL（教务处/教务管理员/学校管理员）直接放行，其余角色必须与当前节点匹配且命中真实业务关系，否则 403002。"""
    if _is_school(ctx):
        return
    role = _role()
    status = d.status
    if status == _D_COUNSELOR:
        if role != "COUNSELOR":
            raise no_data_scope("仅辅导员可在该节点审批")
        from app.models import StudentProfile
        stu = db.query(StudentProfile).filter(StudentProfile.id == d.student_id,
                                              StudentProfile.tenant_id == _tid()).first()
        allowed = getattr(ctx, "class_ids", None) or set()
        if not stu or not stu.class_id or int(stu.class_id) not in allowed:
            raise no_data_scope("非本人所带班级学生")
        return
    if status == _D_TEACHER:
        if role != "ACADEMIC_TEACHER":
            raise no_data_scope("仅任课教师可在该节点审批")
        c = _get_course(db, d.exam_course_id)
        if not c.teacher_key or c.teacher_key not in _derive_keys(user):
            raise no_data_scope("非本人授课的考试课程")
        return
    if status == _D_COLLEGE:
        if role != "COLLEGE_ADMIN":
            raise no_data_scope("仅学院教务可在该节点审批")
        c = _get_course(db, d.exam_course_id)
        _check_college_scope(ctx, c.college_id)
        return
    # ACADEMIC_FINAL：仅教务处（TENANT_ALL，已在函数首行放行），其余角色一律拒绝
    raise no_data_scope("仅教务处可执行终审")


def _visible_defer_record(user, db, ctx, d) -> bool:
    """列表可见性判断——与 _check_defer_scope「当前节点是否轮到我审批」是不同维度：
    辅导员/任课教师/学院教务应能看到与本人有真实业务关系的缓考记录（本班学生/本人授课/
    本学院），不局限于记录恰好卡在自己审批节点的那一条，否则历史记录（已终审/已驳回/
    还没到自己节点）会对本该看到的人完全不可见。TENANT_ALL 由调用方另行放行，此处不重复判断。"""
    role = _role()
    if role == "COUNSELOR":
        from app.models import StudentProfile
        stu = db.query(StudentProfile).filter(StudentProfile.id == d.student_id,
                                              StudentProfile.tenant_id == _tid()).first()
        allowed = getattr(ctx, "class_ids", None) or set()
        return bool(stu and stu.class_id and int(stu.class_id) in allowed)
    if role == "ACADEMIC_TEACHER":
        c = _get_course(db, d.exam_course_id)
        return bool(c.teacher_key and c.teacher_key in _derive_keys(user))
    if role == "COLLEGE_ADMIN":
        c = _get_course(db, d.exam_course_id)
        try:
            _check_college_scope(ctx, c.college_id)
            return True
        except AppException:
            return False
    return False


def defer_review(user, defer_id, action, reason=""):
    """四级审批任一节点：APPROVE 推进/最终 APPROVED；RETURN 退回学生补材料；REJECT 驳回终态。"""
    from app.models import AaDeferredExam
    with session() as db:
        ctx = _ctx(user, db)
        d = db.query(AaDeferredExam).filter(AaDeferredExam.id == defer_id, AaDeferredExam.tenant_id == _tid()).first()
        if not d:
            raise not_found("缓考申请不存在")
        if d.status not in _DEFER_CHAIN:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请已处理，不可重复审批", http_status=409)
        _check_defer_scope(user, db, ctx, d)
        if action == "APPROVE":
            d.status = _DEFER_CHAIN[d.status]
            d.current_node = d.status
        elif action == "RETURN":
            reason = (reason or "").strip()
            if len(reason) < 5:
                raise _bad("退回原因必填且不少于5字")
            d.status = _D_RETURNED
            d.return_reason = reason
        elif action == "REJECT":
            d.status = _D_REJECTED
            d.return_reason = (reason or "").strip()
        else:
            raise _bad("非法审批动作")
        _audit(db, "DEFERRED_EXAM", d.id, "DEFER_REVIEW_ACT", f"{action}->{d.status}")
        db.commit()
        return _defer_dto(d)


def defer_resubmit(user, defer_id):
    from app.models import AaDeferredExam
    ctx = get_current_user_ctx() or {}
    with session() as db:
        d = db.query(AaDeferredExam).filter(AaDeferredExam.id == defer_id, AaDeferredExam.tenant_id == _tid()).first()
        if not d:
            raise not_found("缓考申请不存在")
        if str(d.student_no) != str(ctx.get("studentNo")):
            raise no_data_scope("仅本人可重提")
        if d.status != _D_RETURNED:
            raise _invalid("仅退回状态可重提")
        d.status = _D_COUNSELOR
        d.current_node = "COUNSELOR"
        _audit(db, "DEFERRED_EXAM", d.id, "DEFER_RESUBMIT", "补材料重提")
        db.commit()
        return _defer_dto(d)


def defer_list(user, status=None, student_only=False, page=1, page_size=50):
    """缓考列表。修复：非 student_only 模式下此前对 TENANT_ALL 以外角色完全不做范围收敛，
    任意持权限的辅导员/任课教师/学院教务都能看到全校缓考记录（含学生申请理由等敏感信息）。
    现按 _visible_defer_record 的真实业务关系逐条过滤（按班级/授课/学院，与记录当前处于
    哪个审批节点无关，历史/终态记录同样可见），TENANT_ALL 角色不受影响，仍返回全量。"""
    from app.models import AaDeferredExam
    raw_ctx = get_current_user_ctx() or {}
    with session() as db:
        affairs_ctx = _ctx(user, db)
        q = db.query(AaDeferredExam).filter(AaDeferredExam.tenant_id == _tid(), AaDeferredExam.is_deleted.is_(False))
        if student_only:
            q = q.filter(AaDeferredExam.student_no == raw_ctx.get("studentNo"))
        if status:
            q = q.filter(AaDeferredExam.status == status)
        rows = q.order_by(AaDeferredExam.id.desc()).all()
        if not student_only and not _is_school(affairs_ctx):
            rows = [d for d in rows if _visible_defer_record(user, db, affairs_ctx, d)]
        total = len(rows)
        return [_defer_dto(d) for d in rows[(page - 1) * page_size: page * page_size]], total


def _batch_stats_calc(db, b):
    """批次统计核心计算（课程数/已确认数/缺考/违纪），供 batch_stats 与 12号卡归档列表 completenessSummary 复用。"""
    from app.models import AaExamCourse, AaExamIncident
    courses = db.query(AaExamCourse).filter(AaExamCourse.batch_id == b.id, AaExamCourse.tenant_id == _tid(),
                                            AaExamCourse.status != "REMOVED").all()
    cids = [c.id for c in courses]
    incidents = db.query(AaExamIncident).filter(AaExamIncident.tenant_id == _tid(),
                                                AaExamIncident.exam_course_id.in_(cids or [0]),
                                                AaExamIncident.status == "ACTIVE").all() if cids else []
    absent = len([i for i in incidents if i.incident_type == "ABSENT"])
    violation = len([i for i in incidents if i.incident_type == "DISCIPLINE_VIOLATION"])
    return {"courseCount": len(courses), "confirmedCount": len([c for c in courses if c.status == "CONFIRMED"]),
            "absentCount": absent, "violationCount": violation}


def batch_stats(user, bid):
    with session() as db:
        _ctx(user, db)
        b = _get_batch(db, bid)
        return {"batchId": str(b.id), "status": b.status, **_batch_stats_calc(db, b)}


def list_archived_batches(user, term_id=None, college_id=None, page=1, page_size=20):
    """12号卡「考务归档」只读列表：仅 ARCHIVED 批次，教务处全校可见，学院教务按本学院有关联考试课程收敛。"""
    from app.models import AaExamBatch, AaExamCourse
    with session() as db:
        ctx = _ctx(user, db)
        q = db.query(AaExamBatch).filter(AaExamBatch.tenant_id == _tid(), AaExamBatch.is_deleted.is_(False),
                                         AaExamBatch.status == _B_ARCHIVED)
        if term_id:
            q = q.filter(AaExamBatch.term_id == int(term_id))
        rows = q.order_by(AaExamBatch.id.desc()).all()
        if not _is_school(ctx):
            allowed = getattr(ctx, "college_ids", None) or set()
            scoped_bids = {bid for (bid,) in db.query(AaExamCourse.batch_id).filter(
                AaExamCourse.tenant_id == _tid(), AaExamCourse.college_id.in_(allowed or [0])).distinct().all()}
            rows = [b for b in rows if b.id in scoped_bids]
        if college_id:
            cid_f = int(college_id)
            scoped2 = {bid for (bid,) in db.query(AaExamCourse.batch_id).filter(
                AaExamCourse.tenant_id == _tid(), AaExamCourse.college_id == cid_f).distinct().all()}
            rows = [b for b in rows if b.id in scoped2]
        total = len(rows)
        out = []
        for b in rows[(page - 1) * page_size: page * page_size]:
            dto = _batch_dto(b)
            dto["archivedAt"] = _iso(getattr(b, "updated_at", None))
            dto["completenessSummary"] = _batch_stats_calc(db, b)
            out.append(dto)
        return out, total
