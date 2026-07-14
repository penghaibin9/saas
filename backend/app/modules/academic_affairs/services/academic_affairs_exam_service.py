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


def _conflict(msg):
    return AppException("DATA_CONFLICT", msg, http_status=409)


def _invalid(msg):
    return AppException("DATA_CONFLICT", msg, http_status=409)


def _bad(msg):
    return AppException("VALIDATION_ERROR", msg)


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
        if b.status != _B_CONFIRMED:
            raise _invalid("仅 COURSE_CONFIRMED 阶段可编排考场")
        seq = (db.query(AaExamRoom).filter(AaExamRoom.exam_course_id == c.id, AaExamRoom.tenant_id == _tid(),
                                           AaExamRoom.is_deleted.is_(False)).count()) + 1
        r = AaExamRoom(tenant_id=_tid(), exam_course_id=c.id, room_seq=seq,
                       classroom_text=getattr(body, "classroomText", None),
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


# ══════════ 发布 / 归档 ══════════

def publish_batch(user, bid):
    """ARRANGED→PUBLISHED（通知考生+监考教师，此处落一条审计代通知）。V1 允许 CONFIRMED 直接发布前先置 ARRANGED。"""
    with session() as db:
        _require_school(_ctx(user, db))
        b = _get_batch(db, bid)
        if b.status == _B_CONFIRMED:
            b.status = _B_ARRANGED  # 简化：确认后即视为可发布（编排完整性校验留增强）
        if b.status != _B_ARRANGED:
            raise _invalid(f"仅 ARRANGED 批次可发布，当前 {b.status}")
        b.status = _B_PUBLISHED
        b.published_at = datetime.utcnow()
        _audit(db, "EXAM_BATCH", b.id, "EXAM_BATCH_PUBLISH", "发布（通知考生+监考教师）")
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

def _defer_dto(d):
    return {"deferId": str(d.id), "studentId": str(d.student_id), "studentName": d.student_name,
            "examCourseId": str(d.exam_course_id), "courseName": d.course_name,
            "reasonType": d.reason_type, "reason": d.reason, "status": d.status,
            "returnReason": d.return_reason, "applyAt": _iso(d.apply_at)}


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
        # 已开考校验
        if c.exam_date:
            now = datetime.utcnow()
            try:
                exam_dt = datetime.fromisoformat(f"{c.exam_date}T{(c.start_time or '00:00')}:00")
                if now >= exam_dt:
                    raise _bad("考试已开始，不可申请缓考")
            except ValueError:
                pass
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


def defer_review(user, defer_id, action, reason=""):
    """四级审批任一节点：APPROVE 推进/最终 APPROVED；RETURN 退回学生补材料；REJECT 驳回终态。"""
    from app.models import AaDeferredExam
    with session() as db:
        _ctx(user, db)
        d = db.query(AaDeferredExam).filter(AaDeferredExam.id == defer_id, AaDeferredExam.tenant_id == _tid()).first()
        if not d:
            raise not_found("缓考申请不存在")
        if d.status not in _DEFER_CHAIN:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该申请已处理，不可重复审批", http_status=409)
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
    from app.models import AaDeferredExam
    ctx = get_current_user_ctx() or {}
    with session() as db:
        _ctx(user, db)
        q = db.query(AaDeferredExam).filter(AaDeferredExam.tenant_id == _tid(), AaDeferredExam.is_deleted.is_(False))
        if student_only:
            q = q.filter(AaDeferredExam.student_no == ctx.get("studentNo"))
        if status:
            q = q.filter(AaDeferredExam.status == status)
        rows = q.order_by(AaDeferredExam.id.desc()).all()
        total = len(rows)
        return [_defer_dto(d) for d in rows[(page - 1) * page_size: page * page_size]], total


def batch_stats(user, bid):
    from app.models import AaExamCourse, AaExamIncident
    with session() as db:
        _ctx(user, db)
        b = _get_batch(db, bid)
        courses = db.query(AaExamCourse).filter(AaExamCourse.batch_id == b.id, AaExamCourse.tenant_id == _tid(),
                                                AaExamCourse.status != "REMOVED").all()
        cids = [c.id for c in courses]
        incidents = db.query(AaExamIncident).filter(AaExamIncident.tenant_id == _tid(),
                                                    AaExamIncident.exam_course_id.in_(cids or [0]),
                                                    AaExamIncident.status == "ACTIVE").all() if cids else []
        absent = len([i for i in incidents if i.incident_type == "ABSENT"])
        violation = len([i for i in incidents if i.incident_type == "DISCIPLINE_VIOLATION"])
        return {"batchId": str(b.id), "status": b.status, "courseCount": len(courses),
                "confirmedCount": len([c for c in courses if c.status == "CONFIRMED"]),
                "absentCount": absent, "violationCount": violation}
