"""岗位实习 · 实习保险投保与核验。

学生提交保单必须绑定真实文件；重交和教师核验均使用 expectedVersion，避免
学生、教师或多个审核人并发操作时静默覆盖。所有本人操作复用统一实习批次解析器。
"""
from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

from sqlalchemy import func, or_, select

from app.core.exceptions import AppException, no_permission, not_found
from app.core.tenant_scoped import tenant_get
from app.models import InternshipAuditTrail, InternshipBatch, InternshipInsurance, InternshipRecord, StudentProfile
from app.modules.internship.services.internship_version import (
    extract_expected_version,
    versioned_update,
)
from app.services.db_service import _as_id, _iso, _tid, session

STATUS_LABEL = {
    "NOT_SUBMITTED": "未提交", "PENDING_VERIFY": "待核验",
    "VERIFIED": "已核验", "REJECTED": "已驳回",
}


def _op_name(user=None) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, insurance_id, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=insurance_id, target_type="INSURANCE",
        action=action, operator_name=operator, detail_json=detail or {},
        occurred_at=datetime.utcnow()))


def _scope(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _coverage(ins, rec, batch):
    from app.modules.internship.services.internship_compliance_service import _insurance_coverage
    from app.modules.internship.services.internship_record_resolver import _is_active_record
    status, reason = _insurance_coverage(ins, rec, batch, "CONTINUE")
    period_status, _ = _insurance_coverage(ins, rec, batch, "ASSESS")
    return {
        "coverageStatus": status, "coverageReason": reason,
        "canRenew": ins.status == "VERIFIED" and _is_active_record(rec, batch) and period_status != "VALID",
    }


def _row(ins, rec, stu, *, batch=None):
    result = {
        "id": str(ins.id), "internId": str(ins.internship_id),
        "internshipId": str(ins.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "enterpriseName": rec.enterprise_name if rec else "",
        "policyNo": ins.policy_no or "", "insurerName": ins.insurer_name or "",
        "coverageType": ins.coverage_type or "",
        "effectiveDate": ins.effective_date or "", "expiryDate": ins.expiry_date or "",
        "fileId": ins.file_id or "", "hasFile": bool(ins.file_id),
        "status": ins.status, "statusLabel": STATUS_LABEL.get(ins.status, ins.status),
        "submittedAt": _iso(ins.submitted_at) or "",
        "verifyComment": ins.verify_comment or "",
        "verifiedByName": ins.verified_by_name or "",
        "verifiedAt": _iso(ins.verified_at) or "",
        "version": int(ins.version or 0),
    }
    if batch is not None:
        result.update(_coverage(ins, rec, batch))
    return result


def _validate_file(file_id, *, required=True):
    fid = str(file_id or "").strip()
    if not fid:
        if required:
            raise AppException("VALIDATION_ERROR", "请上传保险凭证文件")
        return None
    from app.services import file_service
    if not file_service.get_file_meta(fid):
        raise AppException("VALIDATION_ERROR", "保险凭证不存在或无权访问，请重新上传")
    return fid


def _validate_dates(effective, expiry):
    start = str(effective or "").strip()
    end = str(expiry or "").strip()
    if not start or not end:
        raise AppException("VALIDATION_ERROR", "保险生效日期与到期日期必填")
    try:
        start_date = date.fromisoformat(start[:10])
        end_date = date.fromisoformat(end[:10])
    except ValueError:
        raise AppException("VALIDATION_ERROR", "保险日期格式必须为 YYYY-MM-DD")
    if end_date < start_date:
        raise AppException("VALIDATION_ERROR", "保险到期日期不能早于生效日期")
    return start_date.isoformat(), end_date.isoformat()


def list_insurances(page, page_size, status=None, keyword=None, batch_id=None, user=None):
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    with session() as db:
        batch = resolve_batch(db, batch_id)
        scoped = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False)), user).subquery()
        query = select(InternshipInsurance, InternshipRecord, StudentProfile).join(
            InternshipRecord, InternshipRecord.id == InternshipInsurance.internship_id
        ).join(
            StudentProfile, StudentProfile.id == InternshipInsurance.student_id
        ).where(
            InternshipInsurance.tenant_id == _tid(),
            InternshipInsurance.is_deleted.is_(False),
            InternshipInsurance.internship_id.in_(select(scoped.c.id)),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        if status:
            query = query.where(InternshipInsurance.status == status)
        term = str(keyword or "").strip()
        if term:
            like = f"%{term}%"
            query = query.where(or_(
                StudentProfile.real_name.like(like),
                StudentProfile.student_no.like(like),
                InternshipInsurance.policy_no.like(like),
            ))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        size = max(0, int(page_size or 0))
        if size == 0:
            return [], total
        rows = db.execute(
            query.order_by(InternshipInsurance.id.desc())
            .offset((max(1, int(page or 1)) - 1) * size).limit(size)
        ).all()
        return [_row(insurance, record, student, batch=batch)
                for insurance, record, student in rows], total


def student_submit(user, body) -> dict:
    from app.modules.internship.services.internship_agreement_service import _student_record
    payload = body or {}
    policy_no = str(payload.get("policyNo") or "").strip()
    insurer = str(payload.get("insurerName") or "").strip()
    if len(policy_no) < 3 or len(insurer) < 2:
        raise AppException("VALIDATION_ERROR", "保单号与承保单位填写不完整")
    effective, expiry = _validate_dates(
        payload.get("effectiveDate"), payload.get("expiryDate"))
    file_id = _validate_file(payload.get("fileId"), required=True)
    with session() as db:
        rec, stu = _student_record(db, user, batch_id=payload.get("batchId"), for_write=True)
        if payload.get("internshipId") is not None and str(payload["internshipId"]) != str(rec.id):
            raise AppException("DATA_CONFLICT", "实习记录与当前批次不一致，请重新读取")
        batch = tenant_get(db, InternshipBatch, rec.batch_id)
        ins = db.scalar(select(InternshipInsurance).where(
            InternshipInsurance.tenant_id == _tid(),
            InternshipInsurance.internship_id == rec.id,
            InternshipInsurance.is_deleted.is_(False)).with_for_update())
        values = {
            "policy_no": policy_no,
            "insurer_name": insurer,
            "coverage_type": str(payload.get("coverageType") or "").strip() or None,
            "effective_date": effective,
            "expiry_date": expiry,
            "file_id": file_id,
            "status": "PENDING_VERIFY",
            "submitted_at": datetime.utcnow(),
            "verify_comment": None,
            "verified_by_name": None,
            "verified_at": None,
        }
        previous = None
        if not ins:
            ins = InternshipInsurance(
                tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id,
                **values)
            db.add(ins)
            db.flush()
            new_version = int(ins.version or 0)
            action = "SUBMIT"
        else:
            if ins.status == "VERIFIED":
                if not _coverage(ins, rec, batch)["canRenew"]:
                    raise AppException("DATA_CONFLICT", "当前保单已核验并覆盖实习期，无需重新提交")
                from app.modules.internship.services.internship_compliance_service import _insurance_coverage
                candidate = SimpleNamespace(effective_date=effective, expiry_date=expiry)
                candidate_status, candidate_reason = _insurance_coverage(candidate, rec, batch, "ASSESS")
                if candidate_status != "VALID":
                    raise AppException("VALIDATION_ERROR", candidate_reason)
                previous = {
                    "version": int(ins.version or 0), "status": ins.status,
                    "fileId": str(ins.file_id or ""), "effectiveDate": ins.effective_date,
                    "expiryDate": ins.expiry_date, "verifiedByName": ins.verified_by_name,
                    "verifiedAt": _iso(ins.verified_at), "verifyComment": ins.verify_comment,
                }
                action = "RENEW"
            else:
                action = "RESUBMIT" if ins.status == "REJECTED" else "UPDATE_PENDING"
            new_version = versioned_update(
                db, InternshipInsurance, entity_id=ins.id, tenant_id=_tid(),
                expected_version=extract_expected_version(payload),
                expected_status=ins.status, values=values)
        # New ORM rows already bind through the after-flush hook. Only atomic
        # SQL replacements need explicit binding; doing both duplicates the
        # pending FileBinding before commit when autoflush is disabled.
        if action != "SUBMIT":
            from app.services.file_business_binding_service import bind_file_to_business
            bind_file_to_business(
                db, file_id=file_id, biz_type="INTERNSHIP_INSURANCE", biz_id=str(ins.id),
                actor=user, subject_type="STUDENT", subject_id=str(stu.id),
                module_code="INTERNSHIP", student_id=stu.id, batch_id=str(rec.batch_id),
                college_id=stu.college_id, class_id=stu.class_id,
                scope={"internshipId": str(rec.id), "studentId": str(stu.id),
                       "studentNo": stu.student_no, "batchId": str(rec.batch_id),
                       "advisorUserId": str(rec.advisor_user_id or ""),
                       "businessType": "INTERNSHIP_INSURANCE", "businessId": str(ins.id)},
                legacy_target_values={str(ins.id), str(rec.id), str(stu.id), str(stu.student_no)},
            )
        rec.insurance_info = f"{insurer} · {policy_no} · 待核验"
        _trail(db, ins.id, action, {
            "policyNoMasked": policy_no[-4:].rjust(len(policy_no), "*"),
            "fileId": file_id, "effectiveDate": effective, "expiryDate": expiry,
            "newVersion": new_version,
            **({"previousPolicy": previous} if previous else {}),
        }, _op_name(user))
        db.commit()
        ins = db.get(InternshipInsurance, ins.id)
        return _row(ins, rec, stu, batch=batch)


def verify_insurance(insurance_id, action: str, comment: str = "", *, expected_version=None,
                     user=None) -> dict:
    action = str(action or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    if action == "REJECT" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    with session() as db:
        ins = db.scalar(select(InternshipInsurance).where(
            InternshipInsurance.id == _as_id(insurance_id),
            InternshipInsurance.tenant_id == _tid(),
            InternshipInsurance.is_deleted.is_(False)).with_for_update())
        if not ins:
            raise not_found("保险记录不存在")
        rec = tenant_get(db, InternshipRecord, ins.internship_id)
        stu = tenant_get(db, StudentProfile, ins.student_id)
        if not rec or not stu:
            raise not_found("保险关联的实习档案不存在或不在当前租户")
        scope, in_scope = _scope(user)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("该保险记录不在你的数据范围内")
        if ins.status != "PENDING_VERIFY":
            raise AppException("DATA_CONFLICT", "仅待核验记录可处理")
        if not ins.file_id or not _validate_file(ins.file_id, required=True):
            raise AppException("DATA_CONFLICT", "保险凭证缺失，不能核验通过")
        new_status = "VERIFIED" if action == "APPROVE" else "REJECTED"
        new_version = versioned_update(
            db, InternshipInsurance, entity_id=ins.id, tenant_id=_tid(),
            expected_version=extract_expected_version({"expectedVersion": expected_version}),
            expected_status="PENDING_VERIFY",
            values={
                "status": new_status,
                "verify_comment": (comment or "").strip() or None,
                "verified_by_name": _op_name(user),
                "verified_at": datetime.utcnow(),
            })
        if rec:
            rec.insurance_info = (
                f"{ins.insurer_name} · {ins.policy_no} · 已核验"
                if action == "APPROVE" else "保险核验驳回")
        _trail(db, ins.id, f"VERIFY_{action}", {
            "comment": (comment or "").strip(), "newVersion": new_version,
        }, _op_name(user))
        db.commit()
        ins = db.get(InternshipInsurance, ins.id)
        return _row(ins, rec, stu, batch=tenant_get(db, InternshipBatch, rec.batch_id))


def student_my_insurance(user) -> dict | None:
    from app.modules.internship.services.internship_agreement_service import _student_record
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec:
            return None
        ins = db.scalars(select(InternshipInsurance).where(
            InternshipInsurance.tenant_id == _tid(),
            InternshipInsurance.internship_id == rec.id,
            InternshipInsurance.is_deleted.is_(False))).first()
        if not ins:
            return {"status": "NOT_SUBMITTED", "statusLabel": STATUS_LABEL["NOT_SUBMITTED"],
                    "version": 0}
        return _row(ins, rec, stu, batch=tenant_get(db, InternshipBatch, rec.batch_id))


def get_insurance(insurance_id, *, batch_id, user=None):
    """Read a deep-linked policy under the same batch and row scope as its queue."""
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    with session() as db:
        batch = resolve_batch(db, batch_id)
        query = select(InternshipInsurance, InternshipRecord, StudentProfile).join(
            InternshipRecord, InternshipRecord.id == InternshipInsurance.internship_id
        ).join(StudentProfile, StudentProfile.id == InternshipInsurance.student_id).where(
            InternshipInsurance.id == _as_id(insurance_id),
            InternshipInsurance.tenant_id == _tid(),
            InternshipInsurance.is_deleted.is_(False),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        row = db.execute(apply_internship_record_scope(query, user)).first()
        if not row:
            raise not_found("保险记录不存在或不在当前可查看范围内")
        return _row(*row, batch=batch)
