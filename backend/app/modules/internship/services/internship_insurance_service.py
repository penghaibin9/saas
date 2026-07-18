"""岗位实习 · 实习保险投保与核验。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import InternshipAuditTrail, InternshipInsurance, InternshipRecord, StudentProfile
from app.services.db_service import _as_id, _iso, _tid, session

STATUS_LABEL = {
    "NOT_SUBMITTED": "未提交", "PENDING_VERIFY": "待核验", "VERIFIED": "已核验", "REJECTED": "已驳回",
}


def _op_name(user=None) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, iid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=iid, target_type="INSURANCE",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _scope(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _row(ins, rec, stu):
    return {
        "id": str(ins.id), "internId": str(ins.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "enterpriseName": rec.enterprise_name if rec else "",
        "policyNo": ins.policy_no or "", "insurerName": ins.insurer_name or "",
        "coverageType": ins.coverage_type or "",
        "effectiveDate": ins.effective_date or "", "expiryDate": ins.expiry_date or "",
        "hasFile": bool(ins.file_id),
        "status": ins.status, "statusLabel": STATUS_LABEL.get(ins.status, ins.status),
        "submittedAt": _iso(ins.submitted_at) or "",
        "verifyComment": ins.verify_comment or "",
    }


def list_insurances(page, page_size, status=None, keyword=None, user=None):
    with session() as db:
        rows = db.scalars(select(InternshipInsurance).where(
            InternshipInsurance.tenant_id == _tid(), InternshipInsurance.is_deleted.is_(False)
        ).order_by(InternshipInsurance.id.desc())).all()
        scope, in_scope = _scope(user)
        items = []
        for ins in rows:
            rec = db.get(InternshipRecord, ins.internship_id)
            stu = db.get(StudentProfile, ins.student_id)
            if status and ins.status != status:
                continue
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            if not in_scope(scope, db, rec, stu):
                continue
            items.append(_row(ins, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def student_submit(user, body) -> dict:
    from app.modules.internship.services.internship_agreement_service import _student_record
    b = body or {}
    policy_no = (b.get("policyNo") or "").strip()
    insurer = (b.get("insurerName") or "").strip()
    if not policy_no or not insurer:
        raise AppException("VALIDATION_ERROR", "保单号与承保单位必填")
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec:
            raise not_found("未找到实习记录")
        ins = db.scalars(select(InternshipInsurance).where(
            InternshipInsurance.tenant_id == _tid(), InternshipInsurance.internship_id == rec.id,
            InternshipInsurance.is_deleted.is_(False))).first()
        if not ins:
            ins = InternshipInsurance(tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id)
            db.add(ins)
        elif ins.status == "VERIFIED":
            raise AppException("DATA_CONFLICT", "保险已核验通过，如需变更请联系管理员")
        ins.policy_no = policy_no
        ins.insurer_name = insurer
        ins.coverage_type = (b.get("coverageType") or "").strip() or None
        ins.effective_date = (b.get("effectiveDate") or "").strip() or None
        ins.expiry_date = (b.get("expiryDate") or "").strip() or None
        if b.get("fileId"):
            ins.file_id = str(b["fileId"]).strip()
        ins.status = "PENDING_VERIFY"
        ins.submitted_at = datetime.utcnow()
        db.flush()
        if rec:
            rec.insurance_info = f"{insurer} · {policy_no} · 待核验"
        _trail(db, ins.id, "SUBMIT", {"policyNo": policy_no}, _op_name(user))
        db.commit()
        return _row(ins, rec, stu)


def verify_insurance(iid, action: str, comment: str = "", user=None) -> dict:
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    with session() as db:
        ins = db.get(InternshipInsurance, _as_id(iid))
        if not ins or ins.is_deleted or ins.tenant_id != _tid():
            raise not_found("保险记录不存在")
        if ins.status != "PENDING_VERIFY":
            raise AppException("DATA_CONFLICT", "仅待核验记录可处理")
        rec = db.get(InternshipRecord, ins.internship_id)
        stu = db.get(StudentProfile, ins.student_id)
        scope, in_scope = _scope(user)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("不在数据范围内")
        ins.status = "VERIFIED" if action == "APPROVE" else "REJECTED"
        ins.verify_comment = (comment or "").strip()
        ins.verified_by_name = _op_name(user)
        ins.verified_at = datetime.utcnow()
        if rec:
            if action == "APPROVE":
                rec.insurance_info = f"{ins.insurer_name} · {ins.policy_no} · 已核验"
            else:
                rec.insurance_info = "保险核验驳回"
        _trail(db, ins.id, f"VERIFY_{action}", {"comment": ins.verify_comment}, _op_name(user))
        db.commit()
        return _row(ins, rec, stu)


def student_my_insurance(user) -> dict | None:
    from app.modules.internship.services.internship_agreement_service import _student_record
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec:
            return None
        ins = db.scalars(select(InternshipInsurance).where(
            InternshipInsurance.tenant_id == _tid(), InternshipInsurance.internship_id == rec.id,
            InternshipInsurance.is_deleted.is_(False))).first()
        if not ins:
            return {"status": "NOT_SUBMITTED", "statusLabel": STATUS_LABEL["NOT_SUBMITTED"]}
        return _row(ins, rec, stu)
