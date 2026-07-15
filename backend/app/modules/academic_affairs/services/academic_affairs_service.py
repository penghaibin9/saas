"""13B-P1 教务中心：学年学期/校历/节次 + 学籍名册 + 入学/学年注册。

注册结果经 change_student_status() 单一入口写主档（PENDING_REGISTER→REGISTERED）。
学籍名册只读 t_student_profile（脱敏），不建 roster 表。注册预检只读 t_orientation_student，不复制迎新数据。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import and_, func, or_, select

from app.core.affairs_security import build_affairs_context, no_data_scope
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
