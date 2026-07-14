"""13A-P5 谈心谈话 + 家校联系（集中兑现进360）。

谈话：建计划(批量生成 record)→填记录(→COMPLETED,进360)→跟进/办结/转风险/转家校；
心理(PSYCHOLOGY)类内容仅授权角色可见全文。家校：联系记录 append-only,查看完整号码必填原因+审计。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, audit_insert, session

TALK_TOPICS = ("DAILY", "ACADEMIC", "PSYCHOLOGY", "DISCIPLINE", "EMPLOYMENT",
               "INTERNSHIP", "AID", "DORM")
_PSY_ROLES = {"SCHOOL_ADMIN", "STUDENT_AFFAIRS_ADMIN", "PSYCHOLOGY_TEACHER", "ADMIN"}

L_TALK = {"PLANNED": "待谈", "SCHEDULED": "已约定", "COMPLETED": "已谈话",
          "FOLLOW_UP": "跟进中", "CLOSED": "已办结", "CANCELLED": "已取消"}


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


def _can_view_psy(user) -> bool:
    return (user or {}).get("currentRoleCode") in _PSY_ROLES


def _scope_or_403(db, student_id, user, what="该记录"):
    from app.models import StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    allowed, _ = _allowed_class_ids(db, user)
    if allowed is None:
        return
    s = db.get(StudentProfile, int(student_id)) if student_id else None
    if not s or s.class_id not in allowed:
        raise AppException("NO_DATA_SCOPE", f"{what}不在您的数据范围内")


# ═══════════ 谈话 ═══════════

def _talk_row(x, user, s=None) -> dict:
    psy_masked = (x.topic_type == "PSYCHOLOGY" and not _can_view_psy(user))
    return {
        "talkId": str(x.id), "planId": str(x.plan_id or ""), "studentId": str(x.student_id),
        "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
        "talkType": x.topic_type, "topic": x.topic or "", "talkAt": _iso(x.talk_at),
        "content": "[心理谈话·明细受限]" if psy_masked else (x.content or ""),
        "psyMasked": psy_masked, "result": x.result or "", "needFollow": bool(x.need_follow),
        "relatedRiskId": str(x.related_risk_id or ""), "relatedContactId": str(x.related_contact_id or ""),
        "status": x.status, "statusLabel": L_TALK.get(x.status, x.status), "version": x.version,
    }


def _load_talk(db, talk_id):
    from app.models import StudentProfile, TalkRecord
    x = db.get(TalkRecord, int(talk_id))
    if not x or x.is_deleted or x.tenant_id != _tid():
        raise not_found("谈话记录不存在")
    s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
    return x, s


def create_talk(body, user) -> dict:
    """建谈话计划：批量圈定学生 → 每生一条 talk_record（PLANNED/SCHEDULED）。"""
    if (body.talkType or "") not in TALK_TOPICS:
        raise AppException("VALIDATION_ERROR", "谈话类型非法")
    sids = [int(s) for s in (body.studentIds or []) if str(s).strip()]
    if not sids:
        raise AppException("VALIDATION_ERROR", "至少选择一名学生")
    scheduled = _parse_dt(getattr(body, "scheduledAt", None))
    with session() as db:
        from app.models import StudentProfile, TalkPlan, TalkRecord
        _n, _r, uid = _op()
        teacher_id = int(uid) if uid.isdigit() else None
        plan = TalkPlan(tenant_id=_tid(), plan_name=body.topic, teacher_id=teacher_id,
                        topic_type=body.talkType, planned_at=scheduled,
                        student_ids_json=json.dumps(sids), status="SCHEDULED" if scheduled else "DRAFT")
        db.add(plan)
        db.flush()
        talk_ids = []
        for sid in sids:
            s = db.get(StudentProfile, sid)
            if not s or s.is_deleted or s.tenant_id != _tid():
                raise not_found(f"学生 {sid} 不存在")
            _scope_or_403(db, sid, user, "学生")
            rec = TalkRecord(tenant_id=_tid(), plan_id=plan.id, student_id=sid, teacher_id=teacher_id,
                             topic_type=body.talkType, topic=body.topic, talk_at=scheduled,
                             status="SCHEDULED" if scheduled else "PLANNED")
            db.add(rec)
            db.flush()
            talk_ids.append(str(rec.id))
        _audit(db, "TALK", plan.id, "PLAN_CREATE", f"{len(sids)}生")
        db.commit()
        return {"planId": str(plan.id), "talkIds": talk_ids}


def record_talk(talk_id, user, content, result="", need_follow=False) -> dict:
    if not content or len(content.strip()) < 20:
        raise AppException("VALIDATION_ERROR", "谈话内容必填且不少于 20 字")
    with session() as db:
        from app.models import StudentStageEvent
        x, s = _load_talk(db, talk_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in ("PLANNED", "SCHEDULED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该谈话已记录，不可重复填写")
        x.content, x.result, x.need_follow = content.strip(), result, bool(need_follow)
        x.talk_at = x.talk_at or datetime.utcnow()
        x.status, x.version = ("FOLLOW_UP" if need_follow else "COMPLETED"), x.version + 1
        # 进 360（学生端仅见"已谈话"摘要，内容分级）
        db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(x.student_id), from_stage=None,
                                 to_stage="TALK_COMPLETED", reason=f"谈心谈话（{x.topic_type}）",
                                 source_module="student-affairs"))
        _audit(db, "TALK", x.id, "RECORD", x.topic_type)
        db.commit()
        db.refresh(x)
        return _talk_row(x, user, s)


def follow_up(talk_id, user, action, content="") -> dict:
    """跟进/办结/转风险/转家校。"""
    action = (action or "").upper()
    with session() as db:
        from app.models import AffairsRiskRecord, FamilyContactLog, StudentStageEvent
        x, s = _load_talk(db, talk_id)
        _scope_or_403(db, x.student_id, user)
        if x.status not in ("COMPLETED", "FOLLOW_UP"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅已完成/跟进中的谈话可操作")
        if action == "FOLLOW":
            x.status, x.version = "FOLLOW_UP", x.version + 1
            _audit(db, "TALK", x.id, "FOLLOW", content or "")
        elif action == "CLOSE":
            x.status, x.version = "CLOSED", x.version + 1
            db.add(StudentStageEvent(tenant_id=_tid(), student_id=int(x.student_id), from_stage=None,
                                     to_stage="TALK_CLOSED", reason="谈话办结", source_module="student-affairs"))
            _audit(db, "TALK", x.id, "CLOSE")
        elif action == "TO_RISK":
            src = "MENTAL" if x.topic_type == "PSYCHOLOGY" else "MANUAL"
            risk = AffairsRiskRecord(tenant_id=_tid(), student_id=x.student_id, source=src,
                                     source_ref_id=x.id, risk_level="MEDIUM",
                                     title=f"谈话转风险：{x.topic or ''}", detail=content or x.content,
                                     status="NEW")
            db.add(risk)
            db.flush()
            x.related_risk_id, x.version = risk.id, x.version + 1
            _audit(db, "TALK", x.id, "TO_RISK", str(risk.id))
        elif action == "TO_HOME_SCHOOL":
            log = FamilyContactLog(tenant_id=_tid(), student_id=x.student_id, contact_type="PHONE",
                                   contact_reason=f"谈话转家校：{x.topic or ''}", contact_result=content,
                                   related_risk_id=x.related_risk_id, occurred_at=datetime.utcnow())
            db.add(log)
            db.flush()
            x.related_contact_id, x.version = log.id, x.version + 1
            _audit(db, "TALK", x.id, "TO_HOME_SCHOOL", str(log.id))
        else:
            raise AppException("VALIDATION_ERROR", "无效操作")
        db.commit()
        db.refresh(x)
        return _talk_row(x, user, s)


def get_talk(talk_id, user) -> dict:
    with session() as db:
        x, s = _load_talk(db, talk_id)
        _scope_or_403(db, x.student_id, user)
        return _talk_row(x, user, s)


def list_talks(user, talk_type=None, status=None, student_id=None, page=1, page_size=20):
    from app.models import StudentProfile, TalkRecord
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        conds = [TalkRecord.tenant_id == _tid(), TalkRecord.is_deleted.is_(False)]
        if talk_type:
            conds.append(TalkRecord.topic_type == talk_type)
        if status:
            conds.append(TalkRecord.status == status)
        if student_id:
            conds.append(TalkRecord.student_id == int(student_id))
        rows = db.scalars(select(TalkRecord).where(*conds).order_by(TalkRecord.id.desc())).all()
        out = []
        for x in rows:
            s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            out.append(_talk_row(x, user, s))
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def talk_stats(user, group_by="TYPE"):
    """谈话工作量统计（完成率）；数据范围与 list_talks 一致（辅导员限本班，绝不回退全租户）。"""
    from app.models import StudentProfile, TalkRecord
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        all_rows = db.scalars(select(TalkRecord).where(
            TalkRecord.tenant_id == _tid(), TalkRecord.is_deleted.is_(False))).all()
        rows = []
        for x in all_rows:
            s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            rows.append(x)
        total = len(rows)
        completed = sum(1 for x in rows if x.status in ("COMPLETED", "FOLLOW_UP", "CLOSED"))
        breakdown = {}
        key = {"TYPE": "topic_type", "COUNSELOR": "teacher_id"}.get(group_by, "topic_type")
        for x in rows:
            k = str(getattr(x, key) or "")
            breakdown.setdefault(k, {"total": 0, "completed": 0})
            breakdown[k]["total"] += 1
            if x.status in ("COMPLETED", "FOLLOW_UP", "CLOSED"):
                breakdown[k]["completed"] += 1
        return {"total": total, "completed": completed,
                "completionRate": round(completed / total, 3) if total else 0.0,
                "breakdown": [{"key": k, **v} for k, v in breakdown.items()]}


# ═══════════ 家校联系 ═══════════

def create_contact(student_id, user, body) -> dict:
    """家校联系记录（append-only）。查看完整号码 → 原因必填 + SENSITIVE_VIEW 审计。"""
    with session() as db:
        from app.models import FamilyContactLog, StudentProfile
        s = db.get(StudentProfile, int(student_id))
        if not s or s.is_deleted or s.tenant_id != _tid():
            raise not_found("学生不存在或不在数据范围内")
        _scope_or_403(db, s.id, user)
        full_view = bool(getattr(body, "fullPhoneView", False))
        view_reason = (getattr(body, "viewReason", "") or "").strip()
        if full_view and len(view_reason) < 5:
            raise AppException("VALIDATION_ERROR", "查看完整号码必须填写原因（≥5字）")
        _n, _r, uid = _op()
        log = FamilyContactLog(tenant_id=_tid(), student_id=s.id,
                               teacher_id=int(uid) if uid.isdigit() else None,
                               contact_type=(body.contactType or "PHONE"),
                               contact_reason=getattr(body, "reason", None),
                               contact_result=getattr(body, "result", None),
                               full_phone_viewed=full_view, view_reason=view_reason or None,
                               occurred_at=datetime.utcnow())
        db.add(log)
        db.flush()
        cid = log.id
        _audit(db, "FAMILY", cid, "CONTACT", body.contactType or "PHONE")
        db.commit()
    if full_view:
        audit_insert("SENSITIVE_VIEW", "family_full_phone",
                     {"studentId": str(student_id), "reason": view_reason}, "SUCCESS")
    return {"contactId": str(cid), "studentId": str(student_id), "fullPhoneViewed": full_view}


def list_contacts(student_id, user, page=1, page_size=20):
    from app.models import FamilyContactLog
    with session() as db:
        _scope_or_403(db, student_id, user)
        rows = db.scalars(select(FamilyContactLog).where(
            FamilyContactLog.tenant_id == _tid(), FamilyContactLog.student_id == int(student_id))
            .order_by(FamilyContactLog.id.desc())).all()
        out = [{"contactId": str(x.id), "contactType": x.contact_type,
                "reason": x.contact_reason or "", "result": x.contact_result or "",
                "fullPhoneViewed": bool(x.full_phone_viewed), "occurredAt": _iso(x.occurred_at)}
               for x in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


# ═══════════ 家校回执（C 包·联系/回执）═══════════

_L_RECEIPT = {"PENDING": "待回执", "RECEIVED": "已回执"}


def _fc_row(x, s=None) -> dict:
    return {"contactId": str(x.id), "studentId": str(x.student_id),
            "studentNo": s.student_no if s else "", "realName": s.real_name if s else "",
            "contactType": x.contact_type, "reason": x.contact_reason or "",
            "result": x.contact_result or "", "occurredAt": _iso(x.occurred_at),
            "receiptStatus": getattr(x, "receipt_status", "PENDING") or "PENDING",
            "receiptStatusLabel": _L_RECEIPT.get(getattr(x, "receipt_status", "PENDING"), "待回执"),
            "receiptAt": _iso(getattr(x, "receipt_at", None)),
            "receiptNote": getattr(x, "receipt_note", None) or ""}


def list_all_contacts(user, receipt_status=None, page=1, page_size=50):
    """全局家校联系记录（数据范围过滤，不含号码本体）。"""
    from app.models import FamilyContactLog, StudentProfile
    from app.services.affairs_dashboard_service import _allowed_class_ids
    with session() as db:
        allowed, _ = _allowed_class_ids(db, user)
        conds = [FamilyContactLog.tenant_id == _tid()]
        if receipt_status:
            conds.append(FamilyContactLog.receipt_status == receipt_status)
        rows = db.scalars(select(FamilyContactLog).where(*conds).order_by(
            FamilyContactLog.id.desc())).all()
        out = []
        for x in rows:
            s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
            if allowed is not None and (not s or s.class_id not in allowed):
                continue
            out.append(_fc_row(x, s))
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def mark_receipt(contact_id, user, note="") -> dict:
    """登记家长回执（PENDING→RECEIVED，记回执内容）。"""
    from app.models import FamilyContactLog, StudentProfile
    with session() as db:
        x = db.get(FamilyContactLog, int(contact_id))
        if not x or x.tenant_id != _tid():
            raise not_found("家校联系记录不存在")
        _scope_or_403(db, x.student_id, user)
        if getattr(x, "receipt_status", "PENDING") == "RECEIVED":
            raise AppException("DATA_CONFLICT", "已登记回执")
        x.receipt_status, x.receipt_at = "RECEIVED", datetime.utcnow()
        x.receipt_note = (note or "").strip() or None
        db.commit(); db.refresh(x)
        s = db.get(StudentProfile, int(x.student_id)) if x.student_id else None
        return _fc_row(x, s)
