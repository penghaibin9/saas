"""Round7 教务四端能力补齐：学生注册自助 / 挂科可选重修 / 考勤自查 / 校历 / 清考可见 / 打印。

由 mobile.py / portal academic_service 直接调用；复用既有 registration/makeup/attendance/calendar/exam 服务。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.modules.academic_affairs.services.mobile_academic_affairs_service import _me, _ns
from app.services.db_service import _iso, _tid, session


_REG_TYPE_LABEL = {"ENROLL": "入学注册", "ANNUAL": "学年注册", "SEMESTER": "学期注册"}


# ═══════════ 学生注册自助 ═══════════

def registration_my(user) -> dict:
    """开放中的注册批次 + 本人注册/资格/暂缓状态。"""
    from app.models import (AaRegistration, AaRegistrationBatch, AaRegistrationDeferral,
                            AaRegistrationException)
    with session() as db:
        stu = _me(db, user)
        batches = db.scalars(select(AaRegistrationBatch).where(
            AaRegistrationBatch.tenant_id == _tid(), AaRegistrationBatch.is_deleted.is_(False),
            AaRegistrationBatch.status == "OPEN").order_by(AaRegistrationBatch.id.desc())).all()
        items = []
        for b in batches:
            reg = db.scalars(select(AaRegistration).where(
                AaRegistration.tenant_id == _tid(), AaRegistration.batch_id == b.id,
                AaRegistration.student_id == stu.id, AaRegistration.is_deleted.is_(False))).first()
            defer = db.scalars(select(AaRegistrationDeferral).where(
                AaRegistrationDeferral.tenant_id == _tid(), AaRegistrationDeferral.batch_id == b.id,
                AaRegistrationDeferral.student_id == stu.id,
                AaRegistrationDeferral.is_deleted.is_(False)).order_by(
                AaRegistrationDeferral.id.desc())).first()
            open_exc = db.scalars(select(AaRegistrationException).where(
                AaRegistrationException.tenant_id == _tid(), AaRegistrationException.batch_id == b.id,
                AaRegistrationException.student_id == stu.id,
                AaRegistrationException.status == "OPEN",
                AaRegistrationException.is_deleted.is_(False))).first()
            elig = (reg.eligibility_status if reg else "PENDING") or "PENDING"
            reg_status = (reg.status if reg else "PENDING_REGISTER")
            already = reg_status == "REGISTERED"
            blocked = elig == "INELIGIBLE" or bool(open_exc)
            items.append({
                "batchId": str(b.id), "batchName": b.batch_name,
                "registerType": b.register_type,
                "registerTypeLabel": _REG_TYPE_LABEL.get(b.register_type, b.register_type),
                "windowStart": _iso(b.window_start), "windowEnd": _iso(b.window_end),
                "registrationStatus": reg_status,
                "eligibilityStatus": elig,
                "eligibilityNote": (reg.eligibility_note if reg else "") or "",
                "hasOpenException": bool(open_exc),
                "exceptionType": (open_exc.exception_type if open_exc else None),
                "deferral": ({
                    "deferralId": str(defer.id), "status": defer.status, "reason": defer.reason,
                    "requestedUntil": _iso(defer.requested_until), "reviewNote": defer.review_note or "",
                } if defer else None),
                "canRegister": (not already) and (not blocked),
                "canDefer": (not already) and (not defer or defer.status == "REJECTED"),
                "blockReason": (
                    "注册资格核验未通过" if elig == "INELIGIBLE"
                    else ("存在未解除的注册异常，请联系辅导员" if open_exc else "")
                ),
            })
        return {
            "studentStatus": stu.student_status,
            "studentNo": stu.student_no,
            "realName": stu.real_name,
            "batches": items,
            "note": "" if items else "当前无开放的注册批次",
        }


def registration_self_register(user, batch_id) -> dict:
    """本人在开放批次完成注册（强制本人 studentId；INELIGIBLE/未解除异常硬拦）。"""
    from app.models import AaRegistration, AaRegistrationException
    from app.modules.academic_affairs.services import academic_affairs_service as svc
    with session() as db:
        stu = _me(db, user)
        sid = stu.id
        reg = db.scalars(select(AaRegistration).where(
            AaRegistration.tenant_id == _tid(), AaRegistration.batch_id == int(batch_id),
            AaRegistration.student_id == sid, AaRegistration.is_deleted.is_(False))).first()
        if reg and (reg.eligibility_status or "") == "INELIGIBLE":
            raise AppException("DATA_CONFLICT", "注册资格核验未通过，请联系辅导员或教务处")
        open_exc = db.scalars(select(AaRegistrationException).where(
            AaRegistrationException.tenant_id == _tid(),
            AaRegistrationException.batch_id == int(batch_id),
            AaRegistrationException.student_id == sid,
            AaRegistrationException.status == "OPEN",
            AaRegistrationException.is_deleted.is_(False))).first()
        if open_exc:
            raise AppException("DATA_CONFLICT", "存在未解除的注册异常，请先联系辅导员处理")
    return svc.register_student(batch_id, user, sid)


def registration_defer_apply_my(user, batch_id, reason, requested_until=None) -> dict:
    """本人申请暂缓注册（不走教职工数据范围校验，仅本人）。"""
    from app.models import AaRegistrationBatch, AaRegistrationDeferral
    from app.modules.academic_affairs.services.academic_affairs_service import _audit, _deferral_row, _parse_dt
    reason = (reason or "").strip()
    if len(reason) < 2:
        raise AppException("VALIDATION_ERROR", "暂缓原因必填")
    with session() as db:
        stu = _me(db, user)
        b = db.get(AaRegistrationBatch, int(batch_id))
        if not b or b.is_deleted or b.tenant_id != _tid():
            raise not_found("注册批次不存在")
        if b.status != "OPEN":
            raise AppException("DATA_CONFLICT", "注册批次未开放或已关闭")
        if stu.student_status not in ("PENDING_REGISTER", "UNREGISTERED", "REGISTERED"):
            # ANNUAL 场景下在籍生也可申请暂缓本批次义务
            raise AppException("DATA_CONFLICT", "当前学籍状态不可申请暂缓注册", http_status=409)
        dup = db.scalars(select(AaRegistrationDeferral).where(
            AaRegistrationDeferral.tenant_id == _tid(), AaRegistrationDeferral.batch_id == b.id,
            AaRegistrationDeferral.student_id == stu.id, AaRegistrationDeferral.status == "PENDING",
            AaRegistrationDeferral.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "本批次已有待审的暂缓申请", http_status=409)
        d = AaRegistrationDeferral(
            tenant_id=_tid(), batch_id=b.id, student_id=stu.id, reason=reason,
            requested_until=_parse_dt(requested_until), status="PENDING")
        db.add(d)
        db.flush()
        _audit(db, "AA_REG_DEFERRAL", d.id, "SELF_APPLY", reason)
        db.commit()
        db.refresh(d)
        return _deferral_row(d)


# ═══════════ 重修/免修可选课程 ═══════════

def _best_grades_for_me(db, stu):
    from app.models import AcademicGrade, AcademicStudent
    acad = db.scalars(select(AcademicStudent).where(
        AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == stu.id,
        AcademicStudent.is_deleted.is_(False))).first()
    if not acad:
        return [], None
    rows = db.scalars(select(AcademicGrade).where(
        AcademicGrade.tenant_id == _tid(), AcademicGrade.acad_student_id == acad.id,
        AcademicGrade.record_status == "ACTIVE", AcademicGrade.is_deleted.is_(False))).all()
    by_course = {}
    for g in rows:
        key = (g.course_name or "").strip()
        if not key:
            continue
        prev = by_course.get(key)
        if prev is None or (g.score or -1) > (prev.score or -1) or (
                (g.score or -1) == (prev.score or -1) and (g.id or 0) > (prev.id or 0)):
            by_course[key] = g
    return list(by_course.values()), acad


def makeup_options_my(user) -> dict:
    """重修候选=挂科；免修候选=尚未及格的课程（禁止纯手输为主入口）。"""
    with session() as db:
        stu = _me(db, user)
        best, _ = _best_grades_for_me(db, stu)
        fails, pending = [], []
        for g in best:
            item = {
                "gradeId": str(g.id),
                "courseName": g.course_name,
                "termCode": g.term or "",
                "score": g.score,
                "credit": float(g.credit_value or 0),
                "passStatus": g.pass_status,
            }
            ps = (g.pass_status or "").upper()
            if ps in ("FAIL", "FAILED"):
                fails.append(item)
            elif ps != "PASSED":
                pending.append(item)
        fails.sort(key=lambda x: (x["termCode"] or "", x["courseName"]))
        pending.sort(key=lambda x: (x["termCode"] or "", x["courseName"]))
        return {
            "retakeOptions": fails,
            "exemptionOptions": pending or fails,
            "retakeTotal": len(fails),
            "exemptionTotal": len(pending or fails),
            "note": "请从列表选择课程提交；手输仅作应急兜底且需与挂科/未及格记录一致。"
            if (fails or pending) else "暂无挂科/未及格课程可选",
        }


# ═══════════ 学生考勤自查 ═══════════

def attendance_my(user) -> dict:
    """本人已提交场次中的考勤明细汇总。点名入口在教师小程序，PC 仅统计。"""
    from app.models import AaAttendanceSession
    with session() as db:
        stu = _me(db, user)
        sid = str(stu.id)
        if not stu.class_id:
            return {"items": [], "summary": {"PRESENT": 0, "LATE": 0, "ABSENT": 0, "LEAVE": 0, "OTHER": 0},
                    "total": 0, "note": "未分配行政班，暂无课堂考勤"}
        rows = db.scalars(select(AaAttendanceSession).where(
            AaAttendanceSession.tenant_id == _tid(),
            AaAttendanceSession.is_deleted.is_(False),
            AaAttendanceSession.status == "SUBMITTED",
            AaAttendanceSession.class_id == int(stu.class_id),
        ).order_by(AaAttendanceSession.session_date.desc(), AaAttendanceSession.id.desc())).all()
        items = []
        summary = {"PRESENT": 0, "LATE": 0, "ABSENT": 0, "LEAVE": 0, "OTHER": 0}
        for t in rows:
            try:
                roster = json.loads(t.roster_json or "[]")
            except json.JSONDecodeError:
                roster = []
            mine = next((x for x in roster if str(x.get("studentId")) == sid), None)
            if not mine:
                continue
            st = (mine.get("status") or "PRESENT").upper()
            if st in summary:
                summary[st] += 1
            else:
                summary["OTHER"] += 1
            items.append({
                "sessionId": str(t.id), "courseName": t.course_name or "",
                "sessionDate": t.session_date, "slotNo": t.slot_no,
                "sessionType": t.session_type or "常规", "status": st,
            })
        return {
            "items": items, "summary": summary, "total": len(items),
            "policy": "ROLLCALL_ON_MINIAPP_ONLY",
            "note": "仅展示已提交场次；教师在小程序点名，PC 端只做统计查询，不提供补点名入口。"
            if items else "暂无已提交的课堂考勤记录",
        }


# ═══════════ 学生校历只读 ═══════════

def calendar_my(user) -> dict:
    from app.models import AaTerm
    from app.modules.academic_affairs.services import academic_affairs_service as svc
    with session() as db:
        _me(db, user)
        term = db.scalars(select(AaTerm).where(
            AaTerm.tenant_id == _tid(), AaTerm.is_current.is_(True),
            AaTerm.is_deleted.is_(False))).first()
        if not term:
            return {"hasTerm": False, "events": [], "weeks": [], "note": "尚未设置当前学期"}
        tid = term.id
        year_code = term.year_code
        term_no = term.term_no
    events = svc.list_calendar(tid, user)
    try:
        weeks_payload = svc.week_calendar(tid, user)
    except AppException as e:
        weeks_payload = {"weeks": [], "note": str(getattr(e, "message", None) or e)}
    weeks = weeks_payload.get("weeks") if isinstance(weeks_payload, dict) else []
    return {
        "hasTerm": True,
        "termId": str(tid),
        "termLabel": f"{year_code or ''}-{term_no or ''}",
        "events": events,
        "weeks": weeks or [],
        "weekMeta": {k: weeks_payload.get(k) for k in ("teachingWeeks", "examWeekStart", "startDate")
                     if isinstance(weeks_payload, dict) and k in weeks_payload},
        "note": weeks_payload.get("note") if isinstance(weeks_payload, dict) else "",
    }


# ═══════════ 清考结果学生可见 ═══════════

def clearance_my(user) -> dict:
    """本人被圈定的毕业清考记录（只读）。"""
    from app.models import AaMakeupBatch, AcademicMakeup, AcademicStudent
    with session() as db:
        stu = _me(db, user)
        acad = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == _tid(), AcademicStudent.student_id == stu.id,
            AcademicStudent.is_deleted.is_(False))).first()
        if not acad:
            return {"items": [], "total": 0, "note": "暂无学业台账，无清考记录"}
        rows = db.scalars(select(AcademicMakeup).where(
            AcademicMakeup.tenant_id == _tid(), AcademicMakeup.acad_student_id == acad.id,
            AcademicMakeup.kind == "CLEARANCE", AcademicMakeup.is_deleted.is_(False),
        ).order_by(AcademicMakeup.id.desc())).all()
        batch_ids = {r.batch_id for r in rows if r.batch_id}
        batches = {}
        if batch_ids:
            batches = {b.id: b for b in db.scalars(select(AaMakeupBatch).where(
                AaMakeupBatch.id.in_(list(batch_ids)))).all()}
        items = []
        for r in rows:
            b = batches.get(r.batch_id)
            items.append({
                "recordId": str(r.id), "batchId": str(r.batch_id or ""),
                "batchName": b.batch_name if b else "",
                "courseName": r.course_name, "termCode": r.term or "",
                "originScore": r.origin_score, "score": r.final_score,
                "status": r.status, "kind": "CLEARANCE",
            })
        return {
            "items": items, "total": len(items),
            "note": "清考由教务处按应届未通过课程圈定；此处仅查看结果，不可自助报名。"
            if items else "暂无清考安排",
        }


# ═══════════ 准考证 / 异动申请表打印留痕 ═══════════

def exam_ticket_print_my(user, body=None) -> dict:
    from app.student_portal.services import common_service as common
    from app.modules.academic_affairs.services.mobile_academic_affairs_service import exam_my
    body = body or {}
    doc = exam_my(user)
    with session() as db:
        stu = _me(db, user)
        sno, name = stu.student_no, stu.real_name
    log = common.print_log(user, {
        "bizType": "EXAM_TICKET",
        "bizId": str(body.get("bizId") or sno or "self"),
        "docName": "准考证",
        "reason": str(body.get("reason") or "个人准考证"),
    })
    return {
        **log, "docName": "准考证", "printReason": body.get("reason") or "个人准考证",
        "document": {**doc, "studentNo": sno, "realName": name},
    }


def status_change_print_my(user, body=None) -> dict:
    from app.student_portal.services import common_service as common
    from app.modules.academic_affairs.services.mobile_academic_affairs_service import status_my
    body = body or {}
    st = status_my(user)
    with session() as db:
        stu = _me(db, user)
        sno, name = stu.student_no, stu.real_name
    log = common.print_log(user, {
        "bizType": "STATUS_CHANGE",
        "bizId": str(body.get("bizId") or body.get("changeType") or "self"),
        "docName": "学籍异动申请审批表",
        "reason": str(body.get("reason") or body.get("changeType") or "学籍异动"),
    })
    return {
        **log,
        "docName": "学籍异动申请审批表",
        "printReason": body.get("reason") or "",
        "document": {
            "studentNo": sno, "realName": name,
            "studentStatus": st.get("studentStatus"),
            "enrolled": st.get("enrolled"),
            "changeType": body.get("changeType"),
            "reason": body.get("reason"),
            "history": (st.get("changes") or [])[:5],
        },
    }
