"""13B-P1 教务中心：学年学期/校历/节次 + 学籍名册 + 入学/学年注册。

注册结果经 change_student_status() 单一入口写主档（PENDING_REGISTER→REGISTERED）。
学籍名册只读 t_student_profile（脱敏），不建 roster 表。注册预检只读 t_orientation_student，不复制迎新数据。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.modules.academic_affairs.services.academic_affairs_status_service import (audit_status_change,
                                                          change_student_status)
from app.services.db_service import _iso, _mask_id_card, _tid, session


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _parse_dt(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def _audit(db, biz_type, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


# ═══════════ 学年学期 ═══════════

def _term_row(t) -> dict:
    return {"termId": str(t.id), "yearCode": t.year_code, "termNo": t.term_no,
            "termName": t.term_name or "", "startDate": _iso(t.start_date), "endDate": _iso(t.end_date),
            "teachingWeeks": t.teaching_weeks, "examWeekStart": t.exam_week_start,
            "isCurrent": bool(t.is_current), "status": t.status}


def create_term(body, user) -> dict:
    with session() as db:
        from app.models import AaTerm
        dup = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == _tid(), AaTerm.year_code == body.yearCode,
            AaTerm.term_no == int(body.termNo), AaTerm.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该学年学期已存在")
        t = AaTerm(tenant_id=_tid(), year_code=body.yearCode, term_no=int(body.termNo),
                   term_name=getattr(body, "termName", None), start_date=_parse_dt(body.startDate),
                   end_date=_parse_dt(body.endDate), teaching_weeks=getattr(body, "teachingWeeks", None),
                   exam_week_start=getattr(body, "examWeekStart", None), status="DRAFT")
        db.add(t)
        db.flush()
        _audit(db, "AA_TERM", t.id, "CREATE", f"{body.yearCode}-{body.termNo}")
        db.commit()
        db.refresh(t)
        return _term_row(t)


def publish_term(term_id, user) -> dict:
    """发布学期（DRAFT→PUBLISHED），设为当前学期（幂等：重复发布不报错）。"""
    with session() as db:
        from app.models import AaTerm
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        t = db.get(AaTerm, int(term_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("学期不存在")
        guard_term_writable(db, term_id)  # 归档11卡§6.2：已归档学期不应被重新发布
        if t.status in ("DRAFT", "PUBLISHED"):
            # 其余学期取消 current
            for other in db.scalars(select(AaTerm).where(
                    AaTerm.tenant_id == _tid(), AaTerm.is_current.is_(True),
                    AaTerm.id != t.id)).all():
                other.is_current = False
            t.status, t.is_current = "PUBLISHED", True
            _audit(db, "AA_TERM", t.id, "PUBLISH")
        db.commit()
        db.refresh(t)
        return _term_row(t)


def list_terms(user, status=None, page=1, page_size=50):
    with session() as db:
        from app.models import AaTerm
        conds = [AaTerm.tenant_id == _tid(), AaTerm.is_deleted.is_(False)]
        if status:
            conds.append(AaTerm.status == status)
        rows = db.scalars(select(AaTerm).where(*conds).order_by(
            AaTerm.year_code.desc(), AaTerm.term_no.desc())).all()
        out = [_term_row(t) for t in rows]
        return out[(max(1, page) - 1) * page_size: (max(1, page) - 1) * page_size + page_size], len(out)


def current_term(user) -> dict:
    with session() as db:
        from app.models import AaTerm
        t = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == _tid(), AaTerm.is_current.is_(True),
            AaTerm.is_deleted.is_(False))).first()
        return _term_row(t) if t else {"termId": "", "isCurrent": False, "note": "尚未设置当前学期"}


# ═══════════ 学年学期 Tier1-R2：当前学期设置 / 学期周次 / 教学周配置 / 学期状态 / 学期归档总览 ═══════════
# 设计来源：project_rule（docs/03-业务模块设计/教务中心/13B-教务中心状态机与权限矩阵.md §SM-01
# DRAFT→PUBLISHED→FROZEN→ARCHIVED）+ existing_code（AaTerm.status/teaching_weeks/exam_week_start
# 字段已建但此前无写入口）。归档的实际执行动作（批次/9域完整性检查/确认封存）归属既有「教务归档」
# 二级模块 academic_affairs_archive_service.py，本节只提供只读总览，不重复实现，避免双写。

def set_current_term(term_id, user) -> dict:
    """当前学期设置：仅 PUBLISHED 学期可设为当前（幂等，不改变 status，只切换 is_current）。"""
    with session() as db:
        from app.models import AaTerm
        t = db.get(AaTerm, int(term_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("学期不存在")
        if t.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅进行中（PUBLISHED）学期可设为当前学期")
        if not t.is_current:
            for other in db.scalars(select(AaTerm).where(
                    AaTerm.tenant_id == _tid(), AaTerm.is_current.is_(True),
                    AaTerm.id != t.id)).all():
                other.is_current = False
            t.is_current = True
            _audit(db, "AA_TERM", t.id, "SET_CURRENT", f"{t.year_code}-{t.term_no}")
        db.commit()
        db.refresh(t)
        return _term_row(t)


def list_term_weeks(term_id, user) -> list:
    """学期周次：按 start_date + teaching_weeks 展开周网格；叠加校历事件（HOLIDAY/EXAM/INTERNSHIP 覆盖当周类型）；
    标记 isCurrent（今天落在该周区间内）。只读计算，不新建表。"""
    from app.models import AaCalendarEvent, AaTerm
    with session() as db:
        t = db.get(AaTerm, int(term_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("学期不存在")
        if not t.start_date or not t.teaching_weeks:
            return []
        events = db.scalars(select(AaCalendarEvent).where(
            AaCalendarEvent.tenant_id == _tid(), AaCalendarEvent.term_id == t.id,
            AaCalendarEvent.is_deleted.is_(False))).all()
        today = datetime.utcnow().date()
        out = []
        for wk in range(1, int(t.teaching_weeks) + 1):
            w_start = (t.start_date + timedelta(days=(wk - 1) * 7)).date()
            w_end = w_start + timedelta(days=6)
            week_type = "EXAM" if t.exam_week_start and wk == int(t.exam_week_start) else "TEACHING"
            remark = None
            for e in events:
                if not e.start_date:
                    continue
                e_start = e.start_date.date()
                e_end = (e.end_date or e.start_date).date()
                if e_start <= w_end and e_end >= w_start and e.event_type in ("HOLIDAY", "EXAM", "INTERNSHIP"):
                    week_type = e.event_type
                    remark = e.remark
                    break
            out.append({"weekNo": wk, "startDate": w_start.isoformat(), "endDate": w_end.isoformat(),
                       "weekType": week_type, "remark": remark or "", "isCurrent": w_start <= today <= w_end})
        return out


def update_teaching_weeks(term_id, body, user) -> dict:
    """教学周配置：仅 DRAFT 学期可调整教学周结构（SM-01：PUBLISHED 后结构性调整须走冻结-解冻或新学期，409）。"""
    with session() as db:
        from app.models import AaTerm
        t = db.get(AaTerm, int(term_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("学期不存在")
        if t.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "已发布学期不可直接调整教学周结构，请走冻结-解冻或新学期")
        tw = getattr(body, "teachingWeeks", None)
        ews = getattr(body, "examWeekStart", None)
        if tw is not None and int(tw) <= 0:
            raise AppException("VALIDATION_ERROR", "教学周数须为正整数")
        if ews is not None and int(ews) <= 0:
            raise AppException("VALIDATION_ERROR", "考试周开始周次须为正整数")
        eff_tw = int(tw) if tw is not None else t.teaching_weeks
        if ews is not None and eff_tw and int(ews) > int(eff_tw):
            raise AppException("VALIDATION_ERROR", "考试周开始周次不能超过教学周总数")
        if tw is not None:
            t.teaching_weeks = int(tw)
        if ews is not None:
            t.exam_week_start = int(ews)
        _audit(db, "AA_TERM", t.id, "TEACHING_WEEKS_UPDATE",
              f"teachingWeeks={t.teaching_weeks},examWeekStart={t.exam_week_start}")
        db.commit()
        db.refresh(t)
        return _term_row(t)


def freeze_term(term_id, user) -> dict:
    """学期状态·冻结：PUBLISHED→FROZEN（排课/选课/考试任一批次进入进行中后建议冻结，冻结后禁止结构性修改）。"""
    with session() as db:
        from app.models import AaTerm
        t = db.get(AaTerm, int(term_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("学期不存在")
        if t.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅进行中（PUBLISHED）学期可冻结")
        t.status = "FROZEN"
        _audit(db, "AA_TERM", t.id, "FREEZE")
        db.commit()
        db.refresh(t)
        return _term_row(t)


def unfreeze_term(term_id, reason, user) -> dict:
    """学期状态·解冻：FROZEN→PUBLISHED（原因必填≥5字，审计留痕）。"""
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "解冻原因必填且不少于5字")
    with session() as db:
        from app.models import AaTerm
        t = db.get(AaTerm, int(term_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("学期不存在")
        if t.status != "FROZEN":
            raise AppException("DATA_CONFLICT", "仅已冻结（FROZEN）学期可解冻")
        t.status = "PUBLISHED"
        _audit(db, "AA_TERM", t.id, "UNFREEZE", reason)
        db.commit()
        db.refresh(t)
        return _term_row(t)


def term_archive_overview(user) -> list:
    """学期归档总览：按学期汇总关联的教务归档批次状态（只读跳转入口）。
    实际归档批次/9数据域完整性检查/确认封存动作单一入口仍在 academic_affairs_archive_service（教务归档二级模块）。"""
    from app.models import AaArchiveBatch, AaTerm
    with session() as db:
        terms = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == _tid(), AaTerm.is_deleted.is_(False)).order_by(
            AaTerm.year_code.desc(), AaTerm.term_no.desc())).all()
        batch_rows = db.scalars(select(AaArchiveBatch).where(
            AaArchiveBatch.tenant_id == _tid(), AaArchiveBatch.is_deleted.is_(False))).all()
        batches = {b.term_id: b for b in batch_rows if b.term_id}
        out = []
        for t in terms:
            b = batches.get(t.id)
            out.append({"termId": str(t.id), "yearCode": t.year_code, "termNo": t.term_no,
                       "termName": t.term_name or "", "termStatus": t.status,
                       "archiveBatchId": str(b.id) if b else None,
                       "archiveBatchStatus": b.status if b else None,
                       "archivedAt": _iso(b.archived_at) if b else None})
        return out


# ═══════════ 学年学期 续工 R3：学年管理 / 学期切换记录 ═══════════
# 设计来源：project_rule（表单字段文档「表单1：学年学期创建」§学年名称——学年并非独立实体，
# 由 t_aa_term.year_code 承载，创建学期时随表单一并录入）+ existing_code（AaTerm.year_code/is_current 与
# set_current_term/publish_term 已写入的 t_affairs_audit_trail(biz_type=AA_TERM) 审计流水）。
# 两个端点均为只读聚合计算，不新建表、不新增权限点（复用既有 academicAffairs.term.view），
# 沿用同批 term_archive_overview/list_term_weeks「只读计算不新建表」的既定模式。

def list_academic_years(user) -> list:
    """学年管理：按 year_code 汇总学期，供学年级总览（第1/2学期是否齐全、学年整体状态、当前学年）。
    ai_proposal：学年级聚合展示是本卡新增的呈现方式，底层数据（year_code 分组）100% 来自既有 t_aa_term，
    不新建表、不新建实体，仅为计算逻辑。"""
    from app.models import AaTerm
    with session() as db:
        terms = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == _tid(), AaTerm.is_deleted.is_(False)).order_by(
            AaTerm.year_code.desc(), AaTerm.term_no.asc())).all()
        groups: dict[str, list] = {}
        order = []
        for t in terms:
            if t.year_code not in groups:
                groups[t.year_code] = []
                order.append(t.year_code)
            groups[t.year_code].append(t)
        out = []
        for yc in order:
            group = groups[yc]
            statuses = {t.status for t in group}
            if statuses & {"PUBLISHED", "FROZEN"}:
                year_status = "ACTIVE"
            elif statuses and statuses == {"ARCHIVED"}:
                year_status = "ARCHIVED"
            elif statuses and statuses == {"DRAFT"}:
                year_status = "PLANNING"
            else:
                year_status = "MIXED"
            starts = [t.start_date for t in group if t.start_date]
            ends = [t.end_date for t in group if t.end_date]
            out.append({
                "yearCode": yc,
                "termCount": len(group),
                "isCurrentYear": any(t.is_current for t in group),
                "yearStatus": year_status,
                "startDate": _iso(min(starts)) if starts else None,
                "endDate": _iso(max(ends)) if ends else None,
                "terms": [_term_row(t) for t in sorted(group, key=lambda x: x.term_no)],
            })
        return out


def list_term_switch_log(user, page=1, page_size=50):
    """学期切换记录：读 t_affairs_audit_trail(biz_type=AA_TERM, action∈PUBLISH/SET_CURRENT)，
    按发生时间顺序推导每次「当前学期」切换的切出→切入学期，最新的排最前。
    PUBLISH 与 SET_CURRENT 均会改写 is_current（见 publish_term/set_current_term），故均计入切换记录。"""
    from app.models import AaTerm, AffairsAuditTrail
    with session() as db:
        rows = db.scalars(select(AffairsAuditTrail).where(
            AffairsAuditTrail.tenant_id == _tid(), AffairsAuditTrail.biz_type == "AA_TERM",
            AffairsAuditTrail.action.in_(("PUBLISH", "SET_CURRENT"))
        ).order_by(AffairsAuditTrail.occurred_at.asc(), AffairsAuditTrail.id.asc())).all()
        term_ids = {r.biz_id for r in rows if r.biz_id}
        terms = {}
        if term_ids:
            for t in db.scalars(select(AaTerm).where(
                    AaTerm.tenant_id == _tid(), AaTerm.id.in_(term_ids))).all():
                terms[t.id] = t

        def _label(tid):
            t = terms.get(tid)
            if not t:
                return None
            return t.term_name or f"{t.year_code} 第{t.term_no}学期"

        out = []
        prev_id = None
        for r in rows:
            out.append({
                "id": str(r.id), "occurredAt": _iso(r.occurred_at), "action": r.action,
                "operator": r.operator or "", "roleName": r.role_name or "",
                "fromTermId": str(prev_id) if prev_id else None,
                "fromTermLabel": _label(prev_id) if prev_id else None,
                "toTermId": str(r.biz_id) if r.biz_id else None,
                "toTermLabel": _label(r.biz_id),
            })
            if r.biz_id:
                prev_id = r.biz_id
        out.reverse()
        total = len(out)
        offset = (max(1, page) - 1) * page_size
        return out[offset: offset + page_size], total


# ═══════════ 校历 / 节次（校历节次 Tier1 R2） ═══════════
# 节假日=t_aa_calendar_event(event_type=HOLIDAY)；补课日/调休=t_aa_calendar_event(event_type=SWAP，
# start_date=原停课日，swap_to_date=补课日，二者必须成对)；节次=t_aa_time_slot（沿用，租户级全局，
# 不随学期锁定）；上课时间段=新表 t_aa_class_time_band（节次的实际钟点，回链 slot_id，支持按校区/
# 生效日期区间配置多套作息）；教学周日历=按 term.start_date+teaching_weeks+exam_week_start 派生，
# 叠加校历事件着色，零新表；校历发布=复用 t_aa_term.status（DRAFT→PUBLISHED）但校验节次已配置+
# 调休已配对，仅教务处/学校管理员可执行（同 grade_service._REVIEW_ROLES 惯例）；
# 校历归档=PUBLISHED/FROZEN→ARCHIVED，仅教务处/学校管理员。

_CAL_MGMT_ROLES = {"ACADEMIC_ADMIN", "SCHOOL_ADMIN"}  # 校历发布/归档超高危角色白名单（同成绩终审惯例）
_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _require_cal_mgmt_role(user):
    role = (user.get("currentRoleCode") or "").upper()
    if role not in _CAL_MGMT_ROLES and user.get("userType") != "PLATFORM_SUPER_ADMIN":
        raise no_permission("仅教务处/学校管理员可执行该操作")


def _load_term(db, term_id):
    from app.models import AaTerm
    t = db.get(AaTerm, int(term_id))
    if not t or t.is_deleted or t.tenant_id != _tid():
        raise not_found("学期不存在")
    return t


def _assert_calendar_editable(t) -> None:
    """校历一旦发布即锁定（不可再增删改事件），需先归档回退或走线下变更，避免课表/统计基准漂移。"""
    if t.status in ("PUBLISHED", "FROZEN", "ARCHIVED"):
        raise AppException("DATA_CONFLICT", "校历已发布，事件已锁定，如需调整请联系教务处")


def _validate_event_dates(t, event_type, start_date, end_date, swap_to_date) -> None:
    if not start_date:
        raise AppException("VALIDATION_ERROR", "请填写开始日期")
    if event_type == "SWAP" and not swap_to_date:
        raise AppException("VALIDATION_ERROR", "补课日必须填写「调至日期」，节假日与补课日须成对登记")
    if event_type == "SWAP" and swap_to_date == start_date:
        raise AppException("VALIDATION_ERROR", "补课日期不能与原停课日期相同")
    if t.start_date and t.end_date:
        for d in (start_date, end_date or start_date, swap_to_date):
            if d and (d < t.start_date or d > t.end_date):
                raise AppException("VALIDATION_ERROR", "日期需在学期起止范围内")


def _calendar_row(e) -> dict:
    return {"eventId": str(e.id), "termId": str(e.term_id), "eventType": e.event_type,
            "startDate": _iso(e.start_date), "endDate": _iso(e.end_date),
            "swapToDate": _iso(e.swap_to_date), "remark": e.remark or "", "version": e.version}


def add_calendar_event(term_id, user, body) -> dict:
    with session() as db:
        from app.models import AaCalendarEvent
        t = _load_term(db, term_id)
        _assert_calendar_editable(t)
        event_type = body.eventType or "TEACHING"
        start_date = _parse_dt(body.startDate)
        end_date = _parse_dt(body.endDate)
        swap_to_date = _parse_dt(getattr(body, "swapToDate", None))
        _validate_event_dates(t, event_type, start_date, end_date, swap_to_date)
        e = AaCalendarEvent(tenant_id=_tid(), term_id=t.id, event_type=event_type,
                            start_date=start_date, end_date=end_date, swap_to_date=swap_to_date,
                            remark=getattr(body, "remark", None))
        db.add(e)
        db.flush()
        _audit(db, "AA_CALENDAR", e.id, "ADD", event_type)
        db.commit()
        db.refresh(e)
        return _calendar_row(e)


def update_calendar_event(term_id, event_id, user, body) -> dict:
    with session() as db:
        from app.models import AaCalendarEvent
        t = _load_term(db, term_id)
        _assert_calendar_editable(t)
        e = db.get(AaCalendarEvent, int(event_id))
        if not e or e.is_deleted or e.tenant_id != _tid() or e.term_id != t.id:
            raise not_found("校历事件不存在")
        event_type = getattr(body, "eventType", None) or e.event_type
        start_date = _parse_dt(getattr(body, "startDate", None)) if getattr(body, "startDate", None) is not None else e.start_date
        end_date = _parse_dt(getattr(body, "endDate", None)) if getattr(body, "endDate", None) is not None else e.end_date
        swap_to_date = _parse_dt(getattr(body, "swapToDate", None)) if getattr(body, "swapToDate", None) is not None else e.swap_to_date
        _validate_event_dates(t, event_type, start_date, end_date, swap_to_date)
        e.event_type, e.start_date, e.end_date, e.swap_to_date = event_type, start_date, end_date, swap_to_date
        if getattr(body, "remark", None) is not None:
            e.remark = body.remark or None
        e.version += 1
        _audit(db, "AA_CALENDAR", e.id, "UPDATE", event_type)
        db.commit()
        db.refresh(e)
        return _calendar_row(e)


def delete_calendar_event(term_id, event_id, user) -> dict:
    with session() as db:
        from app.models import AaCalendarEvent
        t = _load_term(db, term_id)
        _assert_calendar_editable(t)
        e = db.get(AaCalendarEvent, int(event_id))
        if not e or e.is_deleted or e.tenant_id != _tid() or e.term_id != t.id:
            raise not_found("校历事件不存在")
        e.is_deleted = True
        e.version += 1
        _audit(db, "AA_CALENDAR", e.id, "DELETE", e.event_type)
        db.commit()
        return {"eventId": str(event_id)}


def list_calendar(term_id, user, event_type=None):
    from app.models import AaCalendarEvent
    with session() as db:
        conds = [AaCalendarEvent.tenant_id == _tid(), AaCalendarEvent.term_id == int(term_id),
                 AaCalendarEvent.is_deleted.is_(False)]
        if event_type:
            conds.append(AaCalendarEvent.event_type == event_type)
        rows = db.scalars(select(AaCalendarEvent).where(*conds).order_by(AaCalendarEvent.start_date)).all()
        return [_calendar_row(e) for e in rows]


# ── 教学周日历（term.start_date+teaching_weeks+exam_week_start 派生，叠加校历事件着色，零新表）──

def week_calendar(term_id, user) -> dict:
    from app.models import AaCalendarEvent
    with session() as db:
        t = _load_term(db, term_id)
        if not t.start_date or not t.teaching_weeks:
            raise AppException("VALIDATION_ERROR", "请先在「学年学期」维护起止日期与教学周数")
        events = db.scalars(select(AaCalendarEvent).where(
            AaCalendarEvent.tenant_id == _tid(), AaCalendarEvent.term_id == t.id,
            AaCalendarEvent.is_deleted.is_(False), AaCalendarEvent.start_date.is_not(None))).all()
        weeks = []
        cursor = t.start_date
        for wno in range(1, int(t.teaching_weeks) + 1):
            week_start, week_end = cursor, cursor + timedelta(days=6)
            week_type = "EXAM" if (t.exam_week_start and wno >= int(t.exam_week_start)) else "TEACHING"
            holidays, swaps, internships = [], [], []
            for e in events:
                e_end = e.end_date or e.start_date
                if not (e.start_date <= week_end and e_end >= week_start):
                    continue
                if e.event_type == "HOLIDAY":
                    holidays.append({"eventId": str(e.id), "startDate": _iso(e.start_date),
                                     "endDate": _iso(e.end_date), "remark": e.remark or ""})
                    week_type = "HOLIDAY"
                elif e.event_type == "SWAP":
                    swaps.append({"eventId": str(e.id), "startDate": _iso(e.start_date),
                                  "swapToDate": _iso(e.swap_to_date), "remark": e.remark or ""})
                elif e.event_type == "INTERNSHIP" and week_type == "TEACHING":
                    week_type = "INTERNSHIP"
                    internships.append({"eventId": str(e.id)})
            weeks.append({"weekNo": wno, "startDate": _iso(week_start), "endDate": _iso(week_end),
                         "weekType": week_type, "holidays": holidays, "swaps": swaps, "internships": internships})
            cursor += timedelta(days=7)
        return {"termId": str(t.id), "termName": t.term_name or f"{t.year_code} 第{t.term_no}学期",
               "teachingWeeks": t.teaching_weeks, "examWeekStart": t.exam_week_start, "weeks": weeks}


# ── 校历发布（复用 t_aa_term.status；校验节次已配置+调休已配对；仅教务处/学校管理员）──

def publish_calendar(term_id, user) -> dict:
    _require_cal_mgmt_role(user)
    with session() as db:
        from app.models import AaCalendarEvent, AaTerm, AaTimeSlot
        t = _load_term(db, term_id)
        if t.status in ("FROZEN", "ARCHIVED"):
            raise AppException("DATA_CONFLICT", "当前学期状态不允许发布校历")
        if t.status == "DRAFT":
            slot_cnt = db.scalar(select(func.count()).select_from(AaTimeSlot).where(
                AaTimeSlot.tenant_id == _tid(), AaTimeSlot.is_deleted.is_(False),
                AaTimeSlot.status == "ENABLED")) or 0
            if slot_cnt == 0:
                raise AppException("VALIDATION_ERROR", "请先在「节次管理」配置至少一个节次后再发布校历")
            unpaired = db.scalars(select(AaCalendarEvent).where(
                AaCalendarEvent.tenant_id == _tid(), AaCalendarEvent.term_id == t.id,
                AaCalendarEvent.is_deleted.is_(False), AaCalendarEvent.event_type == "SWAP",
                AaCalendarEvent.swap_to_date.is_(None))).first()
            if unpaired:
                raise AppException("VALIDATION_ERROR", "存在未配对的补课日记录，请先补全补课日期")
            for other in db.scalars(select(AaTerm).where(
                    AaTerm.tenant_id == _tid(), AaTerm.is_current.is_(True), AaTerm.id != t.id)).all():
                other.is_current = False
            t.status, t.is_current = "PUBLISHED", True
            _audit(db, "AA_CALENDAR", t.id, "PUBLISH")
        db.commit()
        db.refresh(t)
        return _term_row(t)


# 注：原「校历归档」直写 AaTerm.status=ARCHIVED 的 archive_term() 已在总控合并复核时移除——
# 该路径绕开教务归档模块的批次+9域完整性检查+正规解冻通道，且无任何撤销手段，会把一次按钮误操作
# 变成永久锁死全模块 19+ 写端点的不可逆事故。归档动作统一走 academic_affairs_archive_service
# 的批次流程；本模块只保留只读的 term_detail 供状态展示与跳转引导。

def term_detail(term_id, user) -> dict:
    with session() as db:
        return _term_row(_load_term(db, term_id))


# ── 节次管理（t_aa_time_slot，租户级全局，不随学期锁定）──

def _time_slot_row(x) -> dict:
    return {"slotId": str(x.id), "slotNo": x.slot_no, "slotName": x.slot_name or "",
            "startTime": x.start_time or "", "endTime": x.end_time or "",
            "campusCode": x.campus_code or "", "enabled": bool(x.enabled), "status": x.status,
            "version": x.version}


def create_time_slot(body, user) -> dict:
    with session() as db:
        from app.models import AaTimeSlot
        slot_no = int(body.slotNo)
        dup = db.scalars(select(AaTimeSlot).where(
            AaTimeSlot.tenant_id == _tid(), AaTimeSlot.slot_no == slot_no,
            AaTimeSlot.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该节次序号已存在")
        sl = AaTimeSlot(tenant_id=_tid(), slot_no=slot_no, slot_name=getattr(body, "slotName", None),
                        start_time=getattr(body, "startTime", None), end_time=getattr(body, "endTime", None),
                        status="ENABLED", enabled=True)
        db.add(sl)
        db.flush()
        _audit(db, "AA_TIMESLOT", sl.id, "CREATE", f"第{slot_no}节")
        db.commit()
        db.refresh(sl)
        return _time_slot_row(sl)


def update_time_slot(slot_id, user, body) -> dict:
    with session() as db:
        from app.models import AaTimeSlot
        s = db.get(AaTimeSlot, int(slot_id))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("节次不存在")
        if getattr(body, "slotNo", None) is not None:
            slot_no = int(body.slotNo)
            if slot_no != s.slot_no:
                dup = db.scalars(select(AaTimeSlot).where(
                    AaTimeSlot.tenant_id == _tid(), AaTimeSlot.slot_no == slot_no,
                    AaTimeSlot.id != s.id, AaTimeSlot.is_deleted.is_(False))).first()
                if dup:
                    raise AppException("DATA_CONFLICT", "该节次序号已存在")
            s.slot_no = slot_no
        if getattr(body, "slotName", None) is not None:
            s.slot_name = body.slotName or None
        if getattr(body, "startTime", None) is not None:
            s.start_time = body.startTime or None
        if getattr(body, "endTime", None) is not None:
            s.end_time = body.endTime or None
        if getattr(body, "enabled", None) is not None:
            s.enabled = bool(body.enabled)
            s.status = "ENABLED" if s.enabled else "DISABLED"
        s.version += 1
        _audit(db, "AA_TIMESLOT", s.id, "UPDATE", f"第{s.slot_no}节")
        db.commit()
        db.refresh(s)
        return _time_slot_row(s)


def delete_time_slot(slot_id, user) -> dict:
    with session() as db:
        from app.models import AaTimeSlot
        s = db.get(AaTimeSlot, int(slot_id))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("节次不存在")
        s.is_deleted = True
        s.version += 1
        _audit(db, "AA_TIMESLOT", s.id, "DELETE", f"第{s.slot_no}节")
        db.commit()
        return {"slotId": str(slot_id)}


def list_time_slots(user, include_disabled=False):
    from app.models import AaTimeSlot
    with session() as db:
        conds = [AaTimeSlot.tenant_id == _tid(), AaTimeSlot.is_deleted.is_(False)]
        if not include_disabled:
            conds.append(AaTimeSlot.status == "ENABLED")
        rows = db.scalars(select(AaTimeSlot).where(*conds).order_by(AaTimeSlot.slot_no)).all()
        return [_time_slot_row(x) for x in rows]


# ── 上课时间段（t_aa_class_time_band，节次的实际钟点，支持按校区/生效日期区间配置多套作息）──

def _time_band_row(b) -> dict:
    return {"bandId": str(b.id), "slotId": str(b.slot_id), "bandName": b.band_name or "",
            "campusCode": b.campus_code or "", "effectiveStart": _iso(b.effective_start),
            "effectiveEnd": _iso(b.effective_end), "startTime": b.start_time or "",
            "endTime": b.end_time or "", "status": b.status, "version": b.version}


def _validate_band_times(start_time, end_time) -> None:
    if not start_time or not end_time:
        raise AppException("VALIDATION_ERROR", "开始时间与结束时间必填")
    if not _HHMM_RE.match(start_time) or not _HHMM_RE.match(end_time):
        raise AppException("VALIDATION_ERROR", "时间格式应为 HH:MM，如 08:00")
    if start_time >= end_time:
        raise AppException("VALIDATION_ERROR", "结束时间应晚于开始时间")


def create_time_band(slot_id, user, body) -> dict:
    with session() as db:
        from app.models import AaClassTimeBand, AaTimeSlot
        s = db.get(AaTimeSlot, int(slot_id))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("节次不存在")
        start_time = (getattr(body, "startTime", None) or "").strip()
        end_time = (getattr(body, "endTime", None) or "").strip()
        _validate_band_times(start_time, end_time)
        b = AaClassTimeBand(tenant_id=_tid(), slot_id=s.id, band_name=getattr(body, "bandName", None),
                            campus_code=getattr(body, "campusCode", None),
                            effective_start=_parse_dt(getattr(body, "effectiveStart", None)),
                            effective_end=_parse_dt(getattr(body, "effectiveEnd", None)),
                            start_time=start_time, end_time=end_time, status="ENABLED")
        db.add(b)
        db.flush()
        _audit(db, "AA_TIME_BAND", b.id, "CREATE", f"第{s.slot_no}节 {start_time}-{end_time}")
        db.commit()
        db.refresh(b)
        return _time_band_row(b)


def update_time_band(band_id, user, body) -> dict:
    with session() as db:
        from app.models import AaClassTimeBand
        b = db.get(AaClassTimeBand, int(band_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("上课时间段不存在")
        start_time = getattr(body, "startTime", None)
        end_time = getattr(body, "endTime", None)
        new_start = start_time.strip() if start_time is not None else b.start_time
        new_end = end_time.strip() if end_time is not None else b.end_time
        _validate_band_times(new_start, new_end)
        b.start_time, b.end_time = new_start, new_end
        if getattr(body, "bandName", None) is not None:
            b.band_name = body.bandName or None
        if getattr(body, "campusCode", None) is not None:
            b.campus_code = body.campusCode or None
        if getattr(body, "effectiveStart", None) is not None:
            b.effective_start = _parse_dt(body.effectiveStart)
        if getattr(body, "effectiveEnd", None) is not None:
            b.effective_end = _parse_dt(body.effectiveEnd)
        if getattr(body, "status", None) is not None:
            if body.status not in ("ENABLED", "DISABLED"):
                raise AppException("VALIDATION_ERROR", "状态非法（合法值：ENABLED/DISABLED）")
            b.status = body.status
        b.version += 1
        _audit(db, "AA_TIME_BAND", b.id, "UPDATE", f"{new_start}-{new_end}")
        db.commit()
        db.refresh(b)
        return _time_band_row(b)


def delete_time_band(band_id, user) -> dict:
    with session() as db:
        from app.models import AaClassTimeBand
        b = db.get(AaClassTimeBand, int(band_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("上课时间段不存在")
        b.is_deleted = True
        b.version += 1
        _audit(db, "AA_TIME_BAND", b.id, "DELETE")
        db.commit()
        return {"bandId": str(band_id)}


def list_time_bands(slot_id, user):
    from app.models import AaClassTimeBand
    with session() as db:
        conds = [AaClassTimeBand.tenant_id == _tid(), AaClassTimeBand.is_deleted.is_(False)]
        if slot_id:
            conds.append(AaClassTimeBand.slot_id == int(slot_id))
        rows = db.scalars(select(AaClassTimeBand).where(*conds)
                          .order_by(AaClassTimeBand.slot_id, AaClassTimeBand.effective_start)).all()
        return [_time_band_row(b) for b in rows]


# ═══════════ 学籍名册（只读主档，脱敏）═══════════

def roster(user, keyword=None, status=None, page=1, page_size=20):
    from app.models import StudentProfile
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled
    with session() as db:
        conds = [StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)]
        if status:
            conds.append(StudentProfile.student_status == status)
        rows = db.scalars(select(StudentProfile).where(*conds).order_by(StudentProfile.id.desc())).all()
        out = []
        for s in rows:
            if keyword and keyword not in (s.real_name or "") and keyword not in (s.student_no or ""):
                continue
            out.append({"studentId": str(s.id), "studentNo": s.student_no, "realName": s.real_name,
                        "className": str(s.class_id or ""), "studentStatus": s.student_status,
                        "enrolled": is_enrolled(s.student_status),
                        "idCardMasked": _mask_id_card(s.id_card_encrypted)})
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


# ═══════════ 学籍档案 / 学籍状态总览（Tier1 R2，只读，复用 t_student_profile/t_aa_status_change/College/Major/SchoolClass）═══════════

_STATUS_LABEL = {
    "NORMAL": "正常", "MERGED": "已合并", "RECYCLED": "已回收",
    "PENDING_REGISTER": "待注册", "REGISTERED": "在籍注册", "UNREGISTERED": "未注册",
    "SUSPENDED": "休学", "RETAINED": "留级", "WITHDRAWN": "退学",
    "TRANSFER_SCHOOL": "转学", "GRADUATED": "毕业", "COMPLETED": "结业", "INCOMPLETE": "肄业",
}


def _resolve_org_names(db, s):
    from app.models import College, Major, SchoolClass
    college_name = major_name = class_name = ""
    if s.class_id:
        c = db.get(SchoolClass, int(s.class_id))
        if c and not c.is_deleted and c.tenant_id == _tid():
            class_name = c.class_name
    if s.major_id:
        m = db.get(Major, int(s.major_id))
        if m and not m.is_deleted and m.tenant_id == _tid():
            major_name = m.major_name
    if s.college_id:
        col = db.get(College, int(s.college_id))
        if col and not col.is_deleted and col.tenant_id == _tid():
            college_name = col.college_name
    return college_name, major_name, class_name


def roster_detail(student_id, user) -> dict:
    """学籍档案详情（对齐 13B §2.5 /roll/students/:studentId）：主档 + 组织名称 + 学籍状态历史（全量）。

    数据范围：教务处/校管 TENANT_ALL 全校；学院教务/辅导员按 build_affairs_context 收敛到 from/本院/本班，
    越权直连 URL → 403002（fail-closed，对齐设计验收①）。
    """
    from app.models import AaStatusChange
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled
    with session() as db:
        ctx = build_affairs_context(user, db)
        s = ctx.require_student(db, int(student_id))
        college_name, major_name, class_name = _resolve_org_names(db, s)
        history_rows = db.scalars(select(AaStatusChange).where(
            AaStatusChange.tenant_id == _tid(), AaStatusChange.student_id == s.id,
            AaStatusChange.is_deleted.is_(False)).order_by(AaStatusChange.id.desc())).all()
        history = [{"changeId": str(h.id), "changeType": h.change_type,
                    "fromStatus": h.from_status, "toStatus": h.to_status,
                    "reason": h.reason or "", "status": h.status,
                    "effectiveDate": _iso(h.effective_date), "termCode": h.term_code or ""}
                   for h in history_rows]
        return {
            "studentId": str(s.id), "studentNo": s.student_no, "realName": s.real_name,
            "gender": s.gender or "", "collegeId": str(s.college_id or ""), "collegeName": college_name,
            "majorId": str(s.major_id or ""), "majorName": major_name,
            "classId": str(s.class_id or ""), "className": class_name, "grade": s.grade or "",
            "studentStatus": s.student_status, "statusLabel": _STATUS_LABEL.get(s.student_status, s.student_status),
            "currentStage": s.current_stage, "enrolled": is_enrolled(s.student_status),
            "idCardMasked": _mask_id_card(s.id_card_encrypted),
            "enrollDate": _iso(s.enroll_date), "remark": s.remark or "",
            "statusHistory": history,
        }


def reveal_roster_sensitive(student_id, user, reason="") -> dict:
    """查看完整证件号（sensitiveView 鉴权 + 强制 SENSITIVE_VIEW 审计，越权与成功均落审计，对齐 aid_reveal 同款模式）。"""
    from app.core.exceptions import no_permission
    from app.core.permissions import has_permission
    from app.services.db_service import audit_insert
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "查看理由必填（≥5 字）")
    with session() as db:
        ctx = build_affairs_context(user, db)
        s = ctx.require_student(db, int(student_id))
        if not has_permission(user, "academicAffairs.roster.viewSensitive"):
            audit_insert("SENSITIVE_VIEW", "student_profile",
                         {"studentId": str(student_id), "reason": reason, "granted": False}, "DENY")
            raise no_permission("无学籍证件号完整查看权限")
        audit_insert("SENSITIVE_VIEW", "student_profile",
                     {"studentId": str(student_id), "reason": reason, "granted": True}, "SUCCESS")
        return {"studentId": str(s.id), "idCard": s.id_card_encrypted or ""}


def roster_status_summary(user) -> dict:
    """学籍状态总览（Tier1「学籍状态」）：真实 13 态分布（受控扩展枚举，见 academic_affairs_status_service.STATUSES）
    + 在籍/非在籍 + 近 30 天生效异动数，数据范围与 status-changes 同口径（COLLEGE/CLASS 按 allowed_class_ids 收敛）。
    """
    from app.models import AaStatusChange, StudentProfile
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled
    with session() as db:
        ctx = build_affairs_context(user, db)
        conds = [StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)]
        allowed = ctx.allowed_class_ids(db)
        if allowed is not None:
            conds.append(StudentProfile.class_id.in_(list(allowed)) if allowed else (StudentProfile.id == -1))
        rows = db.scalars(select(StudentProfile).where(*conds)).all()
        by_status: dict = {}
        enrolled_count = 0
        for s in rows:
            by_status[s.student_status] = by_status.get(s.student_status, 0) + 1
            if is_enrolled(s.student_status):
                enrolled_count += 1
        since = datetime.utcnow() - timedelta(days=30)
        sc_conds = [AaStatusChange.tenant_id == _tid(), AaStatusChange.is_deleted.is_(False),
                   AaStatusChange.status == "EFFECTIVE", AaStatusChange.effective_date >= since]
        if allowed is not None:
            if allowed:
                sc_conds.append(or_(AaStatusChange.from_class_id.in_(list(allowed)),
                                    AaStatusChange.to_class_id.in_(list(allowed))))
            else:
                sc_conds.append(AaStatusChange.id == -1)
        recent = db.scalar(select(func.count()).select_from(AaStatusChange).where(*sc_conds)) or 0
        return {
            "total": len(rows),
            "byStatus": [{"status": k, "label": _STATUS_LABEL.get(k, k), "count": v}
                        for k, v in sorted(by_status.items(), key=lambda x: -x[1])],
            "enrolledCount": enrolled_count, "notEnrolledCount": len(rows) - enrolled_count,
            "recentChanges30d": int(recent),
        }


# ═══════════ 学籍导入导出（Tier1 R2：批量建档 + 台账导出）═══════════
# 设计取舍（dedup 核查记录）：仓库已有两套导入导出机制——① app.services.domain_import_service 的 6 域内存态引擎
# （DOMAINS 字典仅支持"单主键+姓名"极简 schema，无持久化 job 记录，不含学院/专业/班级/身份证/初始学籍状态等
# 学籍档案所需字段，若强行套用需大改其 dry_run/confirm 内部逻辑，等同重写）；② app.services.excel 公共底座
# （ColumnSpec/ImportSpec 声明式配置 + 模板/校验/错误行/t_excel_import_job 持久化，已被 graduation_student /
# internship 等模块验证为生产级方案）。本轮选②扩展，不选①，避免在不匹配 schema 上二次改造。
# 导出沿用本模块（academic_affairs_service）内既有 export_unregistered_xlsx 同款 xlsx_util.build_ledger_xlsx +
# 用途≥5字 + StreamingResponse 直出模式，与同模块既有导出端点口径一致（不额外引入 excel.ExportSpec 的 base64 包装）。

_ROSTER_INITIAL_STATUSES = {"PENDING_REGISTER", "NORMAL", "REGISTERED"}


def export_roster_xlsx(user, purpose="", keyword=None, status=None) -> bytes:
    """导出学籍名册 .xlsx（首行水印 + 审计），与学籍名册列表同口径同数据；班级列解析为真实班级名（roster() 原样返回
    class_id 字符串，仅列表页历史行为，本导出单独解析，不改动既有 roster()/学籍名册页契约）。"""
    purpose = (purpose or "").strip()
    if len(purpose) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    from app.services.xlsx_util import build_ledger_xlsx
    rows_data, _total = roster(user, keyword, status, page=1, page_size=10000)
    with session() as db:
        class_ids = {int(r["className"]) for r in rows_data if (r.get("className") or "").isdigit()}
        name_map = _resolve_class_name_map(db, class_ids)
    _n, _r, _uid = _op()
    watermark = f"导出人：{_n or '-'}  时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose}"
    headers = ["学号", "姓名", "班级", "学籍状态", "是否在籍", "身份证（脱敏）"]
    rows = [[r["studentNo"], r["realName"], name_map.get(r["className"], r["className"]),
             _STATUS_LABEL.get(r["studentStatus"], r["studentStatus"]),
             ("在籍" if r["enrolled"] else "非在籍"), r["idCardMasked"] or ""]
            for r in rows_data]
    content = build_ledger_xlsx("学籍名册", headers, rows, watermark=watermark)
    with session() as db:
        _audit(db, "AA_ROSTER", None, "EXPORT", f"用途={purpose[:100]} rows={len(rows)}")
        db.commit()
    return content


def _resolve_class_name_map(db, class_ids) -> dict:
    from app.models import SchoolClass
    if not class_ids:
        return {}
    rows = db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == _tid(), SchoolClass.id.in_(list(class_ids)))).all()
    return {str(c.id): c.class_name for c in rows}


def _roster_import_dup_check(rows: list) -> dict:
    """库内学号查重（studentNo 已存在于 t_student_profile）。"""
    from app.models import StudentProfile
    nos = {(r.get("studentNo") or "").strip() for r in rows if r.get("studentNo")}
    if not nos:
        return {}
    with session() as db:
        existing = {s.student_no for s in db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.student_no.in_(list(nos)),
            StudentProfile.is_deleted.is_(False))).all()}
    errors = {}
    for i, r in enumerate(rows, start=1):
        no = (r.get("studentNo") or "").strip()
        if no and no in existing:
            errors[i] = f"学号 {no} 已存在于学籍主档"
    return errors


def _roster_import_business_validate(row: dict, row_no: int) -> str | None:
    class_name = (row.get("className") or "").strip()
    with session() as db:
        from app.models import SchoolClass
        matches = db.scalars(select(SchoolClass).where(
            SchoolClass.tenant_id == _tid(), SchoolClass.class_name == class_name,
            SchoolClass.is_deleted.is_(False))).all()
    if not matches:
        return f"班级「{class_name}」不存在，请先在学院专业班级维护"
    if len(matches) > 1:
        return f"班级「{class_name}」存在 {len(matches)} 个同名班级，无法唯一定位，请联系教务处处理重名"
    init_status = (row.get("initialStatus") or "").strip()
    if init_status and init_status not in _ROSTER_INITIAL_STATUSES:
        return f"初始学籍状态须为 {'/'.join(sorted(_ROSTER_INITIAL_STATUSES))} 之一，休学/退学等须导入后走学籍异动办理"
    return None


def _persist_roster_rows(rows: list) -> dict:
    import hashlib

    from app.models import Major, SchoolClass, StudentProfile, StudentStageEvent
    created = 0
    with session() as db:
        for r in rows or []:
            class_name = (r.get("className") or "").strip()
            cls = db.scalars(select(SchoolClass).where(
                SchoolClass.tenant_id == _tid(), SchoolClass.class_name == class_name,
                SchoolClass.is_deleted.is_(False))).first()
            if not cls:
                continue  # 已在预校验拦截，防御性跳过（理论不可达）
            major = db.get(Major, cls.major_id) if cls.major_id else None
            id_card = (r.get("idCard") or "").strip()
            init_status = (r.get("initialStatus") or "").strip() or "PENDING_REGISTER"
            s = StudentProfile(
                tenant_id=_tid(), student_no=(r.get("studentNo") or "").strip(),
                real_name=(r.get("realName") or "").strip(), gender=(r.get("gender") or "").strip() or None,
                id_card_encrypted=(id_card or None),
                id_card_hash=(hashlib.sha256(id_card.encode()).hexdigest() if id_card else None),
                college_id=(major.college_id if major else None), major_id=cls.major_id,
                class_id=cls.id, grade=cls.grade, current_stage="ENROLLED",
                student_status=init_status, status="ACTIVE")
            db.add(s)
            db.flush()
            db.add(StudentStageEvent(tenant_id=_tid(), student_id=s.id, from_stage=None, to_stage=init_status,
                                     reason="学籍导入建档", source_module="academic-affairs"))
            _audit(db, "AA_ROSTER", s.id, "IMPORT", s.student_no)
            created += 1
        db.commit()
    return {"created": created}


def build_roster_import_spec():
    from app.services import excel
    C = excel.ColumnSpec
    return excel.ImportSpec(
        module_key="academicAffairs", biz_type="roster", template_name="学籍导入",
        columns=[
            C("studentNo", "学号", required=True, max_length=50, example="2026115001",
              unique_in_file=True, help_text="须唯一，不可与库内已有学号重复"),
            C("realName", "姓名", required=True, max_length=100, example="张三"),
            C("gender", "性别", type="enum", options=["男", "女"], example="男"),
            C("idCard", "身份证号", type="idcard", example="", help_text="选填；18 位，入库后脱敏展示，不导出明文"),
            C("className", "班级", required=True, max_length=200, example="软件2601",
              help_text="须为「学院专业班级」中已存在的行政班名称，且租户内不可重名"),
            C("initialStatus", "初始学籍状态", type="enum",
              options=sorted(_ROSTER_INITIAL_STATUSES), example="PENDING_REGISTER",
              help_text="选填，默认待注册 PENDING_REGISTER；不可直接导入休学/退学等中间态，须导入后走「学籍异动」办理"),
        ],
        notes=[
            "1. 仅导入「导入模板」页；第一行表头请勿改动。",
            "2. 带 * 为必填：学号、姓名、班级。",
            "3. 班级须为学院专业班级中已建好的行政班，按名称精确匹配；同名班级会导致该行拦截。",
            "4. 初始学籍状态仅允许 待注册(PENDING_REGISTER)/正常(NORMAL)/在籍注册(REGISTERED)；",
            "   休学/退学/转专业等须导入建档后走「学籍异动」办理，不接受直接导入。",
            "5. 身份证号选填，入库后按平台规则脱敏展示，不回传明文。",
        ],
        duplicate_check=_roster_import_dup_check,
        business_validate=_roster_import_business_validate,
        persist_rows=_persist_roster_rows,
        permission_key="academicAffairs.roster.import",
        audit_action="导入学籍名册",
    )


def roster_import_template_bytes() -> bytes:
    from app.services import excel
    return excel.build_template(build_roster_import_spec())


def roster_import_read(content: bytes) -> list:
    from app.services import excel
    return excel.read_upload(build_roster_import_spec(), content)


def roster_import_errors_pack(rows: list, errors: list) -> dict:
    from app.services import excel
    return excel.build_error_rows(build_roster_import_spec(), rows, errors)


def roster_import_dry_run(rows: list) -> dict:
    from app.services import excel
    return excel.pre_validate(build_roster_import_spec(), rows)


def roster_import_confirm(rows: list) -> dict:
    from app.services import excel
    spec = build_roster_import_spec()
    pre = excel.pre_validate(spec, rows)
    result = excel.confirm_import(spec, rows)
    excel.job_service.record_import(spec.module_key, spec.biz_type, pre=pre, result=result, status="IMPORTED")
    return {"created": result.get("created", 0)}


# ═══════════ 入学/学年注册 ═══════════

def create_registration_batch(body, user) -> dict:
    with session() as db:
        from app.models import AaRegistrationBatch
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        rtype = (body.registerType or "ENROLL")
        if rtype not in ("ENROLL", "ANNUAL"):
            raise AppException("VALIDATION_ERROR", "注册类型非法")
        guard_term_writable(db, getattr(body, "termId", None))  # 归档11卡§6.2：已归档学期不应再开注册批次
        b = AaRegistrationBatch(tenant_id=_tid(), batch_name=body.batchName, register_type=rtype,
                                term_id=(int(body.termId) if getattr(body, "termId", None) else None),
                                window_start=_parse_dt(getattr(body, "windowStart", None)),
                                window_end=_parse_dt(getattr(body, "windowEnd", None)),
                                status=("OPEN" if getattr(body, "open", False) else "DRAFT"))
        db.add(b)
        db.flush()
        _audit(db, "AA_REG_BATCH", b.id, "CREATE", rtype)
        db.commit()
        db.refresh(b)
        return {"batchId": str(b.id), "batchName": b.batch_name, "registerType": b.register_type,
                "status": b.status}


def list_registration_batches(user, status=None, page=1, page_size=20, register_type=None):
    """注册批次列表。register_type 传 ENROLL/ANNUAL 时收窄为「入学注册」/「学年注册」两个三级叶子视图，
    不传时为原「注册批次」通栏视图（两者共用同一批次引擎，不建重复表）。"""
    from app.models import AaRegistrationBatch
    with session() as db:
        conds = [AaRegistrationBatch.tenant_id == _tid(), AaRegistrationBatch.is_deleted.is_(False)]
        if status:
            conds.append(AaRegistrationBatch.status == status)
        if register_type:
            conds.append(AaRegistrationBatch.register_type == register_type)
        rows = db.scalars(select(AaRegistrationBatch).where(*conds).order_by(
            AaRegistrationBatch.id.desc())).all()
        out = [{"batchId": str(b.id), "batchName": b.batch_name, "registerType": b.register_type,
                "status": b.status} for b in rows]
        return out[(max(1, page) - 1) * page_size:(max(1, page) - 1) * page_size + page_size], len(out)


def _precheck(db, student_id) -> dict:
    """注册预检：只读迎新台账（报到/缴费/材料/绿通），不复制。无迎新数据则默认通过。"""
    from app.models import OrientationStudent, StudentProfile
    s = db.get(StudentProfile, int(student_id))
    ori = db.scalars(select(OrientationStudent).where(
        OrientationStudent.tenant_id == _tid(),
        OrientationStudent.name == (s.real_name if s else ""),
        OrientationStudent.is_deleted.is_(False))).first() if s else None
    if not ori:
        return {"reported": True, "paid": True, "material": True, "greenChannel": False,
                "note": "无迎新台账，默认通过"}
    return {"reported": getattr(ori, "report_status", None) in (None, "REPORTED", "DONE"),
            "paid": True, "material": True, "greenChannel": False}


def register_student(batch_id, user, student_id) -> dict:
    """学生注册：预检 → 写注册记录 REGISTERED → change_student_status(REGISTERED) 单一入口。"""
    _n, _r, uid = _op()
    with session() as db:
        from app.models import AaRegistration, AaRegistrationBatch, StudentProfile
        from app.modules.academic_affairs.services.academic_affairs_archive_service import guard_term_writable
        b = db.get(AaRegistrationBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("注册批次不存在")
        guard_term_writable(db, b.term_id)  # 归档11卡§6.2：已归档学期不应受理新注册
        if b.status != "OPEN":
            raise AppException("DATA_CONFLICT", "注册批次未开放或已关闭")
        s = db.get(StudentProfile, int(student_id))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在")
        dup = db.scalars(select(AaRegistration).where(
            AaRegistration.tenant_id == _tid(), AaRegistration.batch_id == b.id,
            AaRegistration.student_id == int(student_id), AaRegistration.is_deleted.is_(False))).first()
        if dup and dup.status == "REGISTERED":
            raise AppException("DATA_CONFLICT", "该生已在本批次完成注册")
        snap = _precheck(db, student_id)
        change_type = "ENROLL_REGISTER" if b.register_type == "ENROLL" else "ANNUAL_REGISTER"
        from_status = s.student_status
        rec = dup or AaRegistration(tenant_id=_tid(), batch_id=b.id, student_id=int(student_id))
        rec.precheck_json = json.dumps(snap, ensure_ascii=False)
        rec.register_at = datetime.utcnow()
        rec.operator_id = int(uid) if uid.isdigit() else None
        rec.status = "REGISTERED"
        if not dup:
            db.add(rec)
            db.flush()
        # 单一写入口更新主档学籍状态
        res = change_student_status(db, student_id, "REGISTERED", change_type=change_type,
                                    reason=f"{b.register_type}注册", operator=uid, source_biz_id=rec.id)
        _audit(db, "AA_REGISTRATION", rec.id, "REGISTER", change_type)
        db.commit()
        db.refresh(rec)
    # 事务外落安全审计
    audit_status_change(student_id, res["fromStatus"], res["toStatus"], change_type, uid)
    return {"registrationId": str(rec.id), "studentId": str(student_id), "status": "REGISTERED",
            "studentStatus": "REGISTERED", "changeType": change_type, "precheck": snap}


def list_registrations(batch_id, user, page=1, page_size=50):
    from app.models import AaRegistration, StudentProfile
    with session() as db:
        join = and_(StudentProfile.id == AaRegistration.student_id,
                    StudentProfile.tenant_id == AaRegistration.tenant_id)
        conds = [AaRegistration.tenant_id == _tid(), AaRegistration.batch_id == int(batch_id),
                 AaRegistration.is_deleted.is_(False)]
        total = db.scalar(select(func.count()).select_from(AaRegistration)
                          .outerjoin(StudentProfile, join).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.execute(select(AaRegistration, StudentProfile)
                          .outerjoin(StudentProfile, join).where(*conds)
                          .order_by(AaRegistration.id.desc()).offset(offset).limit(page_size)).all()
        out = [{"registrationId": str(x.id), "studentId": str(x.student_id),
                "realName": s.real_name if s else "", "status": x.status,
                "registerAt": _iso(x.register_at)} for x, s in rows]
        return out, total


# ═══════════ 注册管理 Tier1 R1：注册资格核验 / 未注册学生 / 暂缓注册 / 注册异常 ═══════════
# 与「注册批次」共用 t_aa_registration_batch/t_aa_registration 引擎，不新建候选人表。
# 数据范围统一走 build_affairs_context（COLLEGE=本院学院教务；TENANT_ALL=教务处/学校管理员）。

_EXCEPTION_TYPES = ("IDENTITY_MISMATCH", "UNPAID", "MATERIAL_MISSING", "OTHER")


def _require_school_scope(ctx):
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("仅教务处可执行该操作")


def _counselor_of(db, student_id):
    from app.models import SchoolClass, StudentProfile
    s = db.get(StudentProfile, int(student_id))
    if not s or not s.class_id:
        return 0
    c = db.get(SchoolClass, int(s.class_id))
    return int(c.counselor_id) if c and c.counselor_id else 0


def _push_todo(db, biz_type, biz_id, todo_type, assignee_id, student_id, title) -> bool:
    """统一待办（幂等：同来源+同类型+同责任人只一条）。assignee_id=0（无绑定辅导员）不推送。"""
    if not assignee_id:
        return False
    from app.models import UnifiedTodo
    exist = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(), UnifiedTodo.source_module == "academic-affairs",
        UnifiedTodo.source_biz_id == int(biz_id), UnifiedTodo.todo_type == todo_type,
        UnifiedTodo.assignee_id == int(assignee_id), UnifiedTodo.is_deleted.is_(False))).first()
    if exist:
        return False
    db.add(UnifiedTodo(tenant_id=_tid(), source_module="academic-affairs", source_biz_type=biz_type,
                       source_biz_id=int(biz_id), todo_type=todo_type, assignee_id=int(assignee_id),
                       student_id=int(student_id) if student_id else None, title=title[:490], status="PENDING"))
    return True


# ── 批次候选学生（资格核验/未注册/扫描共用）──

def _batch_target_statuses(batch) -> tuple:
    """批次类型圈定的候选学籍状态池：ENROLL=待注册在籍生；ANNUAL=在籍待续生（含留级编入）。"""
    return ("PENDING_REGISTER",) if batch.register_type == "ENROLL" else ("REGISTERED", "RETAINED")


def _batch_pending_candidates(db, batch, allowed=None) -> list:
    """本批次尚未完成注册的候选学生：命中批次目标学籍状态池，且本批次内无 REGISTERED 记录
    （ANNUAL 候选池本身即 REGISTERED，必须以本批次注册记录而非主档状态判定是否已完成本轮）。
    allowed=None 不限范围；allowed=空集合 fail-closed 返回 []。返回 [(StudentProfile, AaRegistration|None), ...]。"""
    from app.models import AaRegistration, StudentProfile
    if allowed is not None and not allowed:
        return []
    target_statuses = _batch_target_statuses(batch)
    conds = [StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
             StudentProfile.student_status.in_(target_statuses)]
    if allowed is not None:
        conds.append(StudentProfile.class_id.in_(allowed))
    students = db.scalars(select(StudentProfile).where(*conds).order_by(StudentProfile.id.desc())).all()
    if not students:
        return []
    regs = {r.student_id: r for r in db.scalars(select(AaRegistration).where(
        AaRegistration.tenant_id == _tid(), AaRegistration.batch_id == batch.id,
        AaRegistration.student_id.in_([s.id for s in students]), AaRegistration.is_deleted.is_(False))).all()}
    out = []
    for s in students:
        r = regs.get(s.id)
        if r and r.status == "REGISTERED":
            continue
        out.append((s, r))
    return out


# ── 注册资格核验 ──

def list_registration_eligibility(batch_id, user, status=None, keyword=None, page=1, page_size=20):
    """核验候选名单：按批次类型圈定候选学生(ENROLL=待注册在籍/ANNUAL=在籍待续)，
    排除本批次已完成注册者，左连既有核验记录展示核验结果。"""
    from app.models import AaRegistrationBatch
    with session() as db:
        ctx = build_affairs_context(user, db)
        b = db.get(AaRegistrationBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("注册批次不存在")
        allowed = ctx.allowed_class_ids(db)
        pairs = _batch_pending_candidates(db, b, allowed)
        out = []
        for s, r in pairs:
            if keyword and keyword not in (s.real_name or "") and keyword not in (s.student_no or ""):
                continue
            elig = r.eligibility_status if r else "PENDING"
            if status and elig != status:
                continue
            out.append({
                "studentId": str(s.id), "studentNo": s.student_no, "realName": s.real_name,
                "classId": str(s.class_id or ""), "registrationStatus": (r.status if r else "PENDING_REGISTER"),
                "eligibilityStatus": elig, "eligibilityNote": (r.eligibility_note if r else "") or "",
                "eligibilityCheckedAt": _iso(r.eligibility_checked_at) if r else None,
            })
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def verify_registration_eligibility(batch_id, user, student_id, result, note=None, exception_type=None):
    """核验：ELIGIBLE 只写核验结果（不推进 status，register_student 仍是唯一注册入口）；
    INELIGIBLE 写核验结果 + 转注册异常（复用 _create_exception_row）+ 通知辅导员。"""
    if result not in ("ELIGIBLE", "INELIGIBLE"):
        raise AppException("VALIDATION_ERROR", "核验结果非法")
    _n, _r, uid = _op()
    with session() as db:
        from app.models import AaRegistration, AaRegistrationBatch
        ctx = build_affairs_context(user, db)
        b = db.get(AaRegistrationBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("注册批次不存在")
        if b.status != "OPEN":
            raise AppException("DATA_CONFLICT", "注册批次未开放或已关闭", http_status=409)
        s = ctx.require_student(db, student_id)
        note = (note or "").strip()
        if result == "INELIGIBLE" and not note:
            raise AppException("VALIDATION_ERROR", "不合格需填写核验意见")
        reg = db.scalars(select(AaRegistration).where(
            AaRegistration.tenant_id == _tid(), AaRegistration.batch_id == b.id,
            AaRegistration.student_id == int(student_id), AaRegistration.is_deleted.is_(False))).first()
        if reg and reg.status == "REGISTERED":
            raise AppException("DATA_CONFLICT", "该生已完成注册，无需再核验", http_status=409)
        if not reg:
            reg = AaRegistration(tenant_id=_tid(), batch_id=b.id, student_id=int(student_id))
            reg.precheck_json = json.dumps(_precheck(db, student_id), ensure_ascii=False)
            db.add(reg)
            db.flush()
        reg.eligibility_status = result
        reg.eligibility_note = note or None
        reg.eligibility_checked_at = datetime.utcnow()
        reg.eligibility_checked_by = int(uid) if uid.isdigit() else None
        _audit(db, "AA_REGISTRATION", reg.id, "ELIGIBILITY_VERIFY", f"{result}:{note}")
        exc_id = None
        if result == "INELIGIBLE":
            etype = exception_type if exception_type in _EXCEPTION_TYPES else "OTHER"
            exc = _create_exception_row(db, b, student_id, etype, note, registration_id=reg.id)
            exc_id = exc.id
            cid = _counselor_of(db, student_id)
            _push_todo(db, "AA_REGISTRATION_EXCEPTION", exc.id, "AA_REG_EXCEPTION_HANDLE", cid, student_id,
                      f"{s.real_name} 注册资格核验不合格：{note[:50]}")
        db.commit()
        db.refresh(reg)
        return {"registrationId": str(reg.id), "studentId": str(student_id),
                "eligibilityStatus": reg.eligibility_status, "eligibilityNote": reg.eligibility_note or "",
                "exceptionId": (str(exc_id) if exc_id else None)}


# ── 注册异常 ──

def _create_exception_row(db, batch, student_id, exception_type, description, registration_id=None):
    from app.models import AaRegistrationException
    exc = AaRegistrationException(tenant_id=_tid(), batch_id=batch.id, registration_id=registration_id,
                                  student_id=int(student_id), exception_type=exception_type,
                                  description=(description or "").strip() or None, status="OPEN")
    db.add(exc)
    db.flush()
    _audit(db, "AA_REG_EXCEPTION", exc.id, "MARK_ABNORMAL", exception_type)
    return exc


def _exception_row(e):
    return {"exceptionId": str(e.id), "batchId": str(e.batch_id), "studentId": str(e.student_id),
            "exceptionType": e.exception_type, "description": e.description or "",
            "status": e.status, "resolutionNote": e.resolution_note or "", "resolvedAt": _iso(e.resolved_at)}


def create_registration_exception(batch_id, user, student_id, exception_type, description=None):
    if exception_type not in _EXCEPTION_TYPES:
        raise AppException("VALIDATION_ERROR", "异常类型非法")
    description = (description or "").strip()
    if exception_type == "OTHER" and not description:
        raise AppException("VALIDATION_ERROR", "异常类型为「其他」时需填写说明")
    with session() as db:
        from app.models import AaRegistration, AaRegistrationBatch
        ctx = build_affairs_context(user, db)
        b = db.get(AaRegistrationBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("注册批次不存在")
        s = ctx.require_student(db, student_id)
        reg = db.scalars(select(AaRegistration).where(
            AaRegistration.tenant_id == _tid(), AaRegistration.batch_id == b.id,
            AaRegistration.student_id == int(student_id), AaRegistration.is_deleted.is_(False))).first()
        exc = _create_exception_row(db, b, student_id, exception_type, description,
                                    registration_id=(reg.id if reg else None))
        if reg:
            reg.eligibility_status = "INELIGIBLE"
            reg.eligibility_note = description or exception_type
        cid = _counselor_of(db, student_id)
        _push_todo(db, "AA_REGISTRATION_EXCEPTION", exc.id, "AA_REG_EXCEPTION_HANDLE", cid, student_id,
                  f"{s.real_name} 注册异常：{(description[:50] if description else exception_type)}")
        db.commit()
        db.refresh(exc)
        return _exception_row(exc)


def list_registration_exceptions(user, batch_id=None, status=None, page=1, page_size=20):
    from app.models import AaRegistrationException, StudentProfile
    with session() as db:
        ctx = build_affairs_context(user, db)
        conds = [AaRegistrationException.tenant_id == _tid(), AaRegistrationException.is_deleted.is_(False)]
        if batch_id:
            conds.append(AaRegistrationException.batch_id == int(batch_id))
        if status:
            conds.append(AaRegistrationException.status == status)
        allowed = ctx.allowed_class_ids(db)
        if allowed is not None:
            if not allowed:
                return [], 0
            sids = db.scalars(select(StudentProfile.id).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.class_id.in_(allowed))).all()
            conds.append(AaRegistrationException.student_id.in_(list(sids) or [-1]))
        rows = db.scalars(select(AaRegistrationException).where(*conds).order_by(
            AaRegistrationException.id.desc())).all()
        total = len(rows)
        start = (max(1, page) - 1) * page_size
        page_rows = rows[start:start + page_size]
        prof = {p.id: p for p in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_([e.student_id for e in page_rows] or [-1]))).all()}
        out = []
        for e in page_rows:
            d = _exception_row(e)
            p = prof.get(e.student_id)
            d["realName"] = p.real_name if p else ""
            d["studentNo"] = p.student_no if p else ""
            out.append(d)
        return out, total


def resolve_registration_exception(exception_id, user, note):
    from app.models import AaRegistrationException
    note = (note or "").strip()
    if not note:
        raise AppException("VALIDATION_ERROR", "处理说明必填")
    _n, _r, uid = _op()
    with session() as db:
        ctx = build_affairs_context(user, db)
        exc = db.get(AaRegistrationException, int(exception_id))
        if not exc or exc.is_deleted or exc.tenant_id != _tid():
            raise not_found("注册异常不存在")
        ctx.require_student(db, exc.student_id)
        if exc.status == "RESOLVED":
            raise AppException("DATA_CONFLICT", "该异常已处理", http_status=409)
        exc.status = "RESOLVED"
        exc.resolution_note = note
        exc.resolved_at = datetime.utcnow()
        exc.resolved_by = int(uid) if uid.isdigit() else None
        _audit(db, "AA_REG_EXCEPTION", exc.id, "RESOLVE", note)
        db.commit()
        db.refresh(exc)
        return _exception_row(exc)


# ── 暂缓注册 ──

def _deferral_row(d):
    return {"deferralId": str(d.id), "batchId": str(d.batch_id), "studentId": str(d.student_id),
            "reason": d.reason, "requestedUntil": _iso(d.requested_until), "status": d.status,
            "reviewNote": d.review_note or "", "reviewedAt": _iso(d.reviewed_at)}


def apply_registration_deferral(batch_id, user, student_id, reason, requested_until=None):
    reason = (reason or "").strip()
    if len(reason) < 2:
        raise AppException("VALIDATION_ERROR", "暂缓原因必填")
    with session() as db:
        from app.models import AaRegistrationBatch, AaRegistrationDeferral
        ctx = build_affairs_context(user, db)
        b = db.get(AaRegistrationBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("注册批次不存在")
        s = ctx.require_student(db, student_id)
        if s.student_status not in ("PENDING_REGISTER", "UNREGISTERED"):
            raise AppException("DATA_CONFLICT", "该生当前学籍状态不可申请暂缓注册", http_status=409)
        dup = db.scalars(select(AaRegistrationDeferral).where(
            AaRegistrationDeferral.tenant_id == _tid(), AaRegistrationDeferral.batch_id == b.id,
            AaRegistrationDeferral.student_id == int(student_id), AaRegistrationDeferral.status == "PENDING",
            AaRegistrationDeferral.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该生在本批次已有待审的暂缓申请", http_status=409)
        d = AaRegistrationDeferral(tenant_id=_tid(), batch_id=b.id, student_id=int(student_id), reason=reason,
                                   requested_until=_parse_dt(requested_until), status="PENDING")
        db.add(d)
        db.flush()
        _audit(db, "AA_REG_DEFERRAL", d.id, "APPLY", reason)
        db.commit()
        db.refresh(d)
        return _deferral_row(d)


def list_registration_deferrals(user, batch_id=None, status=None, page=1, page_size=20):
    from app.models import AaRegistrationDeferral, StudentProfile
    with session() as db:
        ctx = build_affairs_context(user, db)
        conds = [AaRegistrationDeferral.tenant_id == _tid(), AaRegistrationDeferral.is_deleted.is_(False)]
        if batch_id:
            conds.append(AaRegistrationDeferral.batch_id == int(batch_id))
        if status:
            conds.append(AaRegistrationDeferral.status == status)
        allowed = ctx.allowed_class_ids(db)
        if allowed is not None:
            if not allowed:
                return [], 0
            sids = db.scalars(select(StudentProfile.id).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.class_id.in_(allowed))).all()
            conds.append(AaRegistrationDeferral.student_id.in_(list(sids) or [-1]))
        rows = db.scalars(select(AaRegistrationDeferral).where(*conds).order_by(
            AaRegistrationDeferral.id.desc())).all()
        total = len(rows)
        start = (max(1, page) - 1) * page_size
        page_rows = rows[start:start + page_size]
        prof = {p.id: p for p in db.scalars(select(StudentProfile).where(
            StudentProfile.id.in_([d.student_id for d in page_rows] or [-1]))).all()}
        out = []
        for d in page_rows:
            row = _deferral_row(d)
            p = prof.get(d.student_id)
            row["realName"] = p.real_name if p else ""
            row["studentNo"] = p.student_no if p else ""
            out.append(row)
        return out, total


def review_registration_deferral(deferral_id, user, action, note=None):
    from app.models import AaRegistrationDeferral
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "非法动作")
    note = (note or "").strip()
    if action == "REJECT" and not note:
        raise AppException("VALIDATION_ERROR", "驳回需填写理由")
    _n, _r, uid = _op()
    with session() as db:
        ctx = build_affairs_context(user, db)
        d = db.get(AaRegistrationDeferral, int(deferral_id))
        if not d or d.is_deleted or d.tenant_id != _tid():
            raise not_found("暂缓注册申请不存在")
        ctx.require_student(db, d.student_id)
        if d.status != "PENDING":
            raise AppException("DATA_CONFLICT", "该申请已处理", http_status=409)
        d.status = "APPROVED" if action == "APPROVE" else "REJECTED"
        d.review_note = note or None
        d.reviewed_at = datetime.utcnow()
        d.reviewed_by = int(uid) if uid.isdigit() else None
        _audit(db, "AA_REG_DEFERRAL", d.id, action, note)
        db.commit()
        db.refresh(d)
        return _deferral_row(d)


# ── 未注册学生 ──

def _active_deferred_sids(db, batch, now=None) -> set:
    """本批次当前仍在有效期内的已批准暂缓注册学生集合（scan_unregistered 与未注册名单共用口径）。"""
    from app.models import AaRegistrationDeferral
    now = now or datetime.utcnow()
    return {d.student_id for d in db.scalars(select(AaRegistrationDeferral).where(
        AaRegistrationDeferral.tenant_id == _tid(), AaRegistrationDeferral.batch_id == batch.id,
        AaRegistrationDeferral.status == "APPROVED", AaRegistrationDeferral.is_deleted.is_(False),
        or_(AaRegistrationDeferral.requested_until.is_(None),
            AaRegistrationDeferral.requested_until >= now))).all()}


def list_unregistered_students(user, batch_id=None, page=1, page_size=20):
    """未注册学生：①本批次已判定 UNREGISTERED（记在 AaRegistration.status；ENROLL 同步主档 student_status，
    ANNUAL 因主档已是 REGISTERED、状态机不允许倒退，仅批次内记账+通知，不改主档——见 scan_unregistered）；
    ②批次窗口已截止但仍待扫描（含从未产生注册记录的候选人，经 _batch_pending_candidates 圈定）。"""
    from app.models import AaRegistration, AaRegistrationBatch, StudentProfile
    with session() as db:
        ctx = build_affairs_context(user, db)
        allowed = ctx.allowed_class_ids(db)
        if allowed is not None and not allowed:
            return [], 0

        def _in_scope(s):
            return allowed is None or (s.class_id in allowed)

        out, batch_cache = [], {}

        def _get_batch(bid):
            if bid not in batch_cache:
                batch_cache[bid] = db.get(AaRegistrationBatch, bid)
            return batch_cache[bid]

        reg_conds = [AaRegistration.tenant_id == _tid(), AaRegistration.is_deleted.is_(False),
                    AaRegistration.status == "UNREGISTERED"]
        if batch_id:
            reg_conds.append(AaRegistration.batch_id == int(batch_id))
        unreg_regs = db.scalars(select(AaRegistration).where(*reg_conds).order_by(AaRegistration.id.desc())).all()
        if unreg_regs:
            profs = {p.id: p for p in db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id.in_([r.student_id for r in unreg_regs]))).all()}
            for r in unreg_regs:
                s = profs.get(r.student_id)
                if not s or not _in_scope(s):
                    continue
                b = _get_batch(r.batch_id)
                out.append({"studentId": str(s.id), "studentNo": s.student_no, "realName": s.real_name,
                           "classId": str(s.class_id or ""), "batchId": str(r.batch_id),
                           "batchName": (b.batch_name if b else ""), "registerType": (b.register_type if b else ""),
                           "windowEnd": (_iso(b.window_end) if b else None), "kind": "UNREGISTERED"})

        now = datetime.utcnow()
        b_conds = [AaRegistrationBatch.tenant_id == _tid(), AaRegistrationBatch.is_deleted.is_(False),
                  AaRegistrationBatch.status == "OPEN", AaRegistrationBatch.window_end.isnot(None),
                  AaRegistrationBatch.window_end < now]
        if batch_id:
            b_conds.append(AaRegistrationBatch.id == int(batch_id))
        open_batches = db.scalars(select(AaRegistrationBatch).where(*b_conds)).all()
        for b in open_batches:
            deferred = _active_deferred_sids(db, b, now)
            for s, r in _batch_pending_candidates(db, b, allowed):
                if r and r.status == "UNREGISTERED":
                    continue  # 已在①列出，避免重复
                if s.id in deferred:
                    continue  # 已批准暂缓且未过期，不算逾期
                out.append({"studentId": str(s.id), "studentNo": s.student_no, "realName": s.real_name,
                           "classId": str(s.class_id or ""), "batchId": str(b.id), "batchName": b.batch_name,
                           "registerType": b.register_type, "windowEnd": _iso(b.window_end),
                           "kind": "OVERDUE_PENDING_SCAN"})
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def scan_unregistered(batch_id, user):
    """批次窗口截止扫描：圈定尚未完成本批次注册且无有效(未过期)暂缓批准的候选人。
    ENROLL 候选人主档仍 PENDING_REGISTER → 经 change_student_status 单一入口转 UNREGISTERED（真实终态）；
    ANNUAL 候选人主档已是 REGISTERED/RETAINED（状态机不允许 REGISTERED→UNREGISTERED 倒退，见 status_service
    白名单），仅置本批次注册记录为 UNREGISTERED + 通知辅导员，主档留给学院走正式异动流程处理。
    仅教务处（TENANT_ALL）可执行；幂等（重复扫描不重复转移/不重复推送）。"""
    from app.models import AaRegistration, AaRegistrationBatch
    _n, _r, uid = _op()
    now = datetime.utcnow()
    changes = []
    with session() as db:
        ctx = build_affairs_context(user, db)
        _require_school_scope(ctx)
        b = db.get(AaRegistrationBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("注册批次不存在")
        if b.status != "OPEN":
            raise AppException("DATA_CONFLICT", "仅开放中的批次可执行未注册扫描", http_status=409)
        if not b.window_end or b.window_end >= now:
            raise AppException("VALIDATION_ERROR", "该批次尚未设置截止时间或未到期，暂不可扫描")
        candidates = _batch_pending_candidates(db, b, None)  # 教务处全校执行，不受操作者数据范围收窄
        deferred_sids = _active_deferred_sids(db, b, now)
        marked = skipped = notified = 0
        for s, r in candidates:
            if r and r.status == "UNREGISTERED":
                continue  # 已扫描过，幂等跳过
            if s.id in deferred_sids:
                skipped += 1
                continue
            if not r:
                r = AaRegistration(tenant_id=_tid(), batch_id=b.id, student_id=s.id, status="PENDING_REGISTER")
                db.add(r)
                db.flush()
            if b.register_type == "ENROLL" and s.student_status == "PENDING_REGISTER":
                res = change_student_status(db, s.id, "UNREGISTERED", change_type="REGISTER_TIMEOUT",
                                            reason="入学注册窗口已截止仍未注册", operator=uid, source_biz_id=r.id)
                changes.append((s.id, res["fromStatus"], res["toStatus"]))
            r.status = "UNREGISTERED"
            marked += 1
            cid = _counselor_of(db, s.id)
            if _push_todo(db, "AA_REGISTRATION", r.id, "AA_UNREGISTERED_HANDLE", cid, s.id,
                         f"{s.real_name} 逾期未完成{'入学' if b.register_type == 'ENROLL' else '学年'}注册"):
                notified += 1
        _audit(db, "AA_REG_BATCH", b.id, "SCAN_UNREGISTERED", f"marked={marked} skipped={skipped}")
        db.commit()
    for sid, frm, to in changes:
        audit_status_change(sid, frm, to, "REGISTER_TIMEOUT", uid)
    return {"batchId": str(batch_id), "marked": marked, "skipped": skipped, "notified": notified}


def export_unregistered_xlsx(user, batch_id=None, purpose="") -> bytes:
    """导出未注册学生名单 .xlsx（首行水印 + 审计）。"""
    purpose = (purpose or "").strip()
    if len(purpose) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")
    from app.services.xlsx_util import build_ledger_xlsx
    rows_data, _total = list_unregistered_students(user, batch_id, page=1, page_size=10000)
    _n, _r, _uid = _op()
    watermark = f"导出人：{_n or '-'}  时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  用途：{purpose}"
    headers = ["学号", "姓名", "批次", "类型", "截止时间", "状态"]
    rows = [[r["studentNo"], r["realName"], r["batchName"],
             ("入学注册" if r["registerType"] == "ENROLL" else "学年注册" if r["registerType"] else ""),
             r["windowEnd"] or "", ("未注册" if r["kind"] == "UNREGISTERED" else "逾期待处理")]
            for r in rows_data]
    content = build_ledger_xlsx("未注册学生名单", headers, rows, watermark=watermark)
    with session() as db:
        _audit(db, "AA_REGISTRATION", batch_id, "EXPORT_UNREGISTERED", f"用途={purpose[:100]}")
        db.commit()
    return content


# ═══════════ 教务首页（四角色视图占位聚合）═══════════

def dashboard(user) -> dict:
    from app.models import AaRegistration, AaTerm, StudentProfile
    with session() as db:
        cur = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == _tid(), AaTerm.is_current.is_(True),
            AaTerm.is_deleted.is_(False))).first()
        stu_total = db.scalar(select(func.count()).select_from(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))) or 0
        registered = db.scalar(select(func.count()).select_from(AaRegistration).where(
            AaRegistration.tenant_id == _tid(), AaRegistration.status == "REGISTERED",
            AaRegistration.is_deleted.is_(False))) or 0
        return {
            "currentTerm": (_term_row(cur) if cur else None),
            "summaryCards": [
                {"key": "studentTotal", "label": "学生数", "value": stu_total, "unit": "人"},
                {"key": "registered", "label": "已注册", "value": registered, "unit": "人"},
            ],
            "moduleCards": [
                {"key": "term", "label": "学年学期", "status": "LIVE"},
                {"key": "roster", "label": "学籍名册", "status": "LIVE"},
                {"key": "registration", "label": "入学注册", "status": "LIVE"},
                {"key": "statusChange", "label": "学籍异动", "status": "PENDING"},
                {"key": "program", "label": "培养方案", "status": "PENDING"},
                {"key": "course", "label": "课程库", "status": "PENDING"},
                {"key": "schedule", "label": "课表", "status": "PENDING"},
                {"key": "grade", "label": "成绩预警", "status": "PENDING"},
                {"key": "graduation", "label": "毕业预审", "status": "PENDING"},
            ],
        }


# ═══════════ 教务看板 · 提醒聚合（P4 六卡；零新表，只读实时聚合既有表，对齐 R9 教学质量看板同款模式）═══════════
#   成绩提交进度 / 考试安排提醒 / 学籍异动提醒 / 学业预警提醒 / 毕业资格预警 / 教务待办
#   不改写任何业务状态机；数据来源与既有列表接口一致（t_aa_grade_task/t_aa_exam_course/
#   t_aa_status_change/t_acad_warning/t_aa_graduation_audit_result）。

_GRADE_STATUS_LABEL = {"NOT_STARTED": "未开始", "INPUTTING": "录入中", "SUBMITTED": "学院审核中",
                       "ACADEMIC_REVIEW": "教务审核中", "RETURNED": "已退回", "PUBLISHED": "已发布",
                       "ARCHIVED": "已归档"}
_CHANGE_TYPE_LABEL = {"SUSPEND": "休学", "WITHDRAW": "退学", "RESUME": "复学", "RETAIN": "留级",
                      "TRANSFER_MAJOR": "转专业"}
_GRAD_WARNING_STATUSES = ("SYSTEM_ABNORMAL", "COLLEGE_REVIEW", "ACADEMIC_REVIEW", "DELAYED")


def _class_name(db, class_id):
    if not class_id:
        return ""
    from app.models import SchoolClass
    c = db.get(SchoolClass, int(class_id))
    return c.class_name if c else ""


def _grade_progress(db) -> dict:
    """成绩提交进度：按 t_aa_grade_task 状态计数 + 滞后任务（未开始/录入中/已退回）录入进度前 10 条。"""
    from app.models import AaGradeRecord, AaGradeTask, StudentProfile
    T = _tid()
    rows = db.scalars(select(AaGradeTask).where(
        AaGradeTask.tenant_id == T, AaGradeTask.is_deleted.is_(False))).all()
    counts = {}
    for t in rows:
        counts[t.status] = counts.get(t.status, 0) + 1
    total = len(rows)
    done = counts.get("SUBMITTED", 0) + counts.get("ACADEMIC_REVIEW", 0) + counts.get("PUBLISHED", 0)
    order = {"RETURNED": 0, "INPUTTING": 1, "NOT_STARTED": 2}
    lagging = sorted([t for t in rows if t.status in ("NOT_STARTED", "INPUTTING", "RETURNED")],
                     key=lambda t: order.get(t.status, 9))
    pending = []
    for t in lagging[:10]:
        entered = db.scalar(select(func.count()).select_from(AaGradeRecord).where(
            AaGradeRecord.tenant_id == T, AaGradeRecord.task_id == t.id,
            AaGradeRecord.is_deleted.is_(False))) or 0
        roster_total = 0
        if t.class_id:
            roster_total = db.scalar(select(func.count()).select_from(StudentProfile).where(
                StudentProfile.tenant_id == T, StudentProfile.class_id == t.class_id,
                StudentProfile.is_deleted.is_(False))) or 0
        pending.append({
            "gradeTaskId": str(t.id), "courseName": t.course_name or "",
            "className": _class_name(db, t.class_id), "teacherKey": t.teacher_key or "",
            "status": t.status, "statusLabel": _GRADE_STATUS_LABEL.get(t.status, t.status),
            "enteredCount": entered, "rosterCount": roster_total,
            "progressRate": round(entered / roster_total * 100, 1) if roster_total else 0.0})
    return {"totalTasks": total, "counts": counts,
            "submittedRate": round(done / total * 100, 1) if total else 0.0,
            "pendingTasks": pending, "drillRoute": "aa-grade-overview"}


def _exam_reminders(db, days_ahead=14) -> dict:
    """考试安排提醒：已确认批次(ARRANGED/PUBLISHED)内、未来 N 天已确认考试课程(CONFIRMED)。"""
    from app.models import AaExamBatch, AaExamCourse
    T = _tid()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    until = (datetime.utcnow() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    join = and_(AaExamBatch.id == AaExamCourse.batch_id, AaExamBatch.tenant_id == AaExamCourse.tenant_id)
    conds = [AaExamCourse.tenant_id == T, AaExamCourse.is_deleted.is_(False),
             AaExamCourse.status == "CONFIRMED", AaExamCourse.exam_date.isnot(None),
             AaExamCourse.exam_date >= today, AaExamCourse.exam_date <= until,
             AaExamBatch.status.in_(["ARRANGED", "PUBLISHED"])]
    total = db.scalar(select(func.count()).select_from(AaExamCourse)
                      .join(AaExamBatch, join).where(*conds)) or 0
    rows = db.execute(select(AaExamCourse, AaExamBatch).join(AaExamBatch, join).where(*conds)
                      .order_by(AaExamCourse.exam_date.asc(), AaExamCourse.start_time.asc()).limit(10)).all()
    items = [{"examCourseId": str(c.id), "courseName": c.course_name or "", "className": c.class_name or "",
              "examDate": c.exam_date or "", "startTime": c.start_time or "", "endTime": c.end_time or "",
              "teacherName": c.teacher_name or "", "batchStatus": b.status} for c, b in rows]
    return {"count": total, "windowDays": days_ahead, "items": items, "drillRoute": "aa-exam"}


def _status_change_reminders(db) -> dict:
    """学籍异动提醒：在途待审批（SUBMITTED/IN_REVIEW，不含注册类）。"""
    from app.models import AaStatusChange, StudentProfile
    T = _tid()
    conds = [AaStatusChange.tenant_id == T, AaStatusChange.is_deleted.is_(False),
             AaStatusChange.change_type != "ENROLL_REGISTER", AaStatusChange.change_type != "ANNUAL_REGISTER",
             AaStatusChange.status.in_(["SUBMITTED", "IN_REVIEW"])]
    join = and_(StudentProfile.id == AaStatusChange.student_id,
               StudentProfile.tenant_id == AaStatusChange.tenant_id)
    total = db.scalar(select(func.count()).select_from(AaStatusChange)
                      .outerjoin(StudentProfile, join).where(*conds)) or 0
    rows = db.execute(select(AaStatusChange, StudentProfile).outerjoin(StudentProfile, join).where(*conds)
                      .order_by(AaStatusChange.id.desc()).limit(10)).all()
    items = [{"changeId": str(x.id), "studentName": s.real_name if s else "",
              "changeType": x.change_type, "changeTypeLabel": _CHANGE_TYPE_LABEL.get(x.change_type, x.change_type),
              "status": x.status, "currentNode": x.current_node or "",
              "submittedAt": _iso(x.created_at) if getattr(x, "created_at", None) else ""}
             for x, s in rows]
    return {"count": total, "items": items, "drillRoute": "aa-status-changes"}


def _warning_reminders(db) -> dict:
    """学业预警提醒：在办（PENDING_HANDLE）学业预警，高等级优先。"""
    from app.models import AcademicStudent, AcademicWarning
    T = _tid()
    conds = [AcademicWarning.tenant_id == T, AcademicWarning.record_status == "ACTIVE",
             AcademicWarning.is_deleted.is_(False), AcademicWarning.status == "PENDING_HANDLE"]
    join = and_(AcademicStudent.id == AcademicWarning.acad_student_id,
               AcademicStudent.tenant_id == AcademicWarning.tenant_id)
    total = db.scalar(select(func.count()).select_from(AcademicWarning)
                      .outerjoin(AcademicStudent, join).where(*conds)) or 0
    rows = db.execute(select(AcademicWarning, AcademicStudent).outerjoin(AcademicStudent, join).where(*conds)
                      .order_by(AcademicWarning.id.desc()).limit(30)).all()
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    items = sorted([{"warningId": str(w.id), "studentName": a.name if a else "",
                     "level": w.level, "reason": w.reason or "", "status": w.status}
                    for w, a in rows], key=lambda x: order.get(x["level"], 9))[:10]
    return {"count": total, "items": items, "drillRoute": "aa-warnings"}


def _graduation_warnings(db) -> dict:
    """毕业资格预警：预审系统异常(SYSTEM_ABNORMAL)/待学院复核/待教务终审/延毕(DELAYED)。"""
    from app.models import AaGraduationAuditBatch, AaGraduationAuditResult, StudentProfile
    T = _tid()
    join_b = and_(AaGraduationAuditBatch.id == AaGraduationAuditResult.batch_id,
                 AaGraduationAuditBatch.tenant_id == AaGraduationAuditResult.tenant_id)
    join_s = and_(StudentProfile.id == AaGraduationAuditResult.student_id,
                 StudentProfile.tenant_id == AaGraduationAuditResult.tenant_id)
    conds = [AaGraduationAuditResult.tenant_id == T, AaGraduationAuditResult.is_deleted.is_(False),
             AaGraduationAuditResult.status.in_(_GRAD_WARNING_STATUSES)]
    total = db.scalar(select(func.count()).select_from(AaGraduationAuditResult)
                      .join(AaGraduationAuditBatch, join_b).where(*conds)) or 0
    rows = db.execute(select(AaGraduationAuditResult, AaGraduationAuditBatch, StudentProfile)
                      .join(AaGraduationAuditBatch, join_b).outerjoin(StudentProfile, join_s).where(*conds)
                      .order_by(AaGraduationAuditResult.id.desc()).limit(10)).all()
    items = [{"resultId": str(r.id), "studentName": s.real_name if s else "",
              "batchName": b.batch_name, "overall": r.overall or "", "conclusion": r.conclusion or "",
              "status": r.status} for r, b, s in rows]
    return {"count": total, "items": items, "drillRoute": "aa-graduation"}


def _todos(grade_counts, sc_count, warn_count, grad_count) -> list:
    """教务待办：跨模块待处理事项计数聚合（点击直达对应处理页）。"""
    review_pending = grade_counts.get("SUBMITTED", 0) + grade_counts.get("ACADEMIC_REVIEW", 0)
    lagging = (grade_counts.get("NOT_STARTED", 0) + grade_counts.get("INPUTTING", 0)
              + grade_counts.get("RETURNED", 0))
    return [
        {"key": "gradeReview", "label": "成绩待审核（学院/教务）", "count": review_pending,
         "drillRoute": "aa-grade-college-review"},
        {"key": "gradeLagging", "label": "成绩未提交（未开始/录入中/已退回）", "count": lagging,
         "drillRoute": "aa-grade-overview"},
        {"key": "statusChangeReview", "label": "学籍异动待审批", "count": sc_count,
         "drillRoute": "aa-status-changes"},
        {"key": "warningHandle", "label": "学业预警待处置", "count": warn_count, "drillRoute": "aa-warnings"},
        {"key": "graduationReview", "label": "毕业资格待复核/异常", "count": grad_count,
         "drillRoute": "aa-graduation"},
    ]


def dashboard_reminders(user) -> dict:
    """教务看板提醒聚合（成绩提交进度/考试安排提醒/学籍异动提醒/学业预警提醒/毕业资格预警/教务待办）。
    零新表：全部实时只读聚合既有业务表，不复制、不改写任何状态机（对齐 R9 教学质量看板同款只读聚合模式）。"""
    from app.core.affairs_security import build_affairs_context
    with session() as db:
        build_affairs_context(user, db)  # 建立安全上下文（本期为全校聚合口径，与教学质量看板一致）
        gp = _grade_progress(db)
        ex = _exam_reminders(db)
        sc = _status_change_reminders(db)
        wr = _warning_reminders(db)
        gr = _graduation_warnings(db)
        todos = _todos(gp["counts"], sc["count"], wr["count"], gr["count"])
        return {"gradeProgress": gp, "examReminders": ex, "statusChangeReminders": sc,
                "warningReminders": wr, "graduationWarnings": gr, "todos": todos,
                "generatedAt": datetime.utcnow().isoformat()}
