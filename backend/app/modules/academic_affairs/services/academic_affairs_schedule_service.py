"""13B-P4 课表（手工/导入双通道，同一三重冲突检测器 + 单双周）。

核心：教师/班级/教室 三重时间冲突检测（对齐正方/强智）。课表项落 t_aa_schedule_item。
批次预发布→发布(通知师生 t_unified_message)→导出水印。三视图(班级/教师/学生)服务端组装。
调停课 V1 基础：发布后作废批次重发运维通道(留审计)，不做流转审批。

课表管理 Tier1 R2（班级课表/教师课表/教室课表/课表发布/课表导出）续工新增：
- class_schedule/teacher_schedule/room_schedule：自动取「当前已发布批次」的独立查询入口（区别于既有
  class_view/teacher_view/student_view 需先知道 batchId 的批次内三视图），周次可选过滤 + 数据范围收敛。
- list_publish_records/export_schedule：t_aa_schedule_publish 发布记录 + xlsx 导出（水印+审计）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

WEEKDAYS = range(1, 8)
PARITIES = ("ALL", "ODD", "EVEN")

# 教师/教室课表「广域查看」角色：不受本人/本班收敛（与 academic_affairs_task_service._REVIEW_ROLES 同构，
# 教务域内小工具函数按模块各自持有，不跨文件耦合）。
_REVIEW_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN", "COLLEGE_ADMIN"}


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _user_keys(user) -> set[str]:
    """派生当前用户可能的教师标识键（userId/登录名/姓名），用于「教师课表」按本人授课范围收敛。"""
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
    """发布课表：通知师生（t_unified_message）+ 落发布记录（t_aa_schedule_publish，供「课表发布」历史查询）。"""
    with session() as db:
        from app.models import AaScheduleBatch, AaScheduleItem, AaSchedulePublish, UnifiedMessage
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
        n, _r, uid = _op()
        db.add(AaSchedulePublish(tenant_id=_tid(), batch_id=b.id, term_id=b.term_id, action="PUBLISH",
                                 operator_name=n or uid, notified_count=len(teachers)))
        _audit(db, "AA_SCHEDULE_BATCH", b.id, "PUBLISH", f"teachers={len(teachers)}")
        db.commit()
        return {"batchId": str(batch_id), "status": "PUBLISHED", "notified": len(teachers)}


def void_and_reissue(batch_id, user, reason="") -> dict:
    """调停课 V1 运维通道：作废已发布批次（留审计+发布记录），新批次重排。不做流转审批。"""
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        from app.models import AaScheduleBatch, AaSchedulePublish
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        if b.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布批次可作废重发")
        b.status = "ARCHIVED"
        n, _r, uid = _op()
        db.add(AaSchedulePublish(tenant_id=_tid(), batch_id=b.id, term_id=b.term_id, action="VOID_REISSUE",
                                 operator_name=n or uid, notified_count=0, note=reason.strip()))
        _audit(db, "AA_SCHEDULE_BATCH", b.id, "VOID_REISSUE", reason.strip())
        db.commit()
        return {"batchId": str(batch_id), "status": "ARCHIVED", "note": "已作废，请新建批次重排"}


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


# ═══════════ Tier1 R2：班级/教师/教室独立课表入口 + 发布记录 + 导出 ═══════════
# 与既有 class_view/teacher_view/student_view（需先知道 batchId 的批次内三视图，供「课表批次/排课」页
# 「三视图」下钻用）不同：以下入口面向导航菜单三级页，自动取「当前已发布批次」，无需先选批次。

def _current_published_batch(db, term_id=None):
    """当前已发布批次：优先按学期过滤，取最近一次发布（publish_at desc）。不存在返回 None（页面走空态）。"""
    from app.models import AaScheduleBatch
    conds = [AaScheduleBatch.tenant_id == _tid(), AaScheduleBatch.is_deleted.is_(False),
             AaScheduleBatch.status == "PUBLISHED"]
    if term_id:
        conds.append(AaScheduleBatch.term_id == int(term_id))
    return db.scalars(select(AaScheduleBatch).where(*conds)
                      .order_by(AaScheduleBatch.publish_at.desc(), AaScheduleBatch.id.desc())).first()


def _week_in_range(row: dict, week) -> bool:
    """周次过滤：week 为空恒真；否则须落在 [startWeek,endWeek] 且单双周相容。"""
    if not week:
        return True
    w = int(week)
    if not (int(row["startWeek"]) <= w <= int(row["endWeek"])):
        return False
    p = row["weekParity"]
    if p == "ODD":
        return w % 2 == 1
    if p == "EVEN":
        return w % 2 == 0
    return True  # ALL 或未知值不拦截


def class_schedule(user, class_id, term_id=None, week=None) -> dict:
    """班级课表（/schedule/class/:classId）：教务处/学院教务（本院）/辅导员（本班）；
    数据范围经 build_affairs_context 收敛，越范围 → 403002（NO_DATA_SCOPE）。"""
    from app.models import AaScheduleItem, SchoolClass
    with session() as db:
        cls = db.get(SchoolClass, int(class_id))
        if not cls or cls.is_deleted or cls.tenant_id != _tid():
            raise not_found("班级不存在")
        ctx = build_affairs_context(user, db)
        if ctx.scope_type != "TENANT_ALL":
            allowed = ctx.allowed_class_ids(db)
            if not allowed or int(class_id) not in allowed:
                raise no_data_scope("该班级不在您的数据范围内")
        batch = _current_published_batch(db, term_id)
        if not batch:
            return {"items": [], "batchId": None, "className": cls.class_name,
                    "note": "该班级本学期暂无已发布课表"}
        rows = _view(db, batch.id, [AaScheduleItem.class_id == int(class_id)])
        rows = [r for r in rows if _week_in_range(r, week)]
        return {"items": rows, "batchId": str(batch.id), "className": cls.class_name, "note": ""}


def teacher_schedule(user, teacher_key, term_id=None, week=None) -> dict:
    """教师课表（/schedule/teacher/:teacherKey）：教务处/学院教务可查任意教师；教师本人仅能查看自己
    （teacherKey 与本人 _user_keys 不命中 → 403002）。weeklyHours 为 V1 近似口径：按已排课表项计数，
    单双周场景未按实际周折算（精确工作量口径以「教学任务.weeklyHours」为准，此处仅课表侧粗略参考）。"""
    role = ((user or {}).get("currentRoleCode") or "").upper()
    if role not in _REVIEW_ROLES and teacher_key not in _user_keys(user):
        raise no_data_scope("仅能查看本人课表")
    from app.models import AaScheduleItem
    with session() as db:
        batch = _current_published_batch(db, term_id)
        if not batch:
            return {"items": [], "batchId": None, "weeklyHours": 0, "note": "本学期暂无授课安排"}
        rows = _view(db, batch.id, [AaScheduleItem.teacher_key == teacher_key])
        weekly_hours = len(rows)
        rows = [r for r in rows if _week_in_range(r, week)]
        return {"items": rows, "batchId": str(batch.id), "weeklyHours": weekly_hours, "note": ""}


def room_schedule(user, classroom_id, term_id=None, week=None) -> dict:
    """教室课表（/schedule/room/:classroomId）：教务处/学院教务只读；教室无个人归属不做自身范围收敛。
    classroom_text 为课表项自由文本快照（方案A，不外键化），按教室字典拼装的展示名做精确匹配；
    若手工排课时教室文本与字典不一致（历史数据/自由录入）可能查不全，与教室预约模块同口径、同已知限制。"""
    from app.models import AaClassroom, AaScheduleItem
    with session() as db:
        c = db.get(AaClassroom, int(classroom_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("教室不存在")
        display = f"{c.building_name}{c.room_code}"
        candidates = {display}
        if c.room_name:
            candidates.add(c.room_name)
        batch = _current_published_batch(db, term_id)
        if not batch:
            return {"items": [], "batchId": None, "classroomText": display,
                    "note": "该教室本学期暂无已发布课表"}
        rows = _view(db, batch.id, [AaScheduleItem.classroom_text.in_(list(candidates))])
        rows = [r for r in rows if _week_in_range(r, week)]
        return {"items": rows, "batchId": str(batch.id), "classroomText": display, "note": ""}


def list_publish_records(user, term_id=None, batch_id=None, page=1, page_size=20):
    """课表发布记录（t_aa_schedule_publish）：教务处/学院教务查看发布/作废历史，供「课表发布」页留痕展示。"""
    from app.models import AaSchedulePublish
    with session() as db:
        conds = [AaSchedulePublish.tenant_id == _tid(), AaSchedulePublish.is_deleted.is_(False)]
        if term_id:
            conds.append(AaSchedulePublish.term_id == int(term_id))
        if batch_id:
            conds.append(AaSchedulePublish.batch_id == int(batch_id))
        rows = db.scalars(select(AaSchedulePublish).where(*conds).order_by(AaSchedulePublish.id.desc())).all()
        out = [{"recordId": str(r.id), "batchId": str(r.batch_id), "termId": str(r.term_id or ""),
                "action": r.action, "operatorName": r.operator_name or "", "notifiedCount": r.notified_count or 0,
                "note": r.note or "", "createdAt": _iso(r.created_at)} for r in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


_WEEKDAY_LABEL = {1: "周一", 2: "周二", 3: "周三", 4: "周四", 5: "周五", 6: "周六", 7: "周日"}
_PARITY_LABEL = {"ALL": "全周", "ODD": "单周", "EVEN": "双周"}


def export_schedule(user, scope, identifier, term_id=None, week_start=None, week_end=None, purpose="") -> bytes:
    """课表导出 xlsx（班级/教师/教室三选一；水印+审计，对齐 quality_svc.export_report 同款约定）。"""
    scope = (scope or "").upper()
    if scope not in ("CLASS", "TEACHER", "ROOM"):
        raise AppException("VALIDATION_ERROR", "导出范围仅支持 CLASS/TEACHER/ROOM")
    if not identifier:
        raise AppException("VALIDATION_ERROR", "导出对象必填")
    if not (purpose or "").strip() or len((purpose or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    if scope == "CLASS":
        data = class_schedule(user, identifier, term_id, None)
        sheet_title = f"班级课表-{data.get('className') or identifier}"
    elif scope == "TEACHER":
        data = teacher_schedule(user, identifier, term_id, None)
        sheet_title = f"教师课表-{identifier}"
    else:
        data = room_schedule(user, identifier, term_id, None)
        sheet_title = f"教室课表-{data.get('classroomText') or identifier}"
    rows = data.get("items") or []
    if week_start or week_end:
        ws, we = int(week_start or 1), int(week_end or 52)
        rows = [r for r in rows if not (int(r["endWeek"]) < ws or int(r["startWeek"]) > we)]
    rows = sorted(rows, key=lambda x: (int(x["weekday"]), int(x["slotNo"])))
    data_rows = [[
        _WEEKDAY_LABEL.get(int(r["weekday"]), r["weekday"]), r["slotNo"], r["courseName"], r["className"],
        r["teacherName"], r["classroom"], f"{r['startWeek']}-{r['endWeek']}周",
        _PARITY_LABEL.get(r["weekParity"], r["weekParity"])] for r in rows]
    from app.services.xlsx_util import build_ledger_xlsx
    ctx = get_current_user_ctx() or {}
    watermark = (f"导出人：{ctx.get('realName') or ctx.get('loginName') or '-'}  "
                 f"时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose.strip()}  已脱敏留痕")
    headers = ["星期", "节次", "课程", "班级", "教师", "教室", "起止周", "单双周"]
    content = build_ledger_xlsx(sheet_title, headers, data_rows, watermark=watermark)
    with session() as db:
        _audit(db, "AA_SCHEDULE_EXPORT", None, "EXPORT",
              f"scope={scope} id={identifier} rows={len(data_rows)} purpose={purpose.strip()[:100]}")
        db.commit()
    return content
