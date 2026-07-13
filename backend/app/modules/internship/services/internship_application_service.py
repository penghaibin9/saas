"""Formal internship applications: student submission, staff review and auditable landing."""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.models import (EmpCompany, InternshipApplication, InternshipAuditTrail, InternshipPosition,
                        InternshipRecord, StudentProfile)
from app.modules.internship.services import internship_student_service as student_svc
from app.services.db_service import _iso, _tid, session

TYPE_LABEL = {"POSITION": "校内岗位志愿", "SELF_ARRANGED": "自主实习"}
STATUS_LABEL = {
    "DRAFT": "草稿", "PENDING_REVIEW": "待审核", "APPROVED": "已通过",
    "REJECTED": "已驳回", "WITHDRAWN": "已撤回", "CANCELLED": "已取消",
}
_ACTIVE = ("DRAFT", "PENDING_REVIEW")
_PHONE = re.compile(r"^[0-9+() -]{7,32}$")


def _op_name(user: dict | None = None) -> str:
    return (user or get_current_user_ctx() or {}).get("realName") or "系统"


def _trail(db, app_id: int, action: str, detail: dict | None = None, user: dict | None = None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=app_id, target_type="APPLICATION", action=action,
        operator_name=_op_name(user), detail_json=detail or {}, occurred_at=datetime.utcnow()))


def _get(db, app_id) -> InternshipApplication:
    app = db.get(InternshipApplication, int(app_id))
    if not app or app.is_deleted or app.tenant_id != _tid():
        raise not_found("实习申请不存在或不在当前数据范围内")
    return app


def _record_for_student(db, student_no: str | None):
    if not student_no:
        raise no_permission("学生身份信息缺失")
    stu = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.student_no == student_no,
        StudentProfile.is_deleted.is_(False))).first()
    if not stu:
        raise not_found("未找到当前学生档案")
    rec = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(), InternshipRecord.student_id == stu.id,
        InternshipRecord.is_deleted.is_(False)).order_by(InternshipRecord.id.desc())).first()
    if not rec:
        raise not_found("当前学生尚无实习档案")
    return rec, stu


def _position(db, position_id) -> tuple[InternshipPosition, EmpCompany]:
    if not position_id:
        raise AppException("VALIDATION_ERROR", "请选择实习岗位")
    pos = db.get(InternshipPosition, int(position_id))
    if not pos or pos.is_deleted or pos.tenant_id != _tid():
        raise not_found("岗位不存在或不在当前数据范围内")
    company = db.get(EmpCompany, pos.company_id)
    if not company or company.is_deleted or company.tenant_id != _tid():
        raise not_found("岗位所属企业不存在")
    if pos.status != "PUBLISHED" or company.blacklist or company.coop_status == "BLACKLIST":
        raise AppException("DATA_CONFLICT", "该岗位当前不可申请")
    if (pos.allocated_count or 0) >= (pos.headcount or 0):
        raise AppException("DATA_CONFLICT", "该岗位已满员")
    return pos, company


def _validate_file(file_id: str | None, required: bool = False) -> str | None:
    fid = (file_id or "").strip()
    if not fid:
        if required:
            raise AppException("VALIDATION_ERROR", "请上传自主实习证明材料")
        return None
    from app.services import file_service
    if not file_service.get_file_meta(fid):
        raise AppException("VALIDATION_ERROR", "证明材料不存在或无权访问，请重新上传")
    return fid


def _clean_self_arranged(body: dict, *, require_complete: bool) -> dict:
    company = (body.get("companyName") or "").strip()
    position = (body.get("positionName") or "").strip()
    address = (body.get("workAddress") or "").strip()
    contact = (body.get("contactName") or "").strip()
    phone = (body.get("contactPhone") or "").strip()
    file_id = _validate_file(body.get("evidenceFileId"), required=require_complete)
    if require_complete:
        for value, label, minimum in ((company, "实习单位名称", 2), (position, "实习岗位", 2),
                                      (address, "工作地点", 5), (contact, "单位联系人", 2)):
            if len(value) < minimum:
                raise AppException("VALIDATION_ERROR", f"{label}填写不完整")
        if not _PHONE.fullmatch(phone):
            raise AppException("VALIDATION_ERROR", "单位联系电话格式不正确")
    return {"company_name": company or None, "position_name": position or None,
            "work_address": address or None, "contact_name": contact or None,
            "contact_phone": phone or None, "evidence_file_id": file_id}


def _row(db, app: InternshipApplication, rec=None, stu=None) -> dict:
    rec = rec or db.get(InternshipRecord, app.record_id)
    stu = stu or db.get(StudentProfile, app.student_id)
    pos = db.get(InternshipPosition, app.position_id) if app.position_id else None
    company = db.get(EmpCompany, pos.company_id) if pos else None
    return {
        "id": str(app.id), "recordId": str(app.record_id), "studentId": str(app.student_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "", "applicationType": app.application_type,
        "applicationTypeLabel": TYPE_LABEL.get(app.application_type, app.application_type),
        "volunteerNo": app.volunteer_no, "positionId": str(app.position_id) if app.position_id else "",
        "companyName": app.company_name or (company.name if company else ""),
        "positionName": app.position_name or (pos.title if pos else ""),
        "workAddress": app.work_address or (pos.work_location if pos else "") or "",
        "contactName": app.contact_name or "", "contactPhone": app.contact_phone or "",
        "evidenceFileId": app.evidence_file_id or "", "applicationNote": app.application_note or "",
        "status": app.status, "statusLabel": STATUS_LABEL.get(app.status, app.status),
        "submittedAt": _iso(app.submitted_at) or "", "reviewedBy": app.reviewed_by_name or "",
        "reviewedAt": _iso(app.reviewed_at) or "", "reviewComment": app.review_comment or "",
        "createdAt": _iso(app.created_at) or "",
    }


def _scope_check(db, rec, stu, user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    if not _rec_in_scope(_current_scope(user), db, rec, stu):
        raise no_permission("不在当前教师数据范围内")


def save_my(user: dict, body: dict) -> dict:
    body = body or {}
    app_type = (body.get("applicationType") or "").upper()
    if app_type not in TYPE_LABEL:
        raise AppException("VALIDATION_ERROR", "applicationType 必须是 POSITION 或 SELF_ARRANGED")
    app_id = body.get("id")
    with session() as db:
        rec, stu = _record_for_student(db, user.get("studentNo"))
        if rec.status not in ("PREPARING", "READY"):
            raise AppException("DATA_CONFLICT", "当前实习状态不可新增或修改申请")
        if rec.position_id or rec.destination_type == "SELF_ARRANGED":
            raise AppException("DATA_CONFLICT", "实习去向已落实，不可再新增或修改申请")
        if app_id:
            app = _get(db, app_id)
            if app.record_id != rec.id or app.student_id != stu.id:
                raise no_permission("只能修改本人的实习申请")
            if app.status not in ("DRAFT", "REJECTED", "WITHDRAWN"):
                raise AppException("DATA_CONFLICT", "当前状态不可修改申请")
            if app.application_type != app_type:
                raise AppException("VALIDATION_ERROR", "申请类型不可变更，请新建申请")
        else:
            volunteer = 0 if app_type == "SELF_ARRANGED" else int(body.get("volunteerNo") or 1)
            invalid_volunteer = (volunteer != 0 if app_type == "SELF_ARRANGED"
                                 else volunteer not in (1, 2, 3))
            if invalid_volunteer:
                raise AppException("VALIDATION_ERROR", "校内岗位志愿顺序只能为 1 至 3")
            app = db.scalars(select(InternshipApplication).where(
                InternshipApplication.tenant_id == _tid(), InternshipApplication.record_id == rec.id,
                InternshipApplication.volunteer_no == volunteer,
                InternshipApplication.is_deleted.is_(False))).first()
            if app:
                if app.status in ("APPROVED", "PENDING_REVIEW"):
                    raise AppException("DATA_CONFLICT", "该志愿已有进行中的申请，不可覆盖")
                app.application_type = app_type
            else:
                app = InternshipApplication(tenant_id=_tid(), record_id=rec.id, student_id=stu.id,
                                             batch_id=rec.batch_id, application_type=app_type,
                                             volunteer_no=volunteer, status="DRAFT")
                db.add(app)
        app.application_note = (body.get("applicationNote") or "").strip() or None
        if app_type == "POSITION":
            pos, company = _position(db, body.get("positionId"))
            duplicate_conditions = [
                InternshipApplication.tenant_id == _tid(), InternshipApplication.record_id == rec.id,
                InternshipApplication.position_id == pos.id, InternshipApplication.status.in_(_ACTIVE),
                InternshipApplication.is_deleted.is_(False),
            ]
            if app.id:
                duplicate_conditions.append(InternshipApplication.id != app.id)
            duplicate = db.scalars(select(InternshipApplication).where(*duplicate_conditions)).first()
            if duplicate:
                raise AppException("DATA_CONFLICT", "同一岗位无需重复申请")
            app.position_id = pos.id
            app.company_name = company.name
            app.position_name = pos.title
            app.work_address = pos.work_location
            app.contact_name = app.contact_phone = app.evidence_file_id = None
        else:
            if rec.position_id:
                raise AppException("DATA_CONFLICT", "已分配校内岗位，请通过实习变更流程申请自主实习")
            app.position_id = None
            for field, value in _clean_self_arranged(body, require_complete=False).items():
                setattr(app, field, value)
        app.status = "DRAFT"
        app.submitted_at = None
        app.reviewed_by_name = app.reviewed_at = app.review_comment = None
        app.version = int(app.version or 0) + 1
        db.flush()
        _trail(db, app.id, "SAVE_DRAFT", {"applicationType": app_type, "volunteerNo": app.volunteer_no}, user)
        db.commit()
        return _row(db, app, rec, stu)


def submit_my(user: dict, app_id) -> dict:
    with session() as db:
        rec, stu = _record_for_student(db, user.get("studentNo"))
        app = _get(db, app_id)
        if app.record_id != rec.id or app.student_id != stu.id:
            raise no_permission("只能提交本人的实习申请")
        if app.status not in ("DRAFT", "REJECTED", "WITHDRAWN"):
            raise AppException("DATA_CONFLICT", "当前申请不可提交")
        if app.application_type == "POSITION":
            pos, company = _position(db, app.position_id)
            app.company_name, app.position_name, app.work_address = company.name, pos.title, pos.work_location
        else:
            payload = _clean_self_arranged({"companyName": app.company_name, "positionName": app.position_name,
                                            "workAddress": app.work_address, "contactName": app.contact_name,
                                            "contactPhone": app.contact_phone, "evidenceFileId": app.evidence_file_id},
                                           require_complete=True)
            for field, value in payload.items():
                setattr(app, field, value)
        app.status = "PENDING_REVIEW"
        app.submitted_at = datetime.utcnow()
        app.version = int(app.version or 0) + 1
        _trail(db, app.id, "SUBMIT", {"applicationType": app.application_type}, user)
        db.commit()
        return _row(db, app, rec, stu)


def withdraw_my(user: dict, app_id) -> dict:
    with session() as db:
        rec, stu = _record_for_student(db, user.get("studentNo"))
        app = _get(db, app_id)
        if app.record_id != rec.id or app.student_id != stu.id:
            raise no_permission("只能撤回本人的实习申请")
        if app.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅待审核申请可撤回")
        app.status = "WITHDRAWN"
        app.version = int(app.version or 0) + 1
        _trail(db, app.id, "WITHDRAW", {}, user)
        db.commit()
        return _row(db, app, rec, stu)


def my_applications(user: dict) -> list[dict]:
    with session() as db:
        rec, stu = _record_for_student(db, user.get("studentNo"))
        rows = db.scalars(select(InternshipApplication).where(
            InternshipApplication.tenant_id == _tid(), InternshipApplication.record_id == rec.id,
            InternshipApplication.is_deleted.is_(False)).order_by(
                InternshipApplication.volunteer_no, InternshipApplication.id.desc())).all()
        return [_row(db, app, rec, stu) for app in rows]


def list_applications(page: int, page_size: int, status=None, application_type=None, keyword=None,
                      user: dict | None = None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(InternshipApplication).where(InternshipApplication.tenant_id == _tid(),
                                                InternshipApplication.is_deleted.is_(False))
        if status:
            q = q.where(InternshipApplication.status == status)
        if application_type:
            q = q.where(InternshipApplication.application_type == application_type)
        rows = db.scalars(q.order_by(InternshipApplication.submitted_at.desc(), InternshipApplication.id.desc())).all()
        from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
        scope = _current_scope(user)
        items = []
        for app in rows:
            rec, stu = db.get(InternshipRecord, app.record_id), db.get(StudentProfile, app.student_id)
            if not rec or not stu:
                continue
            if not _rec_in_scope(scope, db, rec, stu):
                continue
            item = _row(db, app, rec, stu)
            if keyword and keyword.strip().lower() not in (
                    item["studentName"] + item["studentNo"] + item["companyName"] + item["positionName"]).lower():
                continue
            items.append(item)
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_application(app_id, user: dict | None = None) -> dict:
    with session() as db:
        app = _get(db, app_id)
        rec, stu = db.get(InternshipRecord, app.record_id), db.get(StudentProfile, app.student_id)
        _scope_check(db, rec, stu, user)
        item = _row(db, app, rec, stu)
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "APPLICATION",
            InternshipAuditTrail.target_id == app.id).order_by(InternshipAuditTrail.id)).all()
        item["auditTrail"] = [{"action": t.action, "operator": t.operator_name or "",
                               "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at) or ""}
                              for t in trail]
        return item


def review_application(app_id, action: str, comment: str = "", user: dict | None = None) -> dict:
    action = (action or "").upper()
    comment = (comment or "").strip()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE 或 REJECT")
    if action == "REJECT" and len(comment) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因不少于 5 个字符")
    with session() as db:
        app = _get(db, app_id)
        rec, stu = db.get(InternshipRecord, app.record_id), db.get(StudentProfile, app.student_id)
        _scope_check(db, rec, stu, user)
        if app.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅待审核申请可处理")
        if action == "REJECT":
            app.status, app.review_comment = "REJECTED", comment
            app.reviewed_by_name, app.reviewed_at = _op_name(user), datetime.utcnow()
            app.version = int(app.version or 0) + 1
            _trail(db, app.id, "REJECT", {"comment": comment}, user)
            db.commit()
            return _row(db, app, rec, stu)
        record_id, position_id, app_type = app.record_id, app.position_id, app.application_type
        self_company, self_position = app.company_name, app.position_name
    # Existing assignment is the only authoritative capacity write path.
    if app_type == "POSITION":
        student_svc.assign_position(record_id, position_id)
    else:
        student_svc.set_destination(record_id, "SELF_ARRANGED", "审核通过自主实习申请")
        with session() as db:
            rec = db.get(InternshipRecord, record_id)
            rec.enterprise_name = self_company
            rec.position_name = self_position
            db.commit()
    with session() as db:
        app = _get(db, app_id)
        rec, stu = db.get(InternshipRecord, app.record_id), db.get(StudentProfile, app.student_id)
        # A second reviewer may not turn a stale application into a landing record.
        if app.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "申请状态已变更，请刷新后重试")
        app.status, app.review_comment = "APPROVED", comment or None
        app.reviewed_by_name, app.reviewed_at = _op_name(user), datetime.utcnow()
        app.version = int(app.version or 0) + 1
        others = db.scalars(select(InternshipApplication).where(
            InternshipApplication.tenant_id == _tid(), InternshipApplication.record_id == app.record_id,
            InternshipApplication.id != app.id, InternshipApplication.status.in_(_ACTIVE),
            InternshipApplication.is_deleted.is_(False))).all()
        for other in others:
            other.status = "CANCELLED"
            other.review_comment = "已因其他实习申请审核通过而取消"
            other.reviewed_by_name, other.reviewed_at = _op_name(user), datetime.utcnow()
        _trail(db, app.id, "APPROVE", {"applicationType": app.application_type}, user)
        db.commit()
        return _row(db, app, rec, stu)
