from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from app.core.exceptions import AppException, not_found
from app.models import InternshipConsent, InternshipRecord, StudentProfile
from app.services.db_service import _as_id, _tid, session

def evaluate_applicability(student, consent_type):
    if consent_type == "STUDENT": return True, "REQUIRED"
    birth = getattr(student, "birth_date", None)
    if not birth: return None, "PENDING_VERIFY"
    if isinstance(birth, str):
        try:
            birth = datetime.fromisoformat(birth[:10]).date()
        except ValueError:
            return None, "PENDING_VERIFY"
    today=datetime.utcnow().date(); age=today.year-birth.year-((today.month,today.day)<(birth.month,birth.day))
    return age < 18, "REQUIRED" if age < 18 else "NOT_APPLICABLE"
def create_pending(body,user=None):
    b=body or {}; typ=(b.get("consentType") or "STUDENT").upper()
    with session() as db:
        from app.modules.internship.services.internship_scope import assert_internship_record_scope
        rec=assert_internship_record_scope(db,b.get("internshipId"),user,"创建知情确认任务")
        stu=db.get(StudentProfile,rec.student_id); applicable, state=evaluate_applicability(stu,typ)
        x=InternshipConsent(tenant_id=_tid(),internship_id=rec.id,batch_id=rec.batch_id,student_id=rec.student_id,consent_type=typ,
            applicable=bool(applicable),participant_name=b.get("participantName"),participant_relation=b.get("participantRelation"),
            content_version=b.get("contentVersion"),content_snapshot=b.get("contentSnapshot"),delivery_channel=b.get("deliveryChannel"),message_id=b.get("messageId"),
            status="PENDING" if applicable is not False else "NOT_APPLICABLE")
        db.add(x);db.commit();return {"id":str(x.id),"status":x.status,"applicability":state}
def mark_viewed(cid):
    with session() as db:
        x=db.get(InternshipConsent,_as_id(cid))
        if not x or x.tenant_id!=_tid(): raise not_found("知情确认不存在")
        x.viewed_at=datetime.utcnow();db.commit();return {"id":str(x.id),"status":x.status}
def confirm(cid,body,user=None):
    b=body or {}
    with session() as db:
        x=db.get(InternshipConsent,_as_id(cid))
        if not x or x.tenant_id!=_tid(): raise not_found("知情确认不存在")
        actor_student_id = str((user or {}).get("studentId") or "")
        if x.consent_type != "STUDENT" or not actor_student_id or actor_student_id != str(x.student_id):
            raise AppException("NO_PERMISSION","学校端不得代确认；仅当前登录学生本人可确认学生知情书")
        if not (b.get("contentSnapshot") or x.content_snapshot): raise AppException("VALIDATION_ERROR","确认必须固化正文快照")
        if x.status == "VALID":
            return {"id": str(x.id), "status": x.status}  # 幂等：已确认不重复改写
        if x.status not in ("PENDING", "REJECTED"):
            raise AppException("DATA_CONFLICT", "当前状态不可确认")
        x.content_snapshot = b.get("contentSnapshot") or x.content_snapshot
        x.confirmation_method = b.get("method") or "ONLINE"
        x.device_digest = b.get("deviceDigest")
        x.confirmed_at = datetime.utcnow()
        x.status = "VALID"
        db.commit()
        return {"id": str(x.id), "status": x.status}


def list_my(user):
    student_id = (user or {}).get("studentId")
    if not student_id:
        raise AppException("NO_PERMISSION", "仅学生本人可访问知情确认")
    with session() as db:
        rows = db.scalars(select(InternshipConsent).where(
            InternshipConsent.tenant_id == _tid(),
            InternshipConsent.student_id == _as_id(student_id),
            InternshipConsent.consent_type == "STUDENT",
            InternshipConsent.is_deleted.is_(False),
        ).order_by(InternshipConsent.id.desc())).all()
        return [{"id": str(x.id), "status": x.status, "contentVersion": x.content_version,
                 "viewedAt": x.viewed_at, "confirmedAt": x.confirmed_at} for x in rows]


def get_my(cid, user):
    student_id = (user or {}).get("studentId")
    if not student_id:
        raise AppException("NO_PERMISSION", "仅学生本人可访问知情确认")
    with session() as db:
        x = db.get(InternshipConsent, _as_id(cid))
        if not x or x.tenant_id != _tid() or x.student_id != _as_id(student_id):
            raise not_found("知情确认不存在")
        if not x.viewed_at:
            x.viewed_at = datetime.utcnow()
            db.commit()
        return {"id": str(x.id), "status": x.status, "contentVersion": x.content_version,
                "contentSnapshot": x.content_snapshot, "viewedAt": x.viewed_at,
                "confirmedAt": x.confirmed_at}
def supersede_for_major_change(db, internship_id, consent_type=None):
    q=select(InternshipConsent).where(InternshipConsent.tenant_id==_tid(),InternshipConsent.internship_id==_as_id(internship_id),InternshipConsent.status=="VALID")
    if consent_type:q=q.where(InternshipConsent.consent_type==consent_type)
    for x in db.scalars(q).all(): x.status="SUPERSEDED"
