"""13B-P4 课表（手工/导入双通道，同一三重冲突检测器 + 单双周）。

核心：教师/班级/教室 三重时间冲突检测（对齐正方/强智）。课表项落 t_aa_schedule_item。
批次预发布→发布(通知师生 t_unified_message)→导出水印。三视图(班级/教师/学生)服务端组装。
调停课 V1 基础：发布后作废批次重发运维通道(留审计)，不做流转审批。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.affairs_security import _derive_keys
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

WEEKDAYS = range(1, 8)
PARITIES = ("ALL", "ODD", "EVEN")

# ── 07号卡·自动排课预留：结果导入(Excel)通道表头（不写算法本体，仅结果落地） ──
IMPORT_HEADERS = ["星期(1-7)", "节次", "课程名称", "教师姓名", "教师工号", "班级ID", "班级名称",
                  "教室", "起始周", "结束周", "单双周(ALL/ODD/EVEN)", "教学任务ID"]
IMPORT_REQUIRED = ["星期(1-7)", "节次", "课程名称"]
IMPORT_SAMPLE = [1, 1, "高等数学", "张老师", "T1001", "", "", "A101", 1, 18, "ALL", ""]
IMPORT_NOTES = [
    "本表用于「自动排课预留」结果导入：第三方顾问/算法排好的课表，通过本模板批量导入本系统。",
    "星期取值1-7；节次对应作息节次序号；单双周填 ALL(全周)/ODD(单周)/EVEN(双周)，留空按全周处理。",
    "若填写「教学任务ID」，系统会自动带出该任务的课程/班级/教师，无需重复填写。",
    "导入按行逐条冲突检测（教师/班级/教室三重×单双周相容），冲突行会被跳过并在返回结果中列出，不影响其余行导入。",
    "单批导入不超过 500 行；超出请分批导入。",
]
IMPORT_HEADER_MAP = {
    "星期(1-7)": "weekday", "节次": "slotNo", "课程名称": "courseName", "教师姓名": "teacherName",
    "教师工号": "teacherKey", "班级ID": "classId", "班级名称": "className", "教室": "classroom",
    "起始周": "startWeek", "结束周": "endWeek", "单双周(ALL/ODD/EVEN)": "weekParity", "教学任务ID": "taskId",
}
IMPORT_MAX_ROWS = 500
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def sanitize_import_rows(rows: list[dict]) -> list[dict]:
    """Excel 导入防公式注入：文本字段以 =/+/-/@ 开头时加撇号前缀转义为纯文本；补齐单双周/周次默认值。"""
    out = []
    for row in rows:
        r = dict(row)
        for k in ("courseName", "teacherName", "className", "classroom"):
            v = r.get(k)
            if isinstance(v, str) and v[:1] in _FORMULA_PREFIXES:
                r[k] = "'" + v
        r["weekParity"] = r.get("weekParity") or "ALL"
        r["startWeek"] = r.get("startWeek") or "1"
        r["endWeek"] = r.get("endWeek") or "18"
        out.append(r)
    return out


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


def archive(batch_id, user) -> dict:
    """13号卡·排课归档：学期结束正式归档（PUBLISHED→ARCHIVED）。

    与上面 void_and_reissue（应急作废重排，审计事件 VOID_REISSUE）语义严格区分——本函数是常规流程终点，
    审计事件为 ARCHIVE，不要求填写原因，归档后数据只读，供教务归档包（R7）统一打包消费。"""
    with session() as db:
        from app.models import AaScheduleBatch
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        if b.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布批次可归档")
        b.status = "ARCHIVED"
        _audit(db, "AA_SCHEDULE_BATCH", b.id, "ARCHIVE", "学期结束正式归档")
        db.commit()
        return {"batchId": str(batch_id), "status": "ARCHIVED"}


# ── 05号卡·教室可用时间：按教室名聚合占用查询 ──

def room_view(batch_id, user, classroom) -> dict:
    """按教室名查占用（辅助人工排课选教室，减少反复试错触发409）。教室为自由文本，字符串精确匹配。"""
    from app.models import AaScheduleBatch, AaScheduleItem
    with session() as db:
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        classroom = (classroom or "").strip()
        if not classroom:
            return {"items": [], "note": "请输入教室名称"}
        items = _view(db, batch_id, [AaScheduleItem.classroom_text == classroom])
        return {"items": items, "note": "该教室本批次暂无排课" if not items else ""}


# ── 11号卡·排课调整：预发布阶段教师异议 → 学院教务员定点改排 ──

def teacher_object(batch_id, user, item_id, reason) -> dict:
    """教师对预发布课表本人条目提异议（COURSE scope=本人任教，按 teacher_key 匹配 _derive_keys）。

    批次回退到 DRAFT：本系统当前批次状态机为 DRAFT/PRE_PUBLISHED/PUBLISHED/ARCHIVED 四态（SM-07 冻结的
    SCHEDULING/CONFLICT_PENDING/TEACHER_CONFIRMING 中间态尚未实现，属其余三级卡范围），DRAFT/PRE_PUBLISHED
    均允许条目编辑（见 add_item 状态校验），回 DRAFT 表达"需重新核对预发布"的等价语义。"""
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "异议原因必填且不少于 5 字")
    with session() as db:
        from app.models import AaScheduleBatch, AaScheduleItem
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        if b.status != "PRE_PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅预发布批次可提出异议")
        it = db.get(AaScheduleItem, int(item_id))
        if not it or it.is_deleted or it.tenant_id != _tid() or it.batch_id != b.id:
            raise not_found("排课条目不存在")
        keys = _derive_keys(user)
        if not it.teacher_key or it.teacher_key not in keys:
            raise AppException("NO_DATA_SCOPE", "仅本人课表可提出异议", http_status=403)
        it.objection_status = "PENDING"
        it.objection_reason = reason.strip()
        b.status = "DRAFT"
        _audit(db, "AA_SCHEDULE", it.id, "TEACHER_OBJECT", reason.strip())
        db.commit()
        return {"itemId": str(it.id), "batchId": str(batch_id), "batchStatus": "DRAFT"}


def list_objections(batch_id, user) -> list[dict]:
    """本批次全部待处理教师异议（排课调整页列表）。"""
    from app.models import AaScheduleItem
    with session() as db:
        rows = db.scalars(select(AaScheduleItem).where(
            AaScheduleItem.tenant_id == _tid(), AaScheduleItem.batch_id == int(batch_id),
            AaScheduleItem.objection_status == "PENDING", AaScheduleItem.is_deleted.is_(False))).all()
        return [{**_item_row(x), "objectionReason": x.objection_reason} for x in rows]


def adjust_item(batch_id, item_id, user, weekday, slot_no, classroom, week_parity="ALL") -> dict:
    """学院教务员对被异议条目定点改排：重新三重冲突检测（排除自身）→通过则更新+清除异议标记。"""
    weekday, slot_no = int(weekday), int(slot_no)
    week_parity = week_parity or "ALL"
    if weekday not in WEEKDAYS:
        raise AppException("VALIDATION_ERROR", "星期非法")
    if week_parity not in PARITIES:
        raise AppException("VALIDATION_ERROR", "单双周非法")
    with session() as db:
        from app.models import AaScheduleBatch, AaScheduleItem
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        if b.status not in ("DRAFT", "PRE_PUBLISHED"):
            raise AppException("DATA_CONFLICT", "已发布课表不可直接改（走作废重发）")
        it = db.get(AaScheduleItem, int(item_id))
        if not it or it.is_deleted or it.tenant_id != _tid() or it.batch_id != b.id:
            raise not_found("排课条目不存在")
        conflict = _detect_conflict(db, b.id, weekday, slot_no, it.start_week, it.end_week,
                                    week_parity, it.teacher_key, it.class_id, classroom, exclude_id=it.id)
        if conflict:
            raise AppException("DATA_CONFLICT", f"排课冲突（{conflict['type']}）：{conflict['detail']}")
        it.weekday, it.slot_no, it.classroom_text, it.week_parity = weekday, slot_no, classroom, week_parity
        it.objection_status, it.objection_reason = None, None
        _audit(db, "AA_SCHEDULE", it.id, "ADJUST_ITEM", f"改排至周{weekday}第{slot_no}节")
        db.commit()
        db.refresh(it)
        return _item_row(it)


# ── 三视图 ──

def _item_row(x) -> dict:
    return {"itemId": str(x.id), "courseName": x.course_name or "", "className": x.class_name or "",
            "classId": str(x.class_id or ""), "teacherName": x.teacher_name or "",
            "teacherKey": x.teacher_key or "", "weekday": x.weekday, "slotNo": x.slot_no,
            "startWeek": x.start_week, "endWeek": x.end_week, "weekParity": x.week_parity,
            "classroom": x.classroom_text or "", "status": x.status}


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


def student_view(batch_id, user, student_id):
    """学生课表：服务端按行政班归属推导（不前端拼接）。"""
    from app.models import AaScheduleItem, StudentProfile
    with session() as db:
        s = db.get(StudentProfile, int(student_id))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在")
        if not s.class_id:
            return {"items": [], "note": "学生无行政班归属"}
        return {"items": _view(db, batch_id, [AaScheduleItem.class_id == int(s.class_id)])}


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
