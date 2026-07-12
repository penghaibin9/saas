"""13B-P1 教务中心：学年学期/校历/节次 + 学籍名册 + 入学/学年注册。

注册结果经 change_student_status() 单一入口写主档（PENDING_REGISTER→REGISTERED）。
学籍名册只读 t_student_profile（脱敏），不建 roster 表。注册预检只读 t_orientation_student，不复制迎新数据。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import and_, func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
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
        t = db.get(AaTerm, int(term_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("学期不存在")
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


# ═══════════ 校历 / 节次 ═══════════

def add_calendar_event(term_id, user, body) -> dict:
    with session() as db:
        from app.models import AaCalendarEvent, AaTerm
        t = db.get(AaTerm, int(term_id))
        if not t or t.is_deleted or t.tenant_id != _tid():
            raise not_found("学期不存在")
        e = AaCalendarEvent(tenant_id=_tid(), term_id=t.id, event_type=(body.eventType or "TEACHING"),
                            start_date=_parse_dt(body.startDate), end_date=_parse_dt(body.endDate),
                            swap_to_date=_parse_dt(getattr(body, "swapToDate", None)),
                            remark=getattr(body, "remark", None))
        db.add(e)
        db.flush()
        _audit(db, "AA_CALENDAR", e.id, "ADD", body.eventType or "TEACHING")
        db.commit()
        return {"eventId": str(e.id), "termId": str(term_id), "eventType": e.event_type}


def list_calendar(term_id, user):
    from app.models import AaCalendarEvent
    with session() as db:
        rows = db.scalars(select(AaCalendarEvent).where(
            AaCalendarEvent.tenant_id == _tid(), AaCalendarEvent.term_id == int(term_id),
            AaCalendarEvent.is_deleted.is_(False)).order_by(AaCalendarEvent.start_date)).all()
        return [{"eventId": str(e.id), "eventType": e.event_type, "startDate": _iso(e.start_date),
                 "endDate": _iso(e.end_date), "swapToDate": _iso(e.swap_to_date),
                 "remark": e.remark or ""} for e in rows]


def create_time_slot(body, user) -> dict:
    with session() as db:
        from app.models import AaTimeSlot
        sl = AaTimeSlot(tenant_id=_tid(), slot_no=int(body.slotNo), slot_name=getattr(body, "slotName", None),
                        start_time=getattr(body, "startTime", None), end_time=getattr(body, "endTime", None),
                        status="ENABLED")
        db.add(sl)
        db.flush()
        _audit(db, "AA_TIMESLOT", sl.id, "CREATE", f"第{body.slotNo}节")
        db.commit()
        return {"slotId": str(sl.id), "slotNo": sl.slot_no}


def list_time_slots(user):
    from app.models import AaTimeSlot
    with session() as db:
        rows = db.scalars(select(AaTimeSlot).where(
            AaTimeSlot.tenant_id == _tid(), AaTimeSlot.is_deleted.is_(False),
            AaTimeSlot.status == "ENABLED").order_by(AaTimeSlot.slot_no)).all()
        return [{"slotId": str(x.id), "slotNo": x.slot_no, "slotName": x.slot_name or "",
                 "startTime": x.start_time or "", "endTime": x.end_time or ""} for x in rows]


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


# ═══════════ 入学/学年注册 ═══════════

def create_registration_batch(body, user) -> dict:
    with session() as db:
        from app.models import AaRegistrationBatch
        rtype = (body.registerType or "ENROLL")
        if rtype not in ("ENROLL", "ANNUAL"):
            raise AppException("VALIDATION_ERROR", "注册类型非法")
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


def list_registration_batches(user, status=None, page=1, page_size=20):
    from app.models import AaRegistrationBatch
    with session() as db:
        conds = [AaRegistrationBatch.tenant_id == _tid(), AaRegistrationBatch.is_deleted.is_(False)]
        if status:
            conds.append(AaRegistrationBatch.status == status)
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
        b = db.get(AaRegistrationBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("注册批次不存在")
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
