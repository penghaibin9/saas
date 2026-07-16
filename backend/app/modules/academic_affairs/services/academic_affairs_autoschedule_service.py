"""自动排课引擎（SM-07 增强层）。

对标商业教务系统（强智《智慧教学服务平台操作手册》印刷页 186-188 排课参数设置、
印刷页 193-197 自动编排课表与漏排信息处理、印刷页 213 课表冲突检查）的自动排课闭环：

    参数设置 → 自动编排 → 漏排原因分析 → 调参迭代续排 → 人工微调

设计约束（为什么这么写）：
1. **判断标准与手工排课同源**：复用 schedule_service._weeks_overlap，避免"自动排出来的课
   手工校验器认为冲突"这类双标。手工/导入/自动三通道共用一套冲突语义。
2. **不查库试探**：候选位置成千上万，逐个 _detect_conflict 查库会打爆 DB。改为一次性
   加载批次现有课表 → 内存占用索引 → O(1) 判冲突。
3. **只动自己排的课**：重排只清 source=AUTO 的项，人工/导入排的课是教务员的劳动成果，
   引擎绝不覆盖（见 clear_auto_items）。这是本模块最重要的安全边界。
4. **不冒充智能**：排不下就如实报漏排 + 归因，不硬塞、不降级偷偷放宽硬约束。
   宁可少排也不排出一张有冲突的课表。

本引擎为确定性算法（贪心 + MRV 启发式 + 稳定序），同输入同输出，可回归测试。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.modules.academic_affairs.services.academic_affairs_schedule_service import _weeks_overlap
from app.services.db_service import _tid, session

# ══════════ 排课参数（rule_key 规范；存 t_aa_schedule_rule.rule_value_json）══════════
# 参数以「批次级优先于学期级」生效，均有安全缺省，未配置也能跑。
RULE_KEYS = {
    "AUTO_DEFAULT_WEEKS": "缺省上课周次 {startWeek,endWeek}：任务未指定起止周时使用",
    "AUTO_WEEKDAYS": "可排星期 [1-7]：默认周一至周五，职校晚自习/周末班可放开",
    "AUTO_SLOTS": "可排节次 [1..n]：默认 1-8",
    "AUTO_FORBIDDEN": "禁排时段 [{weekday,slotNo}]：slotNo 省略=整天禁排（如周三下午教研）",
    "AUTO_CLASS_MAX_PER_DAY": "同班每天最多节次（默认 8）：防一天全塞满",
    "AUTO_TEACHER_MAX_PER_DAY": "同教师每天最多节次（默认 6）：教师工作量保护",
    "AUTO_ROOM_TYPE_MATCH": "教室类型严格匹配（默认 true）：任务指定 LAB 则只用 LAB",
    "AUTO_CAPACITY_CHECK": "教室容量校验（默认 true）：有效座位 < 上课人数即不可用",
    "AUTO_RESPECT_TEACHER_AVAIL": "尊重教师已采纳的不可排时间（默认 true）",
}

_DEF_WEEKDAYS = [1, 2, 3, 4, 5]
_DEF_SLOTS = [1, 2, 3, 4, 5, 6, 7, 8]

# 漏排原因码 → 人话（教务员看得懂才有用；强智印刷页 194「生成课程漏排的原因」）
REASON_LABEL = {
    "NO_TEACHER": "任务未分配教师",
    "TEACHER_BUSY": "教师在所有可排时段均已有课",
    "CLASS_BUSY": "班级在所有可排时段均已有课",
    "NO_ROOM_TYPE": "无该类型教室（或全部停用/维修/专用）",
    "ROOM_TOO_SMALL": "所有同类型教室容量均小于上课人数",
    "ROOM_BUSY": "合适教室在所有可排时段均被占用",
    "TEACHER_UNAVAILABLE": "教师已采纳的不可排时间挤占了全部可行时段",
    "DAY_LIMIT": "受每日最多节次限制，无处可放",
    "NO_SLOT": "可排时段全部被禁排规则排除",
    "PARTIAL": "部分课时已排，剩余课时无可行位置",
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
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_AUTO_SCHEDULE", biz_id=biz_id, action=action,
                             operator=_op(), role_name=_role(), detail=detail[:990],
                             occurred_at=datetime.utcnow()))


def _require_school(user, db):
    ctx = build_affairs_context(user, db)
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可执行自动排课")
    return ctx


# ══════════ 参数读取 ══════════

def _load_params(db, term_id, batch_id) -> dict:
    """读排课参数：批次级覆盖学期级，缺省安全值兜底。"""
    from app.models import AaScheduleRule
    rows = db.scalars(select(AaScheduleRule).where(
        AaScheduleRule.tenant_id == _tid(), AaScheduleRule.status == "ENABLED",
        AaScheduleRule.is_deleted.is_(False))).all()
    term_lv, batch_lv = {}, {}
    for r in rows:
        if r.batch_id and int(r.batch_id) == int(batch_id):
            batch_lv[r.rule_key] = r.rule_value_json
        elif r.term_id and term_id and int(r.term_id) == int(term_id) and not r.batch_id:
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

    weeks = val("AUTO_DEFAULT_WEEKS", {}) or {}
    return {
        "startWeek": int(weeks.get("startWeek") or 1),
        "endWeek": int(weeks.get("endWeek") or 18),
        "weekdays": [int(x) for x in (val("AUTO_WEEKDAYS", _DEF_WEEKDAYS) or _DEF_WEEKDAYS)],
        "slots": [int(x) for x in (val("AUTO_SLOTS", _DEF_SLOTS) or _DEF_SLOTS)],
        "forbidden": val("AUTO_FORBIDDEN", []) or [],
        "classMaxPerDay": int(val("AUTO_CLASS_MAX_PER_DAY", 8) or 8),
        "teacherMaxPerDay": int(val("AUTO_TEACHER_MAX_PER_DAY", 6) or 6),
        "roomTypeMatch": bool(val("AUTO_ROOM_TYPE_MATCH", True)),
        "capacityCheck": bool(val("AUTO_CAPACITY_CHECK", True)),
        "respectAvail": bool(val("AUTO_RESPECT_TEACHER_AVAIL", True)),
    }


def _forbidden_set(params) -> set:
    """{(weekday, slot)} ；slotNo 省略 → 该天全部节次。"""
    out = set()
    for f in params["forbidden"]:
        if not isinstance(f, dict):
            continue
        wd = f.get("weekday")
        if wd is None:
            continue
        sn = f.get("slotNo")
        if sn is None:
            out.update((int(wd), s) for s in params["slots"])
        else:
            out.add((int(wd), int(sn)))
    return out


# ══════════ 占用索引（内存，O(1) 判冲突）══════════

class _Grid:
    """课表占用索引。key→[(start_week,end_week,parity)]，判重用周次相容语义（与手工排课同源）。"""

    def __init__(self):
        self.teacher = {}
        self.klass = {}
        self.room = {}
        self.class_day = {}    # (class_id, weekday) → 已排节数
        self.teacher_day = {}  # (teacher_key, weekday) → 已排节数

    @staticmethod
    def _hit(bucket, key, sw, ew, par) -> bool:
        for (s, e, p) in bucket.get(key, ()):
            if _weeks_overlap(sw, ew, par, s, e, p):
                return True
        return False

    @staticmethod
    def _put(bucket, key, sw, ew, par):
        bucket.setdefault(key, []).append((sw, ew, par))

    def teacher_busy(self, tk, wd, sl, sw, ew, par):
        return bool(tk) and self._hit(self.teacher, (tk, wd, sl), sw, ew, par)

    def class_busy(self, cid, wd, sl, sw, ew, par):
        return bool(cid) and self._hit(self.klass, (int(cid), wd, sl), sw, ew, par)

    def room_busy(self, rid, wd, sl, sw, ew, par):
        return bool(rid) and self._hit(self.room, (int(rid), wd, sl), sw, ew, par)

    def occupy(self, tk, cid, rid, wd, sl, sw, ew, par):
        if tk:
            self._put(self.teacher, (tk, wd, sl), sw, ew, par)
            self.teacher_day[(tk, wd)] = self.teacher_day.get((tk, wd), 0) + 1
        if cid:
            self._put(self.klass, (int(cid), wd, sl), sw, ew, par)
            self.class_day[(int(cid), wd)] = self.class_day.get((int(cid), wd), 0) + 1
        if rid:
            self._put(self.room, (int(rid), wd, sl), sw, ew, par)


def _build_grid(db, batch_id) -> _Grid:
    """用批次现有 EFFECTIVE 课表项建索引（含人工/导入项 → 自动排课会绕开它们）。"""
    from app.models import AaScheduleItem
    g = _Grid()
    rows = db.scalars(select(AaScheduleItem).where(
        AaScheduleItem.tenant_id == _tid(), AaScheduleItem.batch_id == int(batch_id),
        AaScheduleItem.status == "EFFECTIVE", AaScheduleItem.is_deleted.is_(False))).all()
    for r in rows:
        g.occupy(r.teacher_key, r.class_id, r.classroom_id, r.weekday, r.slot_no,
                 r.start_week, r.end_week, r.week_parity)
    return g


# ══════════ 教室候选 ══════════

def _load_rooms(db, params) -> list:
    """可用教室池：排除停用/维修/专用。专用教室(is_exclusive)仅人工可指定，自动排课跳过。"""
    from app.models import AaClassroom
    rows = db.scalars(select(AaClassroom).where(
        AaClassroom.tenant_id == _tid(), AaClassroom.status == "AVAILABLE",
        AaClassroom.is_exclusive.is_(False), AaClassroom.is_deleted.is_(False))).all()
    # 小容量优先 → 大教室留给大班，避免 30 人课占掉 200 人阶梯教室
    return sorted(rows, key=lambda r: ((r.capacity or 0), r.id))


def _room_candidates(rooms, need_type, headcount, params) -> list:
    out = []
    for r in rooms:
        if params["roomTypeMatch"] and need_type and (r.room_type or "") != need_type:
            continue
        if params["capacityCheck"] and headcount and (r.capacity or 0) < headcount:
            continue
        out.append(r)
    return out


# ══════════ 待排任务 ══════════

def _pending_tasks(db, batch_id) -> list:
    """待排任务：本批次已确认、未标记不排课、且尚未排满周学时的任务。"""
    from app.models import AaScheduleItem, AaTeachingTask
    tasks = db.scalars(select(AaTeachingTask).where(
        AaTeachingTask.tenant_id == _tid(), AaTeachingTask.batch_id == int(batch_id),
        AaTeachingTask.status.notin_(("MERGED", "CANCELLED")),
        AaTeachingTask.no_auto_schedule.is_(False),
        AaTeachingTask.is_deleted.is_(False))).all()
    done = {}
    for it in db.scalars(select(AaScheduleItem).where(
            AaScheduleItem.tenant_id == _tid(), AaScheduleItem.batch_id == int(batch_id),
            AaScheduleItem.status == "EFFECTIVE", AaScheduleItem.is_deleted.is_(False))).all():
        if it.task_id:
            done[int(it.task_id)] = done.get(int(it.task_id), 0) + 1
    out = []
    for t in tasks:
        need = int(t.weekly_hours or 0)
        if need <= 0:
            continue  # 未设周学时 → 不知道排几节，不猜（如需排课请先补周学时）
        have = done.get(int(t.id), 0)
        if have < need:
            out.append((t, need - have, have))
    return out


# ══════════ 主流程：自动编排 ══════════

def auto_schedule(user, batch_id, dry_run=False) -> dict:
    """自动编排课表。增量语义：只排"还差课时"的任务，已排的（含人工排的）一律保留。

    dry_run=True 只算不落库，用于教务员调参预览（强智印刷页 193「在上一次排课的基础上继续排课」
    的前置——先看看这轮参数能排出什么，再决定要不要落）。
    """
    from app.models import AaScheduleBatch, AaScheduleItem, AaTeacherAvailability
    with session() as db:
        _require_school(user, db)
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        if b.status not in ("DRAFT", "PRE_PUBLISHED"):
            raise AppException("DATA_CONFLICT", "已发布课表不可自动排课（请走作废重发或调停课）",
                               http_status=409)

        params = _load_params(db, b.term_id, b.id)
        forbidden = _forbidden_set(params)
        grid = _build_grid(db, b.id)
        rooms = _load_rooms(db, params)
        pend = _pending_tasks(db, b.id)

        avail_block = set()
        if params["respectAvail"]:
            for a in db.scalars(select(AaTeacherAvailability).where(
                    AaTeacherAvailability.tenant_id == _tid(),
                    AaTeacherAvailability.status == "ADOPTED",
                    AaTeacherAvailability.is_deleted.is_(False))).all():
                avail_block.add((a.teacher_key, a.weekday, a.slot_no))

        # MRV：候选教室越少的任务越难排 → 先排。同分按 id 稳定序，保证可重放。
        def tightness(item):
            t, _need, _have = item
            cand = _room_candidates(rooms, t.required_room_type, t.expected_students, params)
            return (len(cand), -(t.expected_students or 0), int(t.id))

        pend.sort(key=tightness)

        placed, misses, new_items = [], [], []
        for (t, need, have) in pend:
            sw = int(t.start_week or params["startWeek"])
            ew = int(t.end_week or params["endWeek"])
            par = "ALL"
            cand_rooms = _room_candidates(rooms, t.required_room_type, t.expected_students, params)
            got, why = _place_task(t, need, sw, ew, par, params, forbidden, grid,
                                   cand_rooms, rooms, avail_block)
            for (wd, sl, room) in got:
                new_items.append(dict(task=t, weekday=wd, slot_no=sl, room=room,
                                      start_week=sw, end_week=ew, parity=par))
            if len(got) < need:
                misses.append({
                    "taskId": str(t.id), "courseName": t.course_name,
                    "className": t.teaching_class_name, "teacherName": t.teacher_name,
                    "needSessions": need, "placedSessions": len(got) + have,
                    "reason": ("PARTIAL" if got else why),
                    "reasonLabel": REASON_LABEL.get("PARTIAL" if got else why, why),
                    "detail": _miss_detail(t, why, params),
                })
            if got:
                placed.append({"taskId": str(t.id), "courseName": t.course_name,
                               "sessions": len(got)})

        if not dry_run and new_items:
            for n in new_items:
                t = n["task"]
                r = n["room"]
                db.add(AaScheduleItem(
                    tenant_id=_tid(), batch_id=b.id, task_id=t.id,
                    course_id=t.course_id, course_name=t.course_name,
                    class_id=t.class_id, class_name=t.teaching_class_name,
                    teacher_key=t.teacher_key, teacher_name=t.teacher_name,
                    weekday=n["weekday"], slot_no=n["slot_no"],
                    start_week=n["start_week"], end_week=n["end_week"], week_parity=n["parity"],
                    classroom_id=(r.id if r else None),
                    classroom_text=(_room_label(r) if r else None),
                    status="EFFECTIVE", source="AUTO"))
            _audit(db, b.id, "AUTO_SCHEDULE",
                   f"排入{len(new_items)}节/{len(placed)}个任务，漏排{len(misses)}")
            db.commit()

        return {
            "batchId": str(b.id), "dryRun": dry_run,
            "placedSessions": len(new_items), "placedTasks": len(placed),
            "missedTasks": len(misses),
            "roomPoolSize": len(rooms),
            "params": params,
            "placed": placed, "misses": misses,
        }


def _room_label(r) -> str:
    return (r.room_name or "").strip() or f"{r.building_name}{r.room_code}"


def _place_task(t, need, sw, ew, par, params, forbidden, grid, cand_rooms, all_rooms, avail_block):
    """给单个任务找 need 个位置。返回 (已放置列表, 失败原因码)。

    失败归因优先级：先判"结构性无解"（无教师/无教室类型/教室都太小），
    再判"时间被占满"——这样教务员看到的是根因，不是表象。
    """
    if not t.teacher_key:
        return [], "NO_TEACHER"
    if not cand_rooms:
        # 区分"没有这型教室" vs "有但都太小"——两者处置完全不同
        by_type = [r for r in all_rooms
                   if not (params["roomTypeMatch"] and t.required_room_type
                           and (r.room_type or "") != t.required_room_type)]
        return [], ("ROOM_TOO_SMALL" if by_type else "NO_ROOM_TYPE")

    got = []
    blocked = {"TEACHER_BUSY": 0, "CLASS_BUSY": 0, "ROOM_BUSY": 0,
               "TEACHER_UNAVAILABLE": 0, "DAY_LIMIT": 0, "NO_SLOT": 0}
    for wd in params["weekdays"]:
        for sl in params["slots"]:
            if len(got) >= need:
                break
            if (wd, sl) in forbidden:
                blocked["NO_SLOT"] += 1
                continue
            if params["respectAvail"] and (t.teacher_key, wd, sl) in avail_block:
                blocked["TEACHER_UNAVAILABLE"] += 1
                continue
            if grid.teacher_day.get((t.teacher_key, wd), 0) >= params["teacherMaxPerDay"]:
                blocked["DAY_LIMIT"] += 1
                continue
            if t.class_id and grid.class_day.get((int(t.class_id), wd), 0) >= params["classMaxPerDay"]:
                blocked["DAY_LIMIT"] += 1
                continue
            if grid.teacher_busy(t.teacher_key, wd, sl, sw, ew, par):
                blocked["TEACHER_BUSY"] += 1
                continue
            if grid.class_busy(t.class_id, wd, sl, sw, ew, par):
                blocked["CLASS_BUSY"] += 1
                continue
            room = next((r for r in cand_rooms
                         if not grid.room_busy(r.id, wd, sl, sw, ew, par)), None)
            if room is None:
                blocked["ROOM_BUSY"] += 1
                continue
            grid.occupy(t.teacher_key, t.class_id, room.id, wd, sl, sw, ew, par)
            got.append((wd, sl, room))
        if len(got) >= need:
            break

    if len(got) >= need:
        return got, ""
    why = max(blocked, key=lambda k: blocked[k]) if any(blocked.values()) else "NO_SLOT"
    return got, why


def _miss_detail(t, why, params) -> str:
    """漏排原因的可执行建议——只说这一条该怎么办，不写通用套话。"""
    if why == "NO_TEACHER":
        return "请先在教学任务中分配任课教师"
    if why == "NO_ROOM_TYPE":
        return f"教室字典中无可用的「{t.required_room_type}」类型教室，请补建或放宽任务的教室类型要求"
    if why == "ROOM_TOO_SMALL":
        return f"上课人数 {t.expected_students or '未知'}，现有同类型教室容量均不足，请拆班或调整教室容量"
    if why == "TEACHER_BUSY":
        return f"教师 {t.teacher_name or t.teacher_key} 可排时段已排满，请调整其它任务或放开可排星期/节次"
    if why == "CLASS_BUSY":
        return f"班级 {t.teaching_class_name or ''} 可排时段已排满，请检查该班周学时总量是否超出可排容量"
    if why == "ROOM_BUSY":
        return "合适教室在可排时段均被占用，请补充同类型教室或放开可排时段"
    if why == "TEACHER_UNAVAILABLE":
        return "教师已采纳的不可排时间覆盖了全部可行时段，请与教师协商或关闭该参数"
    if why == "DAY_LIMIT":
        return f"受每日最多节次限制（班 {params['classMaxPerDay']}/师 {params['teacherMaxPerDay']}），请上调限额或放开可排星期"
    if why == "PARTIAL":
        return "部分课时已排入，剩余课时无可行位置，可在漏排列表中手工补排"
    return "无可行位置"


# ══════════ 漏排分析（只读，供调参迭代）══════════

def miss_report(user, batch_id) -> dict:
    """漏排数据分析：不落库，跑一遍看当前参数下谁排不下、为什么。

    强智印刷页 194：「参考漏排原因信息，可以调整排课类别参数、开课通知单特殊参数、
    教室信息等，然后对漏排的课程进行再次自动编排，可以反复迭代」——本函数即该迭代的观察端。
    """
    res = auto_schedule(user, batch_id, dry_run=True)
    by_reason = {}
    for m in res["misses"]:
        by_reason.setdefault(m["reason"], []).append(m)
    return {
        "batchId": res["batchId"],
        "wouldPlaceSessions": res["placedSessions"],
        "missedTasks": res["missedTasks"],
        "roomPoolSize": res["roomPoolSize"],
        "params": res["params"],
        "summary": [{"reason": k, "reasonLabel": REASON_LABEL.get(k, k), "count": len(v)}
                    for k, v in sorted(by_reason.items(), key=lambda kv: -len(kv[1]))],
        "misses": res["misses"],
    }


# ══════════ 清除自动排课结果 ══════════

def clear_auto_items(user, batch_id) -> dict:
    """只清 source=AUTO 的课表项，人工/导入排的一律保留。

    这是重排的安全前提：教务员手工调整过的课位是劳动成果，引擎无权覆盖。
    """
    from app.models import AaScheduleBatch, AaScheduleItem
    with session() as db:
        _require_school(user, db)
        b = db.get(AaScheduleBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("课表批次不存在")
        if b.status not in ("DRAFT", "PRE_PUBLISHED"):
            raise AppException("DATA_CONFLICT", "已发布课表不可清除", http_status=409)
        rows = db.scalars(select(AaScheduleItem).where(
            AaScheduleItem.tenant_id == _tid(), AaScheduleItem.batch_id == int(b.id),
            AaScheduleItem.source == "AUTO", AaScheduleItem.is_deleted.is_(False))).all()
        for r in rows:
            r.is_deleted = True
        _audit(db, b.id, "AUTO_SCHEDULE_CLEAR", f"清除自动排课 {len(rows)} 节（人工/导入项保留）")
        db.commit()
        return {"batchId": str(b.id), "cleared": len(rows)}


# ══════════ 参数元数据（供前端渲染参数面板）══════════

def rule_catalog(user) -> dict:
    """排课参数说明书：key + 中文说明 + 当前缺省值。前端据此渲染参数面板，不写死。"""
    return {"items": [{"ruleKey": k, "description": v} for k, v in RULE_KEYS.items()],
            "defaults": {"weekdays": _DEF_WEEKDAYS, "slots": _DEF_SLOTS,
                         "classMaxPerDay": 8, "teacherMaxPerDay": 6,
                         "roomTypeMatch": True, "capacityCheck": True,
                         "respectAvail": True, "startWeek": 1, "endWeek": 18}}
