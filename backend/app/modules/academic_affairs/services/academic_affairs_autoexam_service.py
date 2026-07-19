"""自动排考引擎（SM-10 增强层）。

对标商业教务系统（强智《智慧教学服务平台操作手册》第5章考务管理，印刷页 271-350）
的自动排考闭环，还原其三段核心算法行为：

1. 自动编排考场（印刷页 297-302）：按考生数从教室字典自动挑选空闲教室并切分考场，
   最少考场数优先、末考场就小不就大（减少空座浪费）；同教室同时段不可复用。
2. 编排座位号：按学号顺排 / 确定性乱序 / 隔座（奇数座位号，实际容纳减半）。
3. 自动安排监考：按"已监考人次最少者优先"均衡工作量，任课教师回避本课程考场（可关），
   同教师同时段冲突自动绕开；每考场主监考 1 名 + 副监考若干（数量可配）。

设计纪律（与 0085 自动排课同一套）：
- 判定语义同源：时间重叠判断复用 exam_service._time_overlap，与手工指定监考的冲突口径一致。
- 增量语义：已有 ACTIVE 考场的课程整体跳过（无论手工还是自动排的），不重复编排。
- 只动自己排的：清除/重排只删 source=AUTO 的考场（连带座位与监考），人工编排绝不覆盖。
- 不冒充智能：时间未定、无花名册、教室容量不够，一律如实报漏排 + 根因 + 处置建议，不硬塞。

两段式已齐（对齐强智"编排时间→编排考场"）：auto_assign_times 先按日期×场次网格
自动定时（同班同时段不撞/每日限考/教师不撞），auto_arrange 再切考场铺座位配监考；
时间未定的课程在后段仍以 NO_TIME 如实上报，不静默跳过。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.modules.academic_affairs.services.academic_affairs_exam_service import _time_overlap
from app.services.db_service import _tid, session

SEAT_MODES = ("SEQUENTIAL", "RANDOM", "SPACED")

# 排考参数（复用 t_aa_schedule_rule 通用规则表，EXAM_ 前缀区分；batch_id 存考试批次 id）
RULE_KEYS = {
    "EXAM_SEAT_MODE": "座位模式 SEQUENTIAL 按学号 / RANDOM 乱序 / SPACED 隔座（默认 SEQUENTIAL）",
    "EXAM_INVIGILATORS_PER_ROOM": "每考场监考人数（默认 2：1 主监考 + 1 副监考）",
    "EXAM_AVOID_OWN_COURSE": "任课教师回避本课程考场（默认 true）",
}

REASON_LABEL = {
    "NO_TIME": "考试时间未编排（日期/开始时间为空）",
    "NO_ROSTER": "无考生名单（课程未挂班级或班级无在读学生）",
    "NO_ROOM": "教室字典无可用教室（或全部停用/维修/专用）",
    "ROOM_SHORT": "该时段空闲教室总容量不足",
}


def _bad(m):
    return AppException("VALIDATION_ERROR", m)


def _op():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("userId") or ctx.get("loginName") or "")


def _role():
    ctx = get_current_user_ctx() or {}
    return str(ctx.get("currentRoleCode") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_AUTO_EXAM", biz_id=biz_id, action=action,
                             operator=_op(), role_name=_role(), detail=detail[:990],
                             occurred_at=datetime.utcnow()))


def _require_school(user, db):
    ctx = build_affairs_context(user, db)
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可执行自动排考")
    return ctx


# ══════════ 参数 ══════════

def _load_params(db, batch) -> dict:
    from app.models import AaScheduleRule
    rows = db.scalars(select(AaScheduleRule).where(
        AaScheduleRule.tenant_id == _tid(), AaScheduleRule.status == "ENABLED",
        AaScheduleRule.rule_key.like("EXAM_%"), AaScheduleRule.is_deleted.is_(False))).all()
    term_lv, batch_lv = {}, {}
    for r in rows:
        if r.batch_id and int(r.batch_id) == int(batch.id):
            batch_lv[r.rule_key] = r.rule_value_json
        elif r.term_id and batch.term_id and int(r.term_id) == int(batch.term_id) and not r.batch_id:
            term_lv[r.rule_key] = r.rule_value_json
    merged = {**term_lv, **batch_lv}

    def val(key, default):
        raw = merged.get(key)
        if raw is None:
            return default
        try:
            v = json.loads(raw)
        except (ValueError, TypeError):
            return default
        return default if v is None else v

    seat_mode = str(val("EXAM_SEAT_MODE", "SEQUENTIAL") or "SEQUENTIAL").upper()
    if seat_mode not in SEAT_MODES:
        seat_mode = "SEQUENTIAL"
    return {
        "seatMode": seat_mode,
        "invigilatorsPerRoom": max(1, int(val("EXAM_INVIGILATORS_PER_ROOM", 2) or 2)),
        "avoidOwnCourse": bool(val("EXAM_AVOID_OWN_COURSE", True)),
    }


# ══════════ 资源加载 ══════════

def _exam_cap(room) -> int:
    """考试容量：优先考试座位数（隔座物理约束），未设则回退上课容量。"""
    return int(room.exam_seats or room.capacity or 0)


def _eff_cap(room, seat_mode) -> int:
    """有效容纳：隔座模式下实际只能坐一半（奇数座位）。"""
    cap = _exam_cap(room)
    return (cap + 1) // 2 if seat_mode == "SPACED" else cap


def _load_rooms(db) -> list:
    from app.models import AaClassroom
    rows = db.scalars(select(AaClassroom).where(
        AaClassroom.tenant_id == _tid(), AaClassroom.status == "AVAILABLE",
        AaClassroom.is_exclusive.is_(False), AaClassroom.is_deleted.is_(False))).all()
    return [r for r in rows if _exam_cap(r) > 0]


def _room_label(r) -> str:
    return (r.room_name or "").strip() or f"{r.building_name}{r.room_code}"


def _room_busy_index(db) -> dict:
    """{classroom_id: [(date, start, end)]} 全租户既有考场占用（含其它批次），避免跨批次撞教室。"""
    from app.models import AaExamCourse, AaExamRoom
    out = {}
    rows = db.execute(select(AaExamRoom, AaExamCourse).join(
        AaExamCourse, AaExamRoom.exam_course_id == AaExamCourse.id).where(
        AaExamRoom.tenant_id == _tid(), AaExamRoom.status == "ACTIVE",
        AaExamRoom.classroom_id.isnot(None), AaExamRoom.is_deleted.is_(False),
        AaExamCourse.exam_date.isnot(None))).all()
    for room, course in rows:
        out.setdefault(int(room.classroom_id), []).append(
            (course.exam_date, course.start_time, course.end_time))
    return out


def _roster(db, course) -> list:
    """考生名单：课程挂接班级的在读学生，按学号稳定排序。"""
    from app.models import StudentProfile
    if not course.class_id:
        return []
    rows = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.class_id == int(course.class_id),
        StudentProfile.student_status == "NORMAL", StudentProfile.is_deleted.is_(False))).all()
    return sorted(rows, key=lambda s: (s.student_no or "", s.id))


def _teacher_pool(db) -> list:
    """监考教师池：有教学任务的教师（去重）。"""
    from app.models import AaTeachingTask
    rows = db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == _tid(),
        AaTeachingTask.teacher_key.isnot(None),
        AaTeachingTask.status.notin_(("MERGED", "CANCELLED")),
        AaTeachingTask.is_deleted.is_(False))).all()
    seen, pool = set(), []
    for t in rows:
        if t.teacher_key and t.teacher_key not in seen:
            seen.add(t.teacher_key)
            pool.append((t.teacher_key, t.teacher_name or t.teacher_key))
    return pool


def _invigilator_state(db) -> tuple:
    """既有监考负载与占用时段：(load{key:count}, busy{key:[(date,start,end)]})——工作量均衡与冲突绕避的基数。"""
    from app.models import AaExamCourse, AaExamInvigilator, AaExamRoom
    load, busy = {}, {}
    rows = db.execute(select(AaExamInvigilator, AaExamCourse).join(
        AaExamRoom, AaExamInvigilator.exam_room_id == AaExamRoom.id).join(
        AaExamCourse, AaExamRoom.exam_course_id == AaExamCourse.id).where(
        AaExamInvigilator.tenant_id == _tid(), AaExamInvigilator.is_deleted.is_(False))).all()
    for inv, course in rows:
        load[inv.teacher_key] = load.get(inv.teacher_key, 0) + 1
        if course.exam_date:
            busy.setdefault(inv.teacher_key, []).append(
                (course.exam_date, course.start_time, course.end_time))
    return load, busy


def _is_busy(busy, key, d, s, e) -> bool:
    return any(_time_overlap(d, s, e, bd, bs, be) for (bd, bs, be) in busy.get(key, ()))


# ══════════ 考场切分 ══════════

def _split_rooms(free_rooms, n, seat_mode):
    """最少考场数切分：容量降序取到够 → 末考场换成"够用的最小教室"减少空座。
    返回 [(room, 人数)]；容量不足返回 None。"""
    cands = sorted(free_rooms, key=lambda r: (-_eff_cap(r, seat_mode), r.id))
    pick, total = [], 0
    for r in cands:
        if total >= n:
            break
        pick.append(r)
        total += _eff_cap(r, seat_mode)
    if total < n:
        return None
    # 末考场就小不就大
    if pick:
        head = pick[:-1]
        head_cap = sum(_eff_cap(r, seat_mode) for r in head)
        tail_need = n - head_cap
        used = {r.id for r in head}
        smaller = [r for r in free_rooms
                   if r.id not in used and _eff_cap(r, seat_mode) >= tail_need]
        if smaller:
            pick = head + [min(smaller, key=lambda r: (_eff_cap(r, seat_mode), r.id))]
    out, remaining = [], n
    for r in pick:
        take = min(_eff_cap(r, seat_mode), remaining)
        out.append((r, take))
        remaining -= take
    return out


def _seat_numbers(count, seat_mode):
    """座位号序列：顺排 1..k；隔座 1,3,5,...（物理隔开）。"""
    if seat_mode == "SPACED":
        return [2 * i - 1 for i in range(1, count + 1)]
    return list(range(1, count + 1))


def _order_students(students, seat_mode, salt):
    """RANDOM 用确定性扰动（同输入同输出，可复现可审计），其余按学号。"""
    if seat_mode == "RANDOM":
        return sorted(students, key=lambda s: hash((s.id, salt)))
    return students


# ══════════ 主流程 ══════════

def auto_arrange(user, batch_id, dry_run=False) -> dict:
    """批次内自动排考：切考场 → 铺座位 → 配监考。增量：已有考场的课程跳过。"""
    from app.models import (AaExamBatch, AaExamCourse, AaExamInvigilator, AaExamRoom,
                            AaExamRoomStudent)
    with session() as db:
        _require_school(user, db)
        # 历史欠账收口（TOCTOU）：排考增量可重跑（批次停在 COURSE_CONFIRMED，不翻状态），
        # 故并发防护不能靠状态跃迁，改对批次行加 FOR UPDATE 行锁——同批次并发自动排考会
        # 串行：第二个请求阻塞至第一个提交后再读 arranged_ids（已含首轮成果），增量跳过逻辑
        # 自然去重，杜绝"两次都读到空 arranged_ids → 同课程重复建考场/座位/准考证号"。
        # dry_run 不落库，无并发写风险，走普通读避免占锁。
        if dry_run:
            b = db.get(AaExamBatch, int(batch_id))
        else:
            b = db.scalars(select(AaExamBatch).where(
                AaExamBatch.id == int(batch_id)).with_for_update()).first()
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("考试批次不存在")
        if b.status != "COURSE_CONFIRMED":
            raise AppException("DATA_CONFLICT", "仅 COURSE_CONFIRMED 阶段可自动排考", http_status=409)

        params = _load_params(db, b)
        seat_mode = params["seatMode"]
        all_rooms = _load_rooms(db)
        room_busy = _room_busy_index(db)
        pool = _teacher_pool(db)
        inv_load, inv_busy = _invigilator_state(db)

        courses = db.scalars(select(AaExamCourse).where(
            AaExamCourse.tenant_id == _tid(), AaExamCourse.batch_id == int(b.id),
            AaExamCourse.status == "CONFIRMED", AaExamCourse.is_deleted.is_(False))).all()
        courses.sort(key=lambda c: (c.exam_date or "9999", c.start_time or "99", c.id))

        arranged_ids = {r for (r,) in db.execute(select(AaExamRoom.exam_course_id).where(
            AaExamRoom.tenant_id == _tid(), AaExamRoom.status == "ACTIVE",
            AaExamRoom.is_deleted.is_(False))).all()}

        arranged, misses, inv_gaps = [], [], []
        skipped = 0
        for c in courses:
            if int(c.id) in arranged_ids:
                skipped += 1  # 已有考场（手工或上轮自动）→ 增量跳过
                continue
            if not c.exam_date or not c.start_time:
                misses.append(_miss(c, "NO_TIME", "请先在考务控制台为该课程编排考试日期与时间"))
                continue
            students = _roster(db, c)
            if not students:
                misses.append(_miss(c, "NO_ROSTER", "请检查课程是否挂接班级、班级是否有在读学生"))
                continue
            if not all_rooms:
                misses.append(_miss(c, "NO_ROOM", "教室字典无可用教室，请补建教室或恢复停用教室"))
                continue
            free = [r for r in all_rooms
                    if not any(_time_overlap(c.exam_date, c.start_time, c.end_time, d, s, e)
                               for (d, s, e) in room_busy.get(int(r.id), ()))]
            plan = _split_rooms(free, len(students), seat_mode)
            if plan is None:
                free_cap = sum(_eff_cap(r, seat_mode) for r in free)
                misses.append(_miss(
                    c, "ROOM_SHORT",
                    f"考生 {len(students)} 人，该时段空闲教室有效容量合计 {free_cap}，"
                    f"缺口 {len(students) - free_cap}；请错开考试时间或补充教室"))
                continue

            ordered = _order_students(students, seat_mode, int(c.id))
            cursor, admission_idx = 0, 0
            room_rows = []
            for seq, (room, take) in enumerate(plan, start=1):
                chunk = ordered[cursor:cursor + take]
                cursor += take
                er = AaExamRoom(tenant_id=_tid(), exam_course_id=c.id, room_seq=seq,
                                classroom_id=room.id, classroom_text=_room_label(room),
                                capacity=_exam_cap(room), planned_count=len(chunk),
                                seat_mode=seat_mode, source="AUTO", status="ACTIVE")
                db.add(er)
                db.flush()
                seats = _seat_numbers(len(chunk), seat_mode)
                for st, seat in zip(chunk, seats):
                    admission_idx += 1
                    # 准考证号全课程连续编号（跨考场不重号）
                    db.add(AaExamRoomStudent(
                        tenant_id=_tid(), exam_room_id=er.id, exam_course_id=c.id,
                        student_id=st.id, student_no=st.student_no, student_name=st.real_name,
                        seat_no=seat, admission_no=f"{c.id}{admission_idx:04d}",
                        attendance_status="NOT_STARTED"))
                room_busy.setdefault(int(room.id), []).append(
                    (c.exam_date, c.start_time, c.end_time))
                room_rows.append({"roomSeq": seq, "classroom": _room_label(room),
                                  "students": len(chunk), "capacity": _exam_cap(room)})

                # ── 监考：工作量均衡 + 任课回避 + 时段冲突绕避 ──
                got = []
                for k, (tk, tn) in enumerate(sorted(
                        pool, key=lambda p: (inv_load.get(p[0], 0), p[0]))):
                    if len(got) >= params["invigilatorsPerRoom"]:
                        break
                    if params["avoidOwnCourse"] and c.teacher_key and tk == c.teacher_key:
                        continue
                    if any(g[0] == tk for g in got):
                        continue
                    if _is_busy(inv_busy, tk, c.exam_date, c.start_time, c.end_time):
                        continue
                    got.append((tk, tn))
                for k, (tk, tn) in enumerate(got):
                    db.add(AaExamInvigilator(
                        tenant_id=_tid(), exam_room_id=er.id, teacher_key=tk, teacher_name=tn,
                        role=("CHIEF" if k == 0 else "ASSISTANT"), confirm_status="ASSIGNED"))
                    inv_load[tk] = inv_load.get(tk, 0) + 1
                    inv_busy.setdefault(tk, []).append((c.exam_date, c.start_time, c.end_time))
                if len(got) < params["invigilatorsPerRoom"]:
                    inv_gaps.append({"courseId": str(c.id), "courseName": c.course_name,
                                     "roomSeq": seq, "needed": params["invigilatorsPerRoom"],
                                     "assigned": len(got),
                                     "advice": "可监考教师不足（时段冲突/任课回避后无人可派），请手工指定或调整参数"})

            arranged.append({"courseId": str(c.id), "courseName": c.course_name,
                             "className": c.class_name, "students": len(students),
                             "rooms": room_rows})

        if dry_run:
            db.rollback()
        else:
            _audit(db, b.id, "AUTO_EXAM_ARRANGE",
                   f"自动排考 {len(arranged)} 门/漏排 {len(misses)}/监考缺口 {len(inv_gaps)}")
            db.commit()

        return {"batchId": str(b.id), "dryRun": dry_run,
                "arrangedCourses": len(arranged), "skippedCourses": skipped,
                "missedCourses": len(misses), "invigilatorGaps": inv_gaps,
                "teacherPoolSize": len(pool), "roomPoolSize": len(all_rooms),
                "params": params, "arranged": arranged, "misses": misses}


def _miss(c, reason, advice) -> dict:
    return {"courseId": str(c.id), "courseName": c.course_name, "className": c.class_name,
            "examDate": c.exam_date, "startTime": c.start_time,
            "reason": reason, "reasonLabel": REASON_LABEL.get(reason, reason), "detail": advice}


# ══════════ 清除自动排考 ══════════

def clear_auto(user, batch_id) -> dict:
    """只清 source=AUTO 的考场（连带座位与监考），人工编排的考场保留。"""
    from app.models import AaExamBatch, AaExamCourse, AaExamInvigilator, AaExamRoom, AaExamRoomStudent
    with session() as db:
        _require_school(user, db)
        b = db.get(AaExamBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("考试批次不存在")
        if b.status not in ("COURSE_CONFIRMED", "ARRANGED"):
            raise AppException("DATA_CONFLICT", "已发布批次不可清除排考结果", http_status=409)
        course_ids = [cid for (cid,) in db.execute(select(AaExamCourse.id).where(
            AaExamCourse.tenant_id == _tid(), AaExamCourse.batch_id == int(b.id),
            AaExamCourse.is_deleted.is_(False))).all()]
        rooms = db.scalars(select(AaExamRoom).where(
            AaExamRoom.tenant_id == _tid(), AaExamRoom.exam_course_id.in_(course_ids or [0]),
            AaExamRoom.source == "AUTO", AaExamRoom.is_deleted.is_(False))).all()
        room_ids = [r.id for r in rooms]
        n_seats = n_invs = 0
        if room_ids:
            n_seats = db.query(AaExamRoomStudent).filter(
                AaExamRoomStudent.tenant_id == _tid(),
                AaExamRoomStudent.exam_room_id.in_(room_ids)).delete(synchronize_session=False)
            n_invs = db.query(AaExamInvigilator).filter(
                AaExamInvigilator.tenant_id == _tid(),
                AaExamInvigilator.exam_room_id.in_(room_ids)).delete(synchronize_session=False)
        for r in rooms:
            r.is_deleted = True
        _audit(db, b.id, "AUTO_EXAM_CLEAR",
               f"清除自动考场 {len(rooms)} 个/座位 {n_seats}/监考 {n_invs}（人工考场保留）")
        db.commit()
        return {"batchId": str(b.id), "clearedRooms": len(rooms),
                "clearedSeats": n_seats, "clearedInvigilators": n_invs}


# ══════════ 编排时间（强智两段式排考的前段：先定时间，再切考场）══════════

def auto_assign_times(user, batch_id, body, dry_run=False) -> dict:
    """自动编排考试时间：日期范围 × 每日场次 组成时段网格，按考生数降序放置。

    硬约束（对标强智排考参数"考试间隔方式/同专业同时间冲突检查"的班级口径）：
    - 同班级同时段绝不撞；同班级每天最多 maxPerDayPerClass 场（默认 1，防连考）；
    - 同任课教师同时段不撞（否则后段监考回避无解）。
    增量：已定时间的课程不动；放不下的课程 NO_SESSION 如实上报。
    """
    from app.models import AaExamBatch, AaExamCourse
    with session() as db:
        _require_school(user, db)
        b = db.get(AaExamBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("考试批次不存在")
        if b.status != "COURSE_CONFIRMED":
            raise AppException("DATA_CONFLICT", "仅 COURSE_CONFIRMED 阶段可编排时间", http_status=409)

        dates = [d.strip() for d in (getattr(body, "dates", None) or []) if str(d).strip()]
        sessions = getattr(body, "sessions", None) or []
        max_per_day = max(1, int(getattr(body, "maxPerDayPerClass", 1) or 1))
        if not dates or not sessions:
            raise AppException("VALIDATION_ERROR", "考试日期与每日场次必填")
        slots = [(d, s.get("start"), s.get("end")) for d in dates
                 for s in sessions if s.get("start")]
        if not slots:
            raise AppException("VALIDATION_ERROR", "场次时间格式非法（需 start/end）")

        courses = db.scalars(select(AaExamCourse).where(
            AaExamCourse.tenant_id == _tid(), AaExamCourse.batch_id == b.id,
            AaExamCourse.status == "CONFIRMED", AaExamCourse.is_deleted.is_(False))).all()
        # 占用索引：含已定时间的课程（增量绕开）。判撞用时段重叠 _time_overlap，
        # 与排考场/监考阶段同源——精确相等只能挡 start 完全一样的场次，8:00-10:00 与
        # 9:00-11:00 这类 start 不同但重叠的时段会漏判，故按 (date,start,end) 存已占用区间。
        class_busy, class_day, teacher_busy = {}, {}, {}
        for c in courses:
            if c.exam_date and c.start_time:
                if c.class_id:
                    class_busy.setdefault(int(c.class_id), []).append((c.exam_date, c.start_time, c.end_time))
                    class_day[(int(c.class_id), c.exam_date)] = \
                        class_day.get((int(c.class_id), c.exam_date), 0) + 1
                if c.teacher_key:
                    teacher_busy.setdefault(c.teacher_key, []).append((c.exam_date, c.start_time, c.end_time))

        pending = [c for c in courses if not (c.exam_date and c.start_time)]
        pending.sort(key=lambda c: (-(c.expected_students or 0), c.id))
        assigned, misses = [], []
        for c in pending:
            got = None
            for (d, st, et) in slots:
                if c.class_id and any(_time_overlap(d, st, et, bd, bs, be)
                                      for (bd, bs, be) in class_busy.get(int(c.class_id), ())):
                    continue
                if c.class_id and class_day.get((int(c.class_id), d), 0) >= max_per_day:
                    continue
                if c.teacher_key and any(_time_overlap(d, st, et, bd, bs, be)
                                         for (bd, bs, be) in teacher_busy.get(c.teacher_key, ())):
                    continue
                got = (d, st, et)
                break
            if not got:
                misses.append({"courseId": str(c.id), "courseName": c.course_name,
                               "className": c.class_name, "reason": "NO_SESSION",
                               "reasonLabel": "时段不足（班级每日限考/教师冲突约束下无可用场次）",
                               "detail": "请扩大考试日期范围、增加每日场次或放宽每日限考数"})
                continue
            d, st, et = got
            c.exam_date, c.start_time, c.end_time = d, st, et
            if c.class_id:
                class_busy.setdefault(int(c.class_id), []).append((d, st, et))
                class_day[(int(c.class_id), d)] = class_day.get((int(c.class_id), d), 0) + 1
            if c.teacher_key:
                teacher_busy.setdefault(c.teacher_key, []).append((d, st, et))
            assigned.append({"courseId": str(c.id), "courseName": c.course_name,
                             "className": c.class_name, "examDate": d,
                             "startTime": st, "endTime": et})
        if dry_run:
            db.rollback()
        else:
            _audit(db, b.id, "AUTO_EXAM_TIMES",
                   f"定时 {len(assigned)} 门/无可用时段 {len(misses)} 门")
            db.commit()
        return {"batchId": str(b.id), "dryRun": dry_run,
                "assigned": len(assigned), "missed": len(misses),
                "slotsTotal": len(slots), "items": assigned, "misses": misses}
