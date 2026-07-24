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

from app.core.affairs_security import _derive_keys, build_affairs_context, no_data_scope
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

# 教师/教室课表「广域查看」角色：不受本人/本班收敛（与 academic_affairs_task_service._REVIEW_ROLES 同构，
# 教务域内小工具函数按模块各自持有，不跨文件耦合）。
_REVIEW_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN", "COLLEGE_ADMIN"}


def _resolve_classroom_id(db, text):
    """人工/导入排课只填 classroom_text（纯文本），若不回填 classroom_id，自动排课引擎的教室占用
    索引（按 classroom_id 建索引）就看不到这些人工课，会把已占用的教室当空闲再排给别的班——
    这里按教室字典的显示名（room_name，或 building_name+room_code）做一次精确匹配，能匹配上就
    回填 classroom_id，让人工课也纳入自动引擎的冲突检测范围；匹配不上则保持 None（无法感知冲突，
    与此前行为一致，不是新增风险）。"""
    text = (text or "").strip()
    if not text:
        return None
    from app.models import AaClassroom
    rows = db.scalars(select(AaClassroom).where(
        AaClassroom.tenant_id == _tid(), AaClassroom.is_deleted.is_(False))).all()
    for r in rows:
        label = (r.room_name or "").strip() or f"{r.building_name}{r.room_code}"
        if label == text:
            return r.id
    return None


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


def _user_keys(user) -> set[str]:
    """派生当前用户的教师标识键（userId/登录名），用于「教师课表」按本人授课范围收敛。

    与 affairs_security._derive_keys 同口径：只认工号族标识，**不含 realName**。
    teacher_schedule() 用本函数做归属校验（`teacher_key not in _user_keys(user)` → 403002），
    姓名一旦入键，同名教师即可传对方工号越权查看其课表。t_aa_schedule_item.teacher_key
    实测存的是工号（如 t_chen_xiaoli），姓名从不作为 teacher_key，故移除姓名不影响本人课表查询。
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
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        guard_term_writable(db, body.termId)  # 归档11卡§6.2：已归档学期不应新建课表批次
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
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        guard_term_writable(db, b.term_id)  # 归档11卡§6.2：已归档学期的课表不应再变更
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
                           classroom_text=it["classroom"], classroom_id=_resolve_classroom_id(db, it["classroom"]),
                           status="EFFECTIVE")
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
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        guard_term_writable(db, b.term_id)  # 归档11卡§6.2：已归档学期的课表不应再导入
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
                                  classroom_text=classroom, classroom_id=_resolve_classroom_id(db, classroom),
                                  status="EFFECTIVE"))
            db.flush()  # 立即可见，供同批导入后续行的冲突检测
            ok += 1
        _audit(db, "AA_SCHEDULE_BATCH", b.id, "IMPORT", f"ok={ok},conflict={len(conflicts)}")
        db.commit()
    return {"batchId": str(batch_id), "imported": ok, "conflicts": conflicts}


# ── 发布 / 作废重发 ──

def pre_publish(batch_id, user) -> dict:
    with session() as db:
        from app.models import AaScheduleBatch
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        guard_term_writable(db, b.term_id)  # 归档11卡§6.2：已归档学期的课表不应再预发布
        if b.status != "DRAFT":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅草稿批次可预发布")
        b.status = "PRE_PUBLISHED"
        _audit(db, "AA_SCHEDULE_BATCH", b.id, "PRE_PUBLISH")
        db.commit()
        return {"batchId": str(batch_id), "status": "PRE_PUBLISHED"}


def publish(batch_id, user) -> dict:
    """发布课表：通知师生（t_unified_message）+ 落发布记录（t_aa_schedule_publish，供「课表发布」历史查询）。"""
    with session() as db:
        from app.models import AaScheduleBatch, AaScheduleItem, AaSchedulePublish, User
        from app.services.message_event_outbox_service import emit_receiver_notice
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        guard_term_writable(db, b.term_id)  # 归档11卡§6.2：已归档学期的课表不应再发布
        if b.status == "PUBLISHED":
            # 幂等：已发布重复请求返回原结果，不重复写通知/发布记录
            last = db.scalars(select(AaSchedulePublish).where(
                AaSchedulePublish.tenant_id == _tid(), AaSchedulePublish.batch_id == b.id,
                AaSchedulePublish.action == "PUBLISH", AaSchedulePublish.is_deleted.is_(False)
            ).order_by(AaSchedulePublish.id.desc())).first()
            return {"batchId": str(batch_id), "status": "PUBLISHED",
                    "notified": (last.notified_count if last else 0), "idempotent": True}
        # CAS：仅 DRAFT/PRE_PUBLISHED 可抢占为 PUBLISHED
        claim = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == b.id, AaScheduleBatch.tenant_id == _tid(),
            AaScheduleBatch.status.in_(["DRAFT", "PRE_PUBLISHED"])).update(
            {AaScheduleBatch.status: "PUBLISHED", AaScheduleBatch.publish_at: datetime.utcnow()},
            synchronize_session=False)
        if not claim:
            db.rollback()
            raise AppException("APPROVAL_VERSION_CONFLICT", "该批次状态不可发布或已发布")
        b.status = "PUBLISHED"
        # 通知涉及的教师（去重；按 teacher_key 解析 User，无法解析则跳过）
        teachers = {r.teacher_key for r in db.scalars(select(AaScheduleItem).where(
            AaScheduleItem.tenant_id == _tid(), AaScheduleItem.batch_id == b.id,
            AaScheduleItem.status == "EFFECTIVE", AaScheduleItem.is_deleted.is_(False))).all()
            if r.teacher_key}
        notified = 0
        for tk in teachers:
            acc = db.scalars(select(User).where(
                User.tenant_id == _tid(), User.login_name == tk,
                User.is_deleted.is_(False), User.status == "ACTIVE")).first()
            if not acc:
                continue
            emit_receiver_notice(
                db,
                event_code="COURSE.SCHEDULE_PUBLISHED",
                source_module="academic-affairs",
                source_biz_type="aa_schedule_batch",
                source_biz_id=b.id,
                receiver_id=acc.id,
                title="课表已发布",
                content=f"{b.batch_name} 已发布，请查看你的课表",
                receiver_as="user",
                dedup_extra=str(tk),
            )
            notified += 1
        n, _r, uid = _op()
        db.add(AaSchedulePublish(tenant_id=_tid(), batch_id=b.id, term_id=b.term_id, action="PUBLISH",
                                 operator_name=n or uid, notified_count=notified))
        _audit(db, "AA_SCHEDULE_BATCH", b.id, "PUBLISH", f"teachers={notified}")
        db.commit()
        from app.services.message_event_outbox_service import try_process_pending_outbox
        try_process_pending_outbox(worker_id="aa-schedule-inline")
        return {"batchId": str(batch_id), "status": "PUBLISHED", "notified": notified}


def void_and_reissue(batch_id, user, reason="") -> dict:
    """调停课 V1 运维通道：作废已发布批次（留审计+发布记录），新批次重排。不做流转审批。"""
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        from app.models import AaScheduleBatch, AaSchedulePublish
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        guard_term_writable(db, b.term_id)  # 归档11卡§6.2：已归档学期的课表不应再作废重发
        if b.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布批次可作废重发")
        b.status = "ARCHIVED"
        n, _r, uid = _op()
        db.add(AaSchedulePublish(tenant_id=_tid(), batch_id=b.id, term_id=b.term_id, action="VOID_REISSUE",
                                 operator_name=n or uid, notified_count=0, note=reason.strip()))
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
        it.classroom_id = _resolve_classroom_id(db, classroom)
        it.objection_status, it.objection_reason = None, None
        # 定点改排属人工决策：自动排的课被人工改排后按人工口径保护（与 move_item 同款，否则下次
        # 清空重排会把教务员刚改好的结果当成自动排课残留一并删除）
        if getattr(it, "source", None) == "AUTO":
            it.source = "MANUAL"
        _audit(db, "AA_SCHEDULE", it.id, "ADJUST_ITEM", f"改排至周{weekday}第{slot_no}节")
        db.commit()
        db.refresh(it)
        return _item_row(it)


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


def student_schedule(user, student_id, term_id=None, week=None) -> dict:
    """学生课表（PC 端 /schedule/student/:studentId，13B 课表管理续工第三轮新增）：教务处/学院教务
    （本院）/辅导员（本班）按学生查询。与既有 student_view（批次内下钻，需先知道 batchId，供「三视图」
    下钻用）不同，本入口面向导航菜单三级页，自动取「当前已发布批次」。数据范围：按学生所在行政班
    收敛（与 class_schedule 同一 build_affairs_context 口径），越范围 → 403002；亦并入本人 LOCKED
    选课结果（与 mobile 端 schedule_my 同口径，见 _enrolled_items，source=ENROLLED）。"""
    from app.models import AaScheduleItem, StudentProfile
    with session() as db:
        s = db.get(StudentProfile, int(student_id))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在")
        ctx = build_affairs_context(user, db)
        if ctx.scope_type != "TENANT_ALL":
            allowed = ctx.allowed_class_ids(db) or set()
            if not s.class_id or int(s.class_id) not in allowed:
                raise no_data_scope("该学生不在您的数据范围内")
        batch = _current_published_batch(db, term_id)
        if not batch:
            return {"items": [], "batchId": None, "studentName": s.real_name, "studentNo": s.student_no,
                    "note": "该学生本学期暂无已发布课表"}
        base_items = _view(db, batch.id, [AaScheduleItem.class_id == int(s.class_id)]) if s.class_id else []
        items = base_items + _enrolled_items(db, s.id)
        items = [r for r in items if _week_in_range(r, week)]
        note = "" if s.class_id else "学生无行政班归属"
        return {"items": items, "batchId": str(batch.id), "studentName": s.real_name,
                "studentNo": s.student_no, "note": note}


def teaching_class_schedule(user, teaching_class_code, term_id=None, week=None) -> dict:
    """教学班课表（PC 端 /schedule/teaching-class/:code，13B 课表管理续工第三轮新增）：教学班无独立表，
    派生自 t_aa_teaching_task.teaching_class_code（与 org_service.list_teaching_classes 同一口径）。
    合班（merge_tasks）后 teaching_class_code 唯一改写为 survivor 专属码，课表项 task_id 落到 survivor，
    item.class_id=survivor.class_id，故按 code 查任务→按 task_id 查课表项，与既有 class_schedule 的
    class_id 过滤结果集一致（同一数据来源，仅入口维度不同）。数据范围：任一关联任务的 class_id 落在
    调用者可见范围内即放行（与 class_schedule 同一收敛函数），越范围 → 403002。"""
    from app.models import AaScheduleItem, AaTeachingTask
    with session() as db:
        tasks = db.scalars(select(AaTeachingTask).where(
            AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
            AaTeachingTask.teaching_class_code == teaching_class_code)).all()
        if not tasks:
            raise not_found("教学班不存在")
        ctx = build_affairs_context(user, db)
        if ctx.scope_type != "TENANT_ALL":
            allowed = ctx.allowed_class_ids(db) or set()
            class_ids = {t.class_id for t in tasks if t.class_id}
            if not (class_ids & allowed):
                raise no_data_scope("该教学班不在您的数据范围内")
        task_ids = [t.id for t in tasks]
        teaching_class_name = next((t.teaching_class_name for t in tasks if t.teaching_class_name),
                                   teaching_class_code)
        batch = _current_published_batch(db, term_id)
        if not batch:
            return {"items": [], "batchId": None, "teachingClassName": teaching_class_name,
                    "note": "该教学班本学期暂无已发布课表"}
        rows = _view(db, batch.id, [AaScheduleItem.task_id.in_(task_ids)])
        rows = [r for r in rows if _week_in_range(r, week)]
        return {"items": rows, "batchId": str(batch.id), "teachingClassName": teaching_class_name, "note": ""}


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


# ═══════════ 课表调整记录（13B 课表管理续工第三轮新增，只读）═══════════

_ADJUST_BIZ_TYPES = {"AA_SCHEDULE", "AA_SCHEDULE_BATCH"}


def list_schedule_adjustments(user, biz_type=None, action=None, page=1, page_size=20):
    """课表调整记录（PC 端 /schedule/adjustments）：读 t_affairs_audit_trail，与
    org_service.list_org_audit 同一「审计留痕直读」模式。biz_type 精确枚举为
    AA_SCHEDULE（条目级：ADD_ITEM/单行 IMPORT 冲突跳过/ADJUST_ITEM/TEACHER_OBJECT）+
    AA_SCHEDULE_BATCH（批次级：CREATE/整批 IMPORT/PRE_PUBLISH/PUBLISH/VOID_REISSUE/ARCHIVE）；
    故意不用 LIKE 前缀匹配——同前缀的 AA_SCHEDULE_CHANGE（调停课台账，独立二级模块自有页面）与
    AA_SCHEDULE_EXPORT（课表导出审计，见「课表导出」页）会被 LIKE 'AA_SCHEDULE%' 误捕获，用精确
    白名单排除。权限口径与同域 list_publish_records 一致（按 academicAffairs.schedule.view 放行，
    不逐条回查学院 scope）——记录内容为排课操作留痕，非学生隐私字段；已知限制：无法按学院/班级
    收窄可见范围，见课表管理三级施工卡「已知欠账」。"""
    from app.models import AffairsAuditTrail
    with session() as db:
        conds = [AffairsAuditTrail.tenant_id == _tid()]
        if biz_type:
            bt = biz_type.strip().upper()
            if bt not in _ADJUST_BIZ_TYPES:
                raise AppException("VALIDATION_ERROR", "bizType 仅支持 AA_SCHEDULE / AA_SCHEDULE_BATCH")
            conds.append(AffairsAuditTrail.biz_type == bt)
        else:
            conds.append(AffairsAuditTrail.biz_type.in_(list(_ADJUST_BIZ_TYPES)))
        if action:
            conds.append(AffairsAuditTrail.action == action.strip().upper())
        total = db.scalar(select(func.count()).select_from(AffairsAuditTrail).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.scalars(select(AffairsAuditTrail).where(*conds)
                          .order_by(AffairsAuditTrail.id.desc()).offset(offset).limit(page_size)).all()
        items = [{"id": str(a.id), "bizType": a.biz_type, "bizId": str(a.biz_id) if a.biz_id else None,
                  "action": a.action, "operator": a.operator or "", "roleName": a.role_name or "",
                  "detail": a.detail or "", "occurredAt": _iso(a.occurred_at)} for a in rows]
        return items, total
def move_item(item_id, user, body) -> dict:
    """拖拽调格（对标商业教务图形化排课）：改星期/节次，走同一三重冲突检测器，冲突 409 原位不动。
    仅 DRAFT/PRE_PUBLISHED 批次可拖；已发布课表走调停课流程。"""
    with session() as db:
        from app.models import AaScheduleBatch, AaScheduleItem
        it = db.get(AaScheduleItem, int(item_id))
        if not it or it.is_deleted or it.tenant_id != _tid() or it.status != "EFFECTIVE":
            raise not_found("课表项不存在")
        b = db.get(AaScheduleBatch, int(it.batch_id))
        if not b or b.status not in ("DRAFT", "PRE_PUBLISHED"):
            raise AppException("DATA_CONFLICT", "已发布课表不可拖拽调整（请走调停课）", http_status=409)
        weekday, slot_no = int(body.weekday), int(body.slotNo)
        if weekday not in WEEKDAYS:
            raise AppException("VALIDATION_ERROR", "星期非法")
        if weekday == it.weekday and slot_no == it.slot_no:
            return {"itemId": str(it.id), "weekday": it.weekday, "slotNo": it.slot_no, "moved": False}
        conflict = _detect_conflict(db, it.batch_id, weekday, slot_no, it.start_week, it.end_week,
                                    it.week_parity, it.teacher_key, it.class_id, it.classroom_text,
                                    exclude_id=it.id)
        if conflict:
            raise AppException("DATA_CONFLICT", f"目标时段冲突：{conflict['detail']}", http_status=409)
        old = f"周{it.weekday}第{it.slot_no}节"
        it.weekday, it.slot_no = weekday, slot_no
        # 拖拽属人工决策：自动排的课被人工挪动后按人工口径保护（重排不再清它）
        if getattr(it, "source", None) == "AUTO":
            it.source = "MANUAL"
        _audit(db, "AA_SCHEDULE_ITEM", it.id, "ITEM_MOVE",
               f"{it.course_name} {old}→周{weekday}第{slot_no}节")
        db.commit()
        return {"itemId": str(it.id), "weekday": weekday, "slotNo": slot_no, "moved": True}
