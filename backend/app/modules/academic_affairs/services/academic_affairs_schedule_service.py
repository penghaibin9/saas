"""13B-P4 课表（手工/导入双通道，同一三重冲突检测器 + 单双周）。

核心：教师/班级/教室 三重时间冲突检测（对齐正方/强智）。课表项落 t_aa_schedule_item。
批次预发布→发布(通知师生 t_unified_message)→导出水印。三视图(班级/教师/学生)服务端组装。
调停课 V1 基础：发布后作废批次重发运维通道(留审计)，不做流转审批。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

WEEKDAYS = range(1, 8)
PARITIES = ("ALL", "ODD", "EVEN")


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_type, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


# ── 三重冲突检测器（核心）──

def _weeks_overlap(s1, e1, p1, s2, e2, p2) -> bool:
    """周次区间相交 且 单双周相容（ALL 与任何相容；ODD 仅与 ODD/ALL；EVEN 仅与 EVEN/ALL）。"""
    if e1 < s2 or e2 < s1:  # 区间不相交
        return False
    if p1 == "ALL" or p2 == "ALL" or p1 == p2:
        return True
    return False  # ODD vs EVEN 不冲突


def _detect_conflict(db, batch_id, weekday, slot_no, start_week, end_week, parity,
                     teacher_key, class_id, classroom, exclude_id=None):
    """返回冲突描述（None=无冲突）。同批次同星期同节次，教师/班级/教室任一相同且周次相容即冲突。"""
    from app.models import AaScheduleItem
    rows = db.scalars(select(AaScheduleItem).where(
        AaScheduleItem.tenant_id == _tid(), AaScheduleItem.batch_id == int(batch_id),
        AaScheduleItem.weekday == weekday, AaScheduleItem.slot_no == slot_no,
        AaScheduleItem.status == "EFFECTIVE", AaScheduleItem.is_deleted.is_(False))).all()
    for r in rows:
        if exclude_id and r.id == exclude_id:
            continue
        if not _weeks_overlap(start_week, end_week, parity, r.start_week, r.end_week, r.week_parity):
            continue
        if teacher_key and r.teacher_key and r.teacher_key == teacher_key:
            return {"type": "TEACHER", "conflictWith": r.teacher_name or teacher_key,
                    "detail": f"教师 {r.teacher_name or teacher_key} 周{weekday}第{slot_no}节已排 {r.course_name}"}
        if class_id and r.class_id and int(r.class_id) == int(class_id):
            return {"type": "CLASS", "conflictWith": r.class_name or str(class_id),
                    "detail": f"班级 {r.class_name or class_id} 周{weekday}第{slot_no}节已排 {r.course_name}"}
        if classroom and r.classroom_text and r.classroom_text == classroom:
            return {"type": "CLASSROOM", "conflictWith": classroom,
                    "detail": f"教室 {classroom} 周{weekday}第{slot_no}节已被占用"}
    return None


# ── 批次 ──

def create_batch(body, user) -> dict:
    with session() as db:
        from app.models import AaScheduleBatch
        b = AaScheduleBatch(tenant_id=_tid(), term_id=int(body.termId),
                            batch_name=(getattr(body, "batchName", None) or f"学期{body.termId}课表"),
                            college_id=(int(body.collegeId) if getattr(body, "collegeId", None) else None),
                            status="DRAFT")
        db.add(b)
        db.flush()
        _audit(db, "AA_SCHEDULE_BATCH", b.id, "CREATE")
        db.commit()
        db.refresh(b)
        return {"batchId": str(b.id), "batchName": b.batch_name, "status": b.status}


def _item_from(body, task=None):
    return dict(
        task_id=(int(body.taskId) if getattr(body, "taskId", None) else None),
        weekday=int(body.weekday), slot_no=int(body.slotNo),
        start_week=int(getattr(body, "startWeek", 1) or 1),
        end_week=int(getattr(body, "endWeek", 18) or 18),
        parity=(getattr(body, "weekParity", "ALL") or "ALL"),
        classroom=getattr(body, "classroom", None),
    )


def add_item(batch_id, user, body) -> dict:
    """手工排一节课。三重冲突→409。"""
    if int(body.weekday) not in WEEKDAYS:
        raise AppException("VALIDATION_ERROR", "星期非法")
    if (getattr(body, "weekParity", "ALL") or "ALL") not in PARITIES:
        raise AppException("VALIDATION_ERROR", "单双周非法")
    with session() as db:
        from app.models import AaScheduleBatch, AaScheduleItem, AaTeachingTask
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        if b.status not in ("DRAFT", "PRE_PUBLISHED"):
            raise AppException("DATA_CONFLICT", "已发布课表不可直接改（走作废重发）")
        it = _item_from(body)
        # 从教学任务带出 课程/班级/教师
        course_name = class_id = class_name = teacher_key = teacher_name = None
        if it["task_id"]:
            t = db.get(AaTeachingTask, it["task_id"])
            if t:
                course_name, class_id, teacher_key, teacher_name = t.course_name, t.class_id, t.teacher_key, t.teacher_name
        class_id = int(body.classId) if getattr(body, "classId", None) else class_id
        teacher_key = getattr(body, "teacherKey", None) or teacher_key
        teacher_name = getattr(body, "teacherName", None) or teacher_name
        conflict = _detect_conflict(db, b.id, it["weekday"], it["slot_no"], it["start_week"],
                                    it["end_week"], it["parity"], teacher_key, class_id, it["classroom"])
        if conflict:
            raise AppException("DATA_CONFLICT", f"排课冲突（{conflict['type']}）：{conflict['detail']}")
        x = AaScheduleItem(tenant_id=_tid(), batch_id=b.id, task_id=it["task_id"],
                           course_name=course_name or getattr(body, "courseName", None),
                           class_id=class_id, class_name=getattr(body, "className", None),
                           teacher_key=teacher_key, teacher_name=teacher_name,
                           weekday=it["weekday"], slot_no=it["slot_no"], start_week=it["start_week"],
                           end_week=it["end_week"], week_parity=it["parity"],
                           classroom_text=it["classroom"], status="EFFECTIVE")
        db.add(x)
        db.flush()
        _audit(db, "AA_SCHEDULE", x.id, "ADD_ITEM", f"周{it['weekday']}第{it['slot_no']}节")
        db.commit()
        db.refresh(x)
        return _item_row(x)


def import_items(batch_id, user, items) -> dict:
    """导入通道：逐行走同一冲突检测器；返回成功数 + 冲突行清单（不整批回滚，逐行落）。"""
    ok, conflicts = 0, []
    with session() as db:
        from app.models import AaScheduleBatch, AaScheduleItem, AaTeachingTask
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        if b.status not in ("DRAFT", "PRE_PUBLISHED"):
            raise AppException("DATA_CONFLICT", "已发布课表不可导入")
        for idx, row in enumerate(items or []):
            weekday, slot_no = int(row.get("weekday")), int(row.get("slotNo"))
            sw, ew = int(row.get("startWeek", 1)), int(row.get("endWeek", 18))
            parity = row.get("weekParity", "ALL")
            classroom = row.get("classroom")
            task_id = row.get("taskId")
            course_name = class_id = teacher_key = teacher_name = None
            if task_id:
                t = db.get(AaTeachingTask, int(task_id))
                if t:
                    course_name, class_id, teacher_key, teacher_name = t.course_name, t.class_id, t.teacher_key, t.teacher_name
            class_id = row.get("classId") or class_id
            teacher_key = row.get("teacherKey") or teacher_key
            # 无 taskId 的导入行（第三方/Excel 排好）直接携带课程名/教师名/班级名，与手工排课 add_item 一致读取
            course_name = row.get("courseName") or course_name
            teacher_name = row.get("teacherName") or teacher_name
            class_name = row.get("className")
            conflict = _detect_conflict(db, b.id, weekday, slot_no, sw, ew, parity, teacher_key,
                                        class_id, classroom)
            if conflict:
                conflicts.append({"row": idx + 1, **conflict})
                continue
            db.add(AaScheduleItem(tenant_id=_tid(), batch_id=b.id,
                                  task_id=(int(task_id) if task_id else None), course_name=course_name,
                                  class_id=(int(class_id) if class_id else None), class_name=class_name,
                                  teacher_key=teacher_key,
                                  teacher_name=teacher_name, weekday=weekday, slot_no=slot_no,
                                  start_week=sw, end_week=ew, week_parity=parity,
                                  classroom_text=classroom, status="EFFECTIVE"))
            db.flush()  # 立即可见，供同批导入后续行的冲突检测
            ok += 1
        _audit(db, "AA_SCHEDULE_BATCH", b.id, "IMPORT", f"ok={ok},conflict={len(conflicts)}")
        db.commit()
    return {"batchId": str(batch_id), "imported": ok, "conflicts": conflicts}


# ── 发布 / 作废重发 ──

def pre_publish(batch_id, user) -> dict:
    with session() as db:
        from app.models import AaScheduleBatch
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        if b.status != "DRAFT":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅草稿批次可预发布")
        b.status = "PRE_PUBLISHED"
        _audit(db, "AA_SCHEDULE_BATCH", b.id, "PRE_PUBLISH")
        db.commit()
        return {"batchId": str(batch_id), "status": "PRE_PUBLISHED"}


def publish(batch_id, user) -> dict:
    """发布课表：通知师生（t_unified_message）。"""
    with session() as db:
        from app.models import AaScheduleBatch, AaScheduleItem, UnifiedMessage
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        if b.status not in ("DRAFT", "PRE_PUBLISHED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该批次状态不可发布")
        b.status, b.publish_at = "PUBLISHED", datetime.utcnow()
        # 通知涉及的教师（去重）
        teachers = {r.teacher_key for r in db.scalars(select(AaScheduleItem).where(
            AaScheduleItem.tenant_id == _tid(), AaScheduleItem.batch_id == b.id,
            AaScheduleItem.status == "EFFECTIVE", AaScheduleItem.is_deleted.is_(False))).all()
            if r.teacher_key}
        for tk in teachers:
            db.add(UnifiedMessage(tenant_id=_tid(), receiver_id=0, source_module="academic-affairs",
                                  source_biz_id=b.id, title="课表已发布",
                                  content=f"{b.batch_name} 已发布，请查看你的课表", message_type="PUBLISHED_NOTICE",
                                  status="UNREAD"))
        _audit(db, "AA_SCHEDULE_BATCH", b.id, "PUBLISH", f"teachers={len(teachers)}")
        db.commit()
        return {"batchId": str(batch_id), "status": "PUBLISHED", "notified": len(teachers)}


def void_and_reissue(batch_id, user, reason="") -> dict:
    """调停课 V1 运维通道：作废已发布批次（留审计），新批次重排。不做流转审批。"""
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        from app.models import AaScheduleBatch
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        if b.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布批次可作废重发")
        b.status = "ARCHIVED"
        _audit(db, "AA_SCHEDULE_BATCH", b.id, "VOID_REISSUE", reason.strip())
        db.commit()
        return {"batchId": str(batch_id), "status": "ARCHIVED", "note": "已作废，请新建批次重排"}


# ── 三视图 ──

def _item_row(x, source="CLASS_DERIVED", selection_record_id=None) -> dict:
    """source: CLASS_DERIVED(行政班课表推导，既有) / ENROLLED(选课LOCKED并入，10号卡新增值)。
    切换位沿用 `13A-13B-V1不可做与后置能力清单.md:45` 预留设计，前端按 source 区分展示。"""
    return {"itemId": str(x.id), "courseName": x.course_name or "", "className": x.class_name or "",
            "classId": str(x.class_id or ""), "teacherName": x.teacher_name or "",
            "teacherKey": x.teacher_key or "", "weekday": x.weekday, "slotNo": x.slot_no,
            "startWeek": x.start_week, "endWeek": x.end_week, "weekParity": x.week_parity,
            "classroom": x.classroom_text or "", "status": x.status, "source": source,
            "selectionRecordId": str(selection_record_id) if selection_record_id else None}


def _view(db, batch_id, extra_conds):
    from app.models import AaScheduleItem
    rows = db.scalars(select(AaScheduleItem).where(
        AaScheduleItem.tenant_id == _tid(), AaScheduleItem.batch_id == int(batch_id),
        AaScheduleItem.status == "EFFECTIVE", AaScheduleItem.is_deleted.is_(False),
        *extra_conds).order_by(AaScheduleItem.weekday, AaScheduleItem.slot_no)).all()
    return [_item_row(x) for x in rows]


def class_view(batch_id, user, class_id):
    from app.models import AaScheduleItem
    with session() as db:
        return {"items": _view(db, batch_id, [AaScheduleItem.class_id == int(class_id)])}


def teacher_view(batch_id, user, teacher_key):
    from app.models import AaScheduleItem
    with session() as db:
        return {"items": _view(db, batch_id, [AaScheduleItem.teacher_key == teacher_key])}


def _enrolled_items(db, student_id):
    """学生本人选课结果并入课表（10号卡）：批次 LOCKED 后，选课记录关联教学任务在已发布课表中
    的排课项(EFFECTIVE)标记 source=ENROLLED；LOCKED 前不并入（避免展示未定选课结果误导学生）。"""
    from app.models import AaScheduleItem, AaSelectionCourse, AaSelectionRecord
    locked = db.query(AaSelectionRecord).filter(
        AaSelectionRecord.tenant_id == _tid(), AaSelectionRecord.student_id == int(student_id),
        AaSelectionRecord.status == "LOCKED", AaSelectionRecord.is_deleted.is_(False)).all()
    if not locked:
        return []
    course_ids = [r.selection_course_id for r in locked]
    courses = db.query(AaSelectionCourse).filter(
        AaSelectionCourse.id.in_(course_ids), AaSelectionCourse.tenant_id == _tid()).all()
    task_to_record = {c.id: (c.teaching_task_id, next(
        (r.id for r in locked if r.selection_course_id == c.id), None)) for c in courses}
    out = []
    for c in courses:
        tt_id, rec_id = task_to_record.get(c.id, (None, None))
        if not tt_id:
            continue
        rows = db.query(AaScheduleItem).filter(
            AaScheduleItem.tenant_id == _tid(), AaScheduleItem.task_id == tt_id,
            AaScheduleItem.status == "EFFECTIVE", AaScheduleItem.is_deleted.is_(False)).all()
        out.extend(_item_row(x, source="ENROLLED", selection_record_id=rec_id) for x in rows)
    return out


def student_view(batch_id, user, student_id):
    """学生课表：服务端按行政班归属推导（CLASS_DERIVED）+ 本人LOCKED选课结果并入（ENROLLED，10号卡）。"""
    from app.models import AaScheduleItem, StudentProfile
    with session() as db:
        s = db.get(StudentProfile, int(student_id))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在")
        base_items = _view(db, batch_id, [AaScheduleItem.class_id == int(s.class_id)]) if s.class_id else []
        items = base_items + _enrolled_items(db, s.id)
        note = "" if s.class_id else "学生无行政班归属"
        return {"items": items, "note": note}


def list_batches(user, term_id=None, status=None, page=1, page_size=20):
    from app.models import AaScheduleBatch
    with session() as db:
        conds = [AaScheduleBatch.tenant_id == _tid(), AaScheduleBatch.is_deleted.is_(False)]
        if term_id:
            conds.append(AaScheduleBatch.term_id == int(term_id))
        if status:
            conds.append(AaScheduleBatch.status == status)
        rows = db.scalars(select(AaScheduleBatch).where(*conds).order_by(AaScheduleBatch.id.desc())).all()
        out = [{"batchId": str(b.id), "batchName": b.batch_name, "termId": str(b.term_id),
                "status": b.status, "publishAt": _iso(b.publish_at)} for b in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total
