"""Formal internship applications: student submission, staff review and auditable landing.

This module is the legacy single-application authority. Recruitment-campaign POSITION applications
belong to VolunteerGroup + EnterpriseDecision V3 and are intentionally invisible here.
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.core.tenant_scoped import tenant_get
from app.models import (EmpCompany, InternshipApplication, InternshipAuditTrail, InternshipPosition,
                        InternshipRecord, StudentProfile)
from app.modules.internship.services import internship_student_service as student_svc
from app.services.db_service import _as_id, _iso, _tid, session

TYPE_LABEL = {"POSITION": "校内岗位志愿", "SELF_ARRANGED": "自主实习", "EXEMPTION": "免实习申请"}
STATUS_LABEL = {
    "DRAFT": "草稿", "PENDING_REVIEW": "待审核", "APPROVED": "已通过",
    "REJECTED": "已驳回", "WITHDRAWN": "已撤回", "CANCELLED": "已取消",
}
_ACTIVE = ("DRAFT", "PENDING_REVIEW")
_PHONE = re.compile(r"^[0-9+() -]{7,32}$")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_CREDIT_CODE = re.compile(r"^[0-9A-HJ-NPQRTUWXY]{18}$")
_POSTAL_CODE = re.compile(r"^[0-9A-Za-z -]{3,20}$")


def _op_name(user: dict | None = None) -> str:
    return (user or get_current_user_ctx() or {}).get("realName") or "系统"


def _trail(db, app_id: int, action: str, detail: dict | None = None, user: dict | None = None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=app_id, target_type="APPLICATION", action=action,
        operator_name=_op_name(user), detail_json=detail or {}, occurred_at=datetime.utcnow()))


def _get(db, app_id) -> InternshipApplication:
    """Generic loader retained for non-legacy internal compatibility; caller owns Authority scope."""
    app = db.get(InternshipApplication, _as_id(app_id))
    if not app or app.is_deleted or app.tenant_id != _tid():
        raise not_found("实习申请不存在或不在当前数据范围内")
    return app


def _get_legacy_application(db, app_id, *, lock: bool = False) -> InternshipApplication:
    """Resolve only campaign_id=NULL rows for every registered legacy student/staff route."""
    q = select(InternshipApplication).where(
        InternshipApplication.id == _as_id(app_id),
        InternshipApplication.tenant_id == _tid(),
        InternshipApplication.campaign_id.is_(None),
        InternshipApplication.is_deleted.is_(False),
    )
    app = db.scalar(q.with_for_update() if lock else q)
    if not app:
        raise not_found("实习申请不存在或不在当前数据范围内")
    return app


def _get_legacy_student_application(db, app_id, *, lock: bool = False) -> InternshipApplication:
    """Named student seam kept explicit for regression contracts and route intent."""
    return _get_legacy_application(db, app_id, lock=lock)


def _record_for_student(db, student_no: str | None, *, batch_id=None, for_write: bool = True):
    """学生本人申请写路径：统一解析器。"""
    from app.modules.internship.services.internship_record_resolver import (
        require_active_student_record,
        resolve_optional_student_record,
    )
    if not student_no:
        raise no_permission("学生身份信息缺失")
    if for_write:
        return require_active_student_record(db, batch_id=batch_id, student_no=student_no)
    rec, stu, ctx = resolve_optional_student_record(db, batch_id=batch_id, student_no=student_no)
    if not stu:
        raise not_found("未找到当前学生档案")
    if not rec:
        raise not_found(ctx.message or "当前学生尚无实习档案")
    return rec, stu


def _position(db, position_id) -> tuple[InternshipPosition, EmpCompany]:
    if not position_id:
        raise AppException("VALIDATION_ERROR", "请选择实习岗位")
    pos = db.get(InternshipPosition, _as_id(position_id))
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


def _legacy_position(db, position_id) -> tuple[InternshipPosition, EmpCompany]:
    """Legacy single-application routes may never write a V3 recruitment-campaign position."""
    pos, company = _position(db, position_id)
    if pos.campaign_id is not None:
        raise AppException(
            "DATA_CONFLICT",
            "招聘季岗位必须通过三志愿原子接口保存/提交，不能逐条写入正式申请",
            http_status=409,
        )
    return pos, company


def _validate_file(file_id: str | None, required: bool = False) -> str | None:
    fid = (file_id or "").strip()
    if not fid:
        if required:
            raise AppException("VALIDATION_ERROR", "请上传申请证明材料")
        return None
    from app.services import file_service
    if not file_service.get_file_meta(fid):
        raise AppException("VALIDATION_ERROR", "证明材料不存在或无权访问，请重新上传")
    return fid


def _text(body: dict, key: str, *, max_len: int, label: str,
          required: bool = False, min_len: int = 1) -> str | None:
    value = str((body or {}).get(key) or "").strip()
    if required and len(value) < min_len:
        raise AppException("VALIDATION_ERROR", f"{label}填写不完整")
    if len(value) > max_len:
        raise AppException("VALIDATION_ERROR", f"{label}不能超过{max_len}个字符")
    return value or None


def _date_value(value, label: str, *, required: bool) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        if required:
            raise AppException("VALIDATION_ERROR", f"请填写{label}")
        return None
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d")
    except ValueError:
        raise AppException("VALIDATION_ERROR", f"{label}格式必须为 YYYY-MM-DD") from None


def _salary_value(value, *, required: bool):
    if value is None or str(value).strip() == "":
        if required:
            raise AppException("VALIDATION_ERROR", "请填写实习薪资")
        return None
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise AppException("VALIDATION_ERROR", "实习薪资格式不正确") from None
    if amount < 0 or amount > Decimal("100000000"):
        raise AppException("VALIDATION_ERROR", "实习薪资超出允许范围")
    return amount


def _file_ids(value, *, max_items: int = 9) -> list[str] | None:
    raw = value if isinstance(value, list) else []
    ids = []
    for item in raw:
        fid = _validate_file(str(item or "").strip(), required=False)
        if fid and fid not in ids:
            ids.append(fid)
    if len(ids) > max_items:
        raise AppException("VALIDATION_ERROR", f"三方协议照片最多上传{max_items}份")
    return ids or None


def _clean_exemption(body: dict, *, require_complete: bool) -> dict:
    """Normalize SM16 exemption fields; approval is the only path that writes EXEMPTED."""
    exemption_type = str((body or {}).get("exemptionType") or "").strip().upper()
    allowed_types = {"FURTHER_STUDY", "MILITARY", "HEALTH", "OTHER"}
    if require_complete and exemption_type not in allowed_types:
        raise AppException("VALIDATION_ERROR", "请选择免实习类型")
    if exemption_type and exemption_type not in allowed_types:
        raise AppException("VALIDATION_ERROR", "免实习类型不合法")
    return {
        "exemption_type": exemption_type or None,
        "exemption_reason": _text(
            body, "exemptionReason", max_len=500, label="免实习原因",
            required=require_complete, min_len=5),
        "exemption_destination": _text(
            body, "exemptionDestination", max_len=200, label="免实习后去向",
            required=require_complete, min_len=2),
        "evidence_file_id": _validate_file(
            (body or {}).get("evidenceFileId"), required=require_complete),
    }


def _clean_self_arranged(body: dict, *, require_complete: bool) -> dict:
    """Normalize the Yiyang complete internship-position snapshot.

    Registry verification fields are intentionally absent here: student input can never turn a
    company into a government-registry verified company. G03 will write those fields only through
    the authorized provider adapter.
    """
    company = _text(body, "companyName", max_len=200, label="实习单位名称",
                    required=require_complete, min_len=2)
    position = _text(body, "positionName", max_len=100, label="实习岗位",
                     required=require_complete, min_len=2)
    address = _text(body, "workAddress", max_len=300, label="岗位地址",
                    required=require_complete, min_len=5)
    contact = _text(body, "contactName", max_len=100, label="单位联系人",
                    required=require_complete, min_len=2)
    phone = _text(body, "contactPhone", max_len=64, label="单位联系电话",
                  required=require_complete, min_len=7)
    credit_code = _text(body, "companyCreditCode", max_len=50, label="统一社会信用代码",
                        required=require_complete, min_len=18)
    company_phone = _text(body, "companyPhone", max_len=64, label="企业联系电话",
                          required=require_complete, min_len=7)
    email = _text(body, "companyEmail", max_len=200, label="企业邮箱",
                  required=require_complete, min_len=3)
    postal = _text(body, "companyPostalCode", max_len=20, label="企业邮编", required=False)
    mentor_phone = _text(body, "enterpriseMentorPhone", max_len=64, label="企业老师联系电话",
                         required=require_complete, min_len=7)
    start_date = _date_value((body or {}).get("internshipStartDate"), "实习开始日期",
                             required=require_complete)
    end_date = _date_value((body or {}).get("internshipEndDate"), "实习结束日期",
                           required=require_complete)
    if start_date and end_date and start_date > end_date:
        raise AppException("VALIDATION_ERROR", "实习结束日期不能早于开始日期")
    if require_complete and credit_code and not _CREDIT_CODE.fullmatch(credit_code.upper()):
        raise AppException("VALIDATION_ERROR", "统一社会信用代码应为18位规范代码")
    if phone and not _PHONE.fullmatch(phone):
        raise AppException("VALIDATION_ERROR", "单位联系电话格式不正确")
    if company_phone and not _PHONE.fullmatch(company_phone):
        raise AppException("VALIDATION_ERROR", "企业联系电话格式不正确")
    if mentor_phone and not _PHONE.fullmatch(mentor_phone):
        raise AppException("VALIDATION_ERROR", "企业老师联系电话格式不正确")
    if email and not _EMAIL.fullmatch(email):
        raise AppException("VALIDATION_ERROR", "企业邮箱格式不正确")
    if postal and not _POSTAL_CODE.fullmatch(postal):
        raise AppException("VALIDATION_ERROR", "企业邮编格式不正确")

    major_match = (body or {}).get("majorMatch")
    if require_complete and not isinstance(major_match, bool):
        raise AppException("VALIDATION_ERROR", "请选择岗位是否专业对口")
    if major_match is not None and not isinstance(major_match, bool):
        raise AppException("VALIDATION_ERROR", "majorMatch 必须为布尔值")

    return {
        "company_name": company,
        "position_name": position,
        "work_address": address,
        "contact_name": contact,
        "contact_phone": phone,
        "evidence_file_id": _validate_file((body or {}).get("evidenceFileId"),
                                            required=require_complete),
        "company_credit_code": credit_code.upper() if credit_code else None,
        "company_principal": _text(body, "companyPrincipal", max_len=100, label="企业负责人",
                                   required=require_complete, min_len=2),
        "company_scale": _text(body, "companyScale", max_len=50, label="企业规模",
                               required=require_complete),
        "company_phone": company_phone,
        "company_email": email,
        "company_nature": _text(body, "companyNature", max_len=50, label="单位性质",
                                required=require_complete),
        "company_industry": _text(body, "companyIndustry", max_len=100, label="所属行业",
                                  required=require_complete),
        "company_registered_address": _text(
            body, "companyRegisteredAddress", max_len=300, label="单位注册地址",
            required=require_complete, min_len=5),
        "company_postal_code": postal,
        "company_province": _text(body, "companyProvince", max_len=50, label="单位所在省",
                                  required=require_complete),
        "company_city": _text(body, "companyCity", max_len=50, label="单位所在市",
                              required=require_complete),
        "company_district": _text(body, "companyDistrict", max_len=50, label="单位所在区县",
                                  required=require_complete),
        "internship_department": _text(body, "internshipDepartment", max_len=100, label="实习部门",
                                       required=require_complete),
        "work_content": _text(body, "workContent", max_len=4000, label="工作内容",
                              required=require_complete, min_len=5),
        "enterprise_mentor_name": _text(
            body, "enterpriseMentorName", max_len=100, label="企业老师",
            required=require_complete, min_len=2),
        "enterprise_mentor_phone": mentor_phone,
        "position_category": _text(body, "positionCategory", max_len=50, label="岗位类别",
                                   required=require_complete),
        "work_country": _text(body, "workCountry", max_len=100, label="实习国家（地区）",
                              required=False),
        "work_province": _text(body, "workProvince", max_len=50, label="岗位所在省",
                               required=require_complete),
        "work_city": _text(body, "workCity", max_len=50, label="岗位所在市",
                           required=require_complete),
        "work_district": _text(body, "workDistrict", max_len=50, label="岗位所在区县",
                               required=require_complete),
        "internship_start_date": start_date,
        "internship_end_date": end_date,
        "internship_mode": _text(body, "internshipMode", max_len=30, label="实习方式",
                                 required=require_complete),
        "major_match": major_match if isinstance(major_match, bool) else None,
        "agreed_salary": _salary_value((body or {}).get("agreedSalary"),
                                       required=require_complete),
        "agreement_file_ids": _file_ids((body or {}).get("agreementFileIds")),
    }


def _snapshot_body(row: InternshipApplication) -> dict:
    return {
        "companyName": row.company_name,
        "positionName": row.position_name,
        "workAddress": row.work_address,
        "contactName": row.contact_name,
        "contactPhone": row.contact_phone,
        "evidenceFileId": row.evidence_file_id,
        "exemptionType": row.exemption_type,
        "exemptionReason": row.exemption_reason,
        "exemptionDestination": row.exemption_destination,
        "companyCreditCode": row.company_credit_code,
        "companyPrincipal": row.company_principal,
        "companyScale": row.company_scale,
        "companyPhone": row.company_phone,
        "companyEmail": row.company_email,
        "companyNature": row.company_nature,
        "companyIndustry": row.company_industry,
        "companyRegisteredAddress": row.company_registered_address,
        "companyPostalCode": row.company_postal_code,
        "companyProvince": row.company_province,
        "companyCity": row.company_city,
        "companyDistrict": row.company_district,
        "internshipDepartment": row.internship_department,
        "workContent": row.work_content,
        "enterpriseMentorName": row.enterprise_mentor_name,
        "enterpriseMentorPhone": row.enterprise_mentor_phone,
        "positionCategory": row.position_category,
        "workCountry": row.work_country,
        "workProvince": row.work_province,
        "workCity": row.work_city,
        "workDistrict": row.work_district,
        "internshipStartDate": _iso(row.internship_start_date),
        "internshipEndDate": _iso(row.internship_end_date),
        "internshipMode": row.internship_mode,
        "majorMatch": row.major_match,
        "agreedSalary": row.agreed_salary,
        "agreementFileIds": list(row.agreement_file_ids or []),
    }


def _apply_position_snapshot(app: InternshipApplication, pos: InternshipPosition,
                             company: EmpCompany) -> None:
    """Freeze what the school catalog actually knows; never fabricate registry verification."""
    app.company_name = company.name
    app.position_name = pos.title
    app.work_address = pos.work_address or pos.work_location
    app.company_credit_code = company.credit_code
    app.company_scale = company.scale
    app.company_nature = company.nature
    app.company_industry = company.industry
    app.company_registered_address = company.address
    app.company_city = company.city
    app.contact_name = company.contact_person
    app.internship_department = None
    app.work_content = pos.work_content
    app.enterprise_mentor_name = pos.mentor_name
    app.position_category = pos.category
    app.agreed_salary = pos.remuneration_amount
    app.registry_verification_status = "UNVERIFIED"
    app.registry_verification_provider = None
    app.registry_reference = None
    app.registry_verified_at = None

def _row(db, app: InternshipApplication, rec=None, stu=None, *,
         pos=None, company=None, preloaded: bool = False) -> dict:
    rec = rec or tenant_get(db, InternshipRecord, app.record_id, tenant_id=app.tenant_id)
    stu = stu or tenant_get(db, StudentProfile, app.student_id, tenant_id=app.tenant_id)
    if not preloaded:
        pos = tenant_get(db, InternshipPosition, app.position_id, tenant_id=app.tenant_id) if app.position_id else None
        company = tenant_get(db, EmpCompany, pos.company_id, tenant_id=app.tenant_id) if pos else None
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
        "evidenceFileId": app.evidence_file_id or "",
        "companyCreditCode": app.company_credit_code or "",
        "companyPrincipal": app.company_principal or "",
        "companyScale": app.company_scale or "",
        "companyPhone": app.company_phone or "",
        "companyEmail": app.company_email or "",
        "companyNature": app.company_nature or "",
        "companyIndustry": app.company_industry or "",
        "companyRegisteredAddress": app.company_registered_address or "",
        "companyPostalCode": app.company_postal_code or "",
        "companyProvince": app.company_province or "",
        "companyCity": app.company_city or "",
        "companyDistrict": app.company_district or "",
        "internshipDepartment": app.internship_department or "",
        "workContent": app.work_content or "",
        "enterpriseMentorName": app.enterprise_mentor_name or "",
        "enterpriseMentorPhone": app.enterprise_mentor_phone or "",
        "positionCategory": app.position_category or "",
        "workCountry": app.work_country or "",
        "workProvince": app.work_province or "",
        "workCity": app.work_city or "",
        "workDistrict": app.work_district or "",
        "internshipStartDate": (_iso(app.internship_start_date) or "")[:10],
        "internshipEndDate": (_iso(app.internship_end_date) or "")[:10],
        "internshipMode": app.internship_mode or "",
        "majorMatch": app.major_match,
        "agreedSalary": float(app.agreed_salary) if app.agreed_salary is not None else None,
        "agreementFileIds": list(app.agreement_file_ids or []),
        "companyRegistryStatus": app.registry_verification_status or "UNVERIFIED",
        "companyRegistryVerified": app.registry_verification_status == "VERIFIED",
        "companyRegistryProvider": app.registry_verification_provider or "",
        "companyRegistryReference": app.registry_reference or "",
        "companyRegistryVerifiedAt": _iso(app.registry_verified_at) or "",
        "applicationNote": app.application_note or "",
        "exemptionType": app.exemption_type or "",
        "exemptionReason": app.exemption_reason or "",
        "exemptionDestination": app.exemption_destination or "",
        "status": app.status, "statusLabel": STATUS_LABEL.get(app.status, app.status),
        "submittedAt": _iso(app.submitted_at) or "", "reviewedBy": app.reviewed_by_name or "",
        "reviewedAt": _iso(app.reviewed_at) or "", "reviewComment": app.review_comment or "",
        "version": int(app.version or 0),
        "recordVersion": int(rec.version or 0) if rec else None,
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
        raise AppException("VALIDATION_ERROR", "applicationType 必须是 POSITION、SELF_ARRANGED 或 EXEMPTION")
    app_id = body.get("id")
    with session() as db:
        rec, stu = _record_for_student(db, user.get("studentNo"))
        if rec.status not in ("PREPARING", "READY"):
            raise AppException("DATA_CONFLICT", "当前实习状态不可新增或修改申请")
        if rec.position_id or rec.destination_type in ("SELF_ARRANGED", "EXEMPTED"):
            raise AppException("DATA_CONFLICT", "实习去向已落实，不可再新增或修改申请")
        if app_id:
            app = _get_legacy_student_application(db, app_id, lock=True)
            if app.record_id != rec.id or app.student_id != stu.id:
                raise no_permission("只能修改本人的实习申请")
            if app.status not in ("DRAFT", "REJECTED", "WITHDRAWN"):
                raise AppException("DATA_CONFLICT", "当前状态不可修改申请")
            if app.application_type != app_type:
                raise AppException("VALIDATION_ERROR", "申请类型不可变更，请新建申请")
        else:
            if app_type == "SELF_ARRANGED":
                volunteer = 0
            elif app_type == "EXEMPTION":
                volunteer = -1
            else:
                volunteer = int(body.get("volunteerNo") or 1)
            if app_type == "POSITION" and volunteer not in (1, 2, 3):
                raise AppException("VALIDATION_ERROR", "校内岗位志愿顺序只能为 1 至 3")
            app = db.scalars(select(InternshipApplication).where(
                InternshipApplication.tenant_id == _tid(), InternshipApplication.record_id == rec.id,
                InternshipApplication.campaign_id.is_(None),
                InternshipApplication.volunteer_no == volunteer,
                InternshipApplication.is_deleted.is_(False)).with_for_update()).first()
            if app:
                if app.status in ("APPROVED", "PENDING_REVIEW"):
                    raise AppException("DATA_CONFLICT", "该志愿已有进行中的申请，不可覆盖")
                app.application_type = app_type
            else:
                app = InternshipApplication(tenant_id=_tid(), record_id=rec.id, student_id=stu.id,
                                             batch_id=rec.batch_id, campaign_id=None,
                                             application_type=app_type,
                                             volunteer_no=volunteer, status="DRAFT")
                db.add(app)
        app.application_note = (body.get("applicationNote") or "").strip() or None
        before_company_identity = (app.company_name or "", app.company_credit_code or "")
        if app_type == "POSITION":
            pos, company = _legacy_position(db, body.get("positionId"))
            duplicate_conditions = [
                InternshipApplication.tenant_id == _tid(), InternshipApplication.record_id == rec.id,
                InternshipApplication.campaign_id.is_(None),
                InternshipApplication.position_id == pos.id, InternshipApplication.status.in_(_ACTIVE),
                InternshipApplication.is_deleted.is_(False),
            ]
            if app.id:
                duplicate_conditions.append(InternshipApplication.id != app.id)
            duplicate = db.scalars(select(InternshipApplication).where(*duplicate_conditions)).first()
            if duplicate:
                raise AppException("DATA_CONFLICT", "同一岗位无需重复申请")
            app.position_id = pos.id
            _apply_position_snapshot(app, pos, company)
            app.contact_phone = app.evidence_file_id = None
        else:
            if rec.position_id:
                raise AppException("DATA_CONFLICT", "已分配校内岗位，请通过实习变更流程申请自主实习")
            app.position_id = None
            for field, value in _clean_self_arranged(body, require_complete=False).items():
                setattr(app, field, value)
            if before_company_identity != (app.company_name or "", app.company_credit_code or ""):
                app.registry_verification_status = "UNVERIFIED"
                app.registry_verification_provider = None
                app.registry_reference = None
                app.registry_verified_at = None
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
        app = _get_legacy_student_application(db, app_id, lock=True)
        if app.record_id != rec.id or app.student_id != stu.id:
            raise no_permission("只能提交本人的实习申请")
        if app.status not in ("DRAFT", "REJECTED", "WITHDRAWN"):
            raise AppException("DATA_CONFLICT", "当前申请不可提交")
        if app.application_type == "POSITION":
            pos, company = _legacy_position(db, app.position_id)
            _apply_position_snapshot(app, pos, company)
        elif app.application_type == "EXEMPTION":
            payload = _clean_exemption(_snapshot_body(app), require_complete=True)
            for field, value in payload.items():
                setattr(app, field, value)
        else:
            payload = _clean_self_arranged(_snapshot_body(app), require_complete=True)
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
        app = _get_legacy_student_application(db, app_id, lock=True)
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
            InternshipApplication.campaign_id.is_(None),
            InternshipApplication.is_deleted.is_(False)).order_by(
                InternshipApplication.volunteer_no, InternshipApplication.id.desc())).all()
        return [_row(db, app, rec, stu) for app in rows]


def list_applications(page: int, page_size: int, status=None, application_type=None, keyword=None,
                      batch_id=None, user: dict | None = None) -> tuple[list[dict], int]:
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    with session() as db:
        batch = resolve_batch(db, batch_id)
        scoped = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False)), user).subquery()
        query = select(
            InternshipApplication, InternshipRecord, StudentProfile,
            InternshipPosition, EmpCompany,
        ).join(
            InternshipRecord, InternshipRecord.id == InternshipApplication.record_id
        ).join(
            StudentProfile, StudentProfile.id == InternshipApplication.student_id
        ).outerjoin(
            InternshipPosition, InternshipPosition.id == InternshipApplication.position_id
        ).outerjoin(
            EmpCompany, EmpCompany.id == InternshipPosition.company_id
        ).where(
            InternshipApplication.tenant_id == _tid(),
            InternshipApplication.campaign_id.is_(None),
            InternshipApplication.is_deleted.is_(False),
            InternshipApplication.record_id.in_(select(scoped.c.id)),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        status_value = str(status or "").strip().upper()
        if status_value and status_value != "ALL":
            if status_value == "REVIEWED":
                query = query.where(InternshipApplication.status.in_(("APPROVED", "REJECTED")))
            elif status_value in STATUS_LABEL:
                query = query.where(InternshipApplication.status == status_value)
            else:
                raise AppException("VALIDATION_ERROR", "不支持的实习申请审核状态")
        if application_type:
            query = query.where(InternshipApplication.application_type == application_type)
        term = str(keyword or "").strip()
        if term:
            like = f"%{term}%"
            query = query.where(or_(
                StudentProfile.real_name.like(like),
                StudentProfile.student_no.like(like),
                InternshipApplication.company_name.like(like),
                InternshipApplication.company_credit_code.like(like),
                InternshipApplication.position_name.like(like),
                InternshipApplication.internship_department.like(like),
                InternshipApplication.position_category.like(like),
                InternshipApplication.company_industry.like(like),
            ))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        size = max(0, int(page_size or 0))
        if size == 0:
            return [], total
        rows = db.execute(
            query.order_by(
                InternshipApplication.submitted_at.desc(),
                InternshipApplication.id.desc(),
            ).offset((max(1, int(page or 1)) - 1) * size).limit(size)
        ).all()
        return [
            _row(db, application, record, student,
                 pos=position, company=company, preloaded=True)
            for application, record, student, position, company in rows
        ], total


_CURRENT_FILLED_STATUSES = ("DRAFT", "PENDING_REVIEW", "APPROVED", "REJECTED")


def application_summary(batch_id=None, user: dict | None = None) -> dict:
    """Yiyang C04/G10: authoritative full-scope application coverage and review counts.

    filledStudents is student/record based, never page based. A current application in
    DRAFT/PENDING_REVIEW/APPROVED/REJECTED counts as filled; WITHDRAWN/CANCELLED does not.
    Review counters are application based so approved/rejected history stays auditable.
    """
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    with session() as db:
        batch = resolve_batch(db, batch_id)
        scoped = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False),
            ),
            user,
        ).subquery()
        scoped_ids = select(scoped.c.id)
        total_students = int(db.scalar(select(func.count()).select_from(scoped)) or 0)

        filled = select(InternshipApplication.record_id).where(
            InternshipApplication.tenant_id == _tid(),
            InternshipApplication.campaign_id.is_(None),
            InternshipApplication.is_deleted.is_(False),
            InternshipApplication.record_id.in_(scoped_ids),
            InternshipApplication.status.in_(_CURRENT_FILLED_STATUSES),
        ).distinct().subquery()
        filled_students = int(db.scalar(select(func.count()).select_from(filled)) or 0)

        status_rows = db.execute(
            select(InternshipApplication.status, func.count(InternshipApplication.id))
            .where(
                InternshipApplication.tenant_id == _tid(),
                InternshipApplication.campaign_id.is_(None),
                InternshipApplication.is_deleted.is_(False),
                InternshipApplication.record_id.in_(scoped_ids),
            )
            .group_by(InternshipApplication.status)
        ).all()
        counts = {str(status): int(count or 0) for status, count in status_rows}
        approved = counts.get("APPROVED", 0)
        rejected = counts.get("REJECTED", 0)
        unfilled_students = max(0, total_students - filled_students)
        filled_rate = round((filled_students * 100.0 / total_students), 1) if total_students else 0.0

        return {
            "batchId": str(batch.id),
            "totalStudents": total_students,
            "filledStudents": filled_students,
            "unfilledStudents": unfilled_students,
            "filledRate": filled_rate,
            "pendingReviewApplications": counts.get("PENDING_REVIEW", 0),
            "reviewedApplications": approved + rejected,
            "approvedApplications": approved,
            "rejectedApplications": rejected,
            "draftApplications": counts.get("DRAFT", 0),
            "withdrawnApplications": counts.get("WITHDRAWN", 0),
            "cancelledApplications": counts.get("CANCELLED", 0),
            "definition": {
                "filled": "当前批次数据范围内存在草稿、待审核、已通过或已驳回的正式实习申请",
                "unfilled": "当前批次数据范围内不存在上述当前填报事实；已撤回/已取消不计当前填报",
                "reviewed": "已通过 + 已驳回申请数",
            },
        }


def list_application_students(page: int, page_size: int, state: str, *, batch_id=None,
                              keyword: str | None = None,
                              user: dict | None = None) -> tuple[list[dict], int]:
    """Yiyang C04/G10 drill-down for filled/unfilled student numerators/denominators."""
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    state_value = str(state or "").strip().upper()
    if state_value not in ("FILLED", "UNFILLED"):
        raise AppException("VALIDATION_ERROR", "state 必须是 FILLED 或 UNFILLED")

    with session() as db:
        batch = resolve_batch(db, batch_id)
        scoped = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False),
            ),
            user,
        ).subquery()
        scoped_ids = select(scoped.c.id)
        filled_record_ids = select(InternshipApplication.record_id).where(
            InternshipApplication.tenant_id == _tid(),
            InternshipApplication.campaign_id.is_(None),
            InternshipApplication.is_deleted.is_(False),
            InternshipApplication.record_id.in_(scoped_ids),
            InternshipApplication.status.in_(_CURRENT_FILLED_STATUSES),
        ).distinct()

        query = select(InternshipRecord, StudentProfile).join(
            StudentProfile, StudentProfile.id == InternshipRecord.student_id
        ).where(
            InternshipRecord.id.in_(scoped_ids),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        if state_value == "FILLED":
            query = query.where(InternshipRecord.id.in_(filled_record_ids))
        else:
            query = query.where(InternshipRecord.id.not_in(filled_record_ids))

        term = str(keyword or "").strip()
        if term:
            like = f"%{term}%"
            query = query.where(or_(
                StudentProfile.real_name.like(like),
                StudentProfile.student_no.like(like),
                InternshipRecord.enterprise_name.like(like),
                InternshipRecord.position_name.like(like),
            ))

        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        size = max(1, min(200, int(page_size or 20)))
        rows = db.execute(
            query.order_by(StudentProfile.student_no, StudentProfile.id)
            .offset((max(1, int(page or 1)) - 1) * size)
            .limit(size)
        ).all()
        return [
            {
                "recordId": str(record.id),
                "studentId": str(student.id),
                "studentName": student.real_name or "-",
                "studentNo": student.student_no or "-",
                "advisorName": record.advisor_name or "",
                "internshipStatus": record.status or "",
                "destinationType": record.destination_type or "",
                "companyName": record.enterprise_name or "",
                "positionName": record.position_name or "",
                "applicationState": state_value,
            }
            for record, student in rows
        ], total

def get_application(app_id, user: dict | None = None) -> dict:
    with session() as db:
        app = _get_legacy_application(db, app_id)
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


_CANCEL_SIBLING_COMMENT = "已因其他实习申请审核通过而取消"


def _exc_reason(exc: BaseException) -> str:
    if isinstance(exc, AppException):
        return (exc.message or "")[:500]
    return (str(exc) or type(exc).__name__)[:500]


def _rollback_approved_application(app_id, cancelled_siblings, user: dict | None = None,
                                   reason: str = "") -> None:
    """落岗失败补偿：仅补偿 legacy application，不得回写 campaign V3 行。"""
    with session() as db:
        app = db.scalar(select(InternshipApplication).where(
            InternshipApplication.id == _as_id(app_id),
            InternshipApplication.tenant_id == _tid(),
            InternshipApplication.campaign_id.is_(None),
            InternshipApplication.is_deleted.is_(False),
        ).with_for_update())
        if not app or app.status != "APPROVED":
            return
        app.status = "PENDING_REVIEW"
        app.review_comment = None
        app.reviewed_by_name = None
        app.reviewed_at = None
        app.version = int(app.version or 0) + 1
        for snap in cancelled_siblings or []:
            other = db.scalar(select(InternshipApplication).where(
                InternshipApplication.id == _as_id(snap["id"]),
                InternshipApplication.tenant_id == _tid(),
                InternshipApplication.campaign_id.is_(None),
                InternshipApplication.is_deleted.is_(False),
            ).with_for_update())
            if not other:
                continue
            if other.status != "CANCELLED":
                continue
            if (other.review_comment or "") != _CANCEL_SIBLING_COMMENT:
                continue
            other.status = snap["status"]
            other.review_comment = snap.get("review_comment")
            other.reviewed_by_name = snap.get("reviewed_by_name")
            other.reviewed_at = snap.get("reviewed_at")
            other.version = int(other.version or 0) + 1
        _trail(db, app.id, "APPROVE_ROLLBACK", {"reason": reason or "落岗失败"}, user)
        db.commit()


def review_application(app_id, action: str, comment: str = "", user: dict | None = None,
                       *, expected_version=None, record_expected_version=None,
                       expected_batch_id=None) -> dict:
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )
    action = (action or "").upper()
    comment = (comment or "").strip()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE 或 REJECT")
    if action == "REJECT" and len(comment) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因不少于 5 个字符")
    ver = extract_expected_version({"expectedVersion": expected_version})
    with session() as db:
        app = db.scalar(select(InternshipApplication).where(
            InternshipApplication.id == _as_id(app_id),
            InternshipApplication.tenant_id == _tid(),
            InternshipApplication.campaign_id.is_(None),
            InternshipApplication.is_deleted.is_(False)).with_for_update())
        if not app:
            raise not_found("实习申请不存在")
        rec = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == app.record_id,
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False)).with_for_update())
        stu = db.get(StudentProfile, app.student_id)
        _scope_check(db, rec, stu, user)
        from app.modules.internship.services.internship_batch_context import assert_record_batch
        assert_record_batch(rec, expected_batch_id)
        if app.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅待审核申请可处理")
        if action == "REJECT":
            new_ver = versioned_update(
                db, InternshipApplication, entity_id=app.id, tenant_id=_tid(),
                expected_version=ver, expected_status="PENDING_REVIEW",
                values={
                    "status": "REJECTED",
                    "review_comment": comment,
                    "reviewed_by_name": _op_name(user),
                    "reviewed_at": datetime.utcnow(),
                },
            )
            _trail(db, app.id, "REJECT", {"comment": comment}, user)
            db.commit()
            app = _get_legacy_application(db, app_id)
            out = _row(db, app, rec, stu)
            out["version"] = new_ver
            return out
        # Legacy application、学生记录、岗位名额、同一 legacy 志愿、审计全部留在同一事务。
        if app.application_type == "POSITION":
            # Historical NULL-campaign rows may have been created before the V3 boundary existed.
            # Revalidate the position itself before the shared assignment path so a legacy approval
            # can never consume/approve a recruitment-campaign volunteer group by association.
            _legacy_position(db, app.position_id)
            student_svc.assign_position_in_tx(
                db, rec, app.position_id, record_expected_version, user=user)
        else:
            record_ver = extract_expected_version({"expectedVersion": record_expected_version})
            if int(rec.version or 0) != record_ver:
                raise AppException("DATA_CONFLICT", "实习学生记录已被其他用户修改，请刷新后重试")
            if app.application_type == "EXEMPTION":
                if rec.position_id or rec.destination_type not in ("NONE", ""):
                    raise AppException("DATA_CONFLICT", "学生已有实习去向，不能直接批准免实习")
                rec.destination_type = "EXEMPTED"
                rec.enterprise_id = None
                rec.position_id = None
                rec.mentor_contact_id = None
                rec.enterprise_name = None
                rec.position_name = None
                rec.enterprise_mentor_name = None
            else:
                rec.destination_type = "SELF_ARRANGED"
                rec.enterprise_name = app.company_name
                rec.position_name = app.position_name
                rec.enterprise_mentor_name = app.enterprise_mentor_name
                rec.intern_start_date = app.internship_start_date
                rec.intern_end_date = app.internship_end_date
            rec.version = record_ver + 1
        new_ver = versioned_update(
            db, InternshipApplication, entity_id=app.id, tenant_id=_tid(),
            expected_version=ver, expected_status="PENDING_REVIEW",
            values={
                "status": "APPROVED",
                "review_comment": comment or None,
                "reviewed_by_name": _op_name(user),
                "reviewed_at": datetime.utcnow(),
            },
        )
        others = db.scalars(select(InternshipApplication).where(
            InternshipApplication.tenant_id == _tid(), InternshipApplication.record_id == app.record_id,
            InternshipApplication.campaign_id.is_(None),
            InternshipApplication.id != app.id, InternshipApplication.status.in_(_ACTIVE),
            InternshipApplication.is_deleted.is_(False))).all()
        for other in others:
            other.status = "CANCELLED"
            other.review_comment = _CANCEL_SIBLING_COMMENT
            other.reviewed_by_name, other.reviewed_at = _op_name(user), datetime.utcnow()
            other.version = int(other.version or 0) + 1
        _trail(db, app.id, "APPROVE", {"applicationType": app.application_type}, user)
        db.commit()
        app = _get_legacy_application(db, app_id)
        rec = tenant_get(db, InternshipRecord, app.record_id, tenant_id=app.tenant_id)
        stu = tenant_get(db, StudentProfile, app.student_id, tenant_id=app.tenant_id)
        out = _row(db, app, rec, stu)
        out["version"] = new_ver
        return out