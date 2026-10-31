"""学生本人批次化正式实习申请。

该服务是学生小程序和学生 PC 的旧单申请兼容写入口。招聘季 POSITION 已切换为
InternshipVolunteerGroup + 1/2/3 原子事务，禁止再从这里逐条写入绕过窗口、材料快照和组锁。
自主实习与历史 campaign_id=NULL 岗位继续兼容本服务。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select

from app.core.exceptions import AppException, no_permission
from app.models import EmpCompany, InternshipApplication, InternshipBatch, InternshipPosition, StudentProfile, InternshipEnterpriseCollegeScope
from app.modules.internship.services import internship_application_service as legacy
from app.modules.internship.services.internship_student_context_guard import (
    require_explicit_context,
)
from app.services.db_service import _as_id, _tid, session

_EDITABLE = {"DRAFT", "REJECTED", "WITHDRAWN"}


def list_positions(user: dict, *, batch_id, internship_id, page=1, page_size=20, keyword="") -> dict:
    """The student's scoped, non-campaign first-placement catalog; counts precede pagination."""
    from app.modules.internship.services.internship_record_resolver import _is_active_record
    from app.modules.internship.services.internship_position_rights import evaluate_position_publishability
    from app.modules.internship.services.internship_student_position_eligibility_service import _major_sql_predicate

    with session() as db:
        record, student, bid = require_explicit_context(db, user,
            {"batchId": batch_id, "internshipId": internship_id}, for_write=False)
        batch = db.get(InternshipBatch, bid)
        org_query, org = legacy._application_org_query(select(StudentProfile).where(
            StudentProfile.id == student.id, StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)))
        college_id, major_name = db.execute(org_query.with_only_columns(org['collegeId'], org['majorName'])).one()
        scopes = select(InternshipEnterpriseCollegeScope.company_id).where(
            InternshipEnterpriseCollegeScope.tenant_id == _tid(), InternshipEnterpriseCollegeScope.is_deleted.is_(False))
        allowed = scopes.where(InternshipEnterpriseCollegeScope.college_id == college_id) if college_id else scopes.where(False)
        query = select(InternshipPosition, EmpCompany).join(EmpCompany, and_(
            EmpCompany.id == InternshipPosition.company_id, EmpCompany.tenant_id == InternshipPosition.tenant_id)).where(
            InternshipPosition.tenant_id == _tid(), InternshipPosition.batch_id == bid,
            InternshipPosition.campaign_id.is_(None), InternshipPosition.is_deleted.is_(False),
            InternshipPosition.status == 'PUBLISHED', InternshipPosition.allocated_count < InternshipPosition.headcount,
            EmpCompany.tenant_id == _tid(), EmpCompany.is_deleted.is_(False), EmpCompany.coop_status == 'ACTIVE',
            EmpCompany.blacklist.is_(False),
            or_(EmpCompany.access_valid_until.is_(None), EmpCompany.access_valid_until >= datetime.utcnow()),
            or_(~EmpCompany.id.in_(scopes), EmpCompany.id.in_(allowed)), _major_sql_predicate(major_name or ''))
        term = str(keyword or '').strip()
        if term:
            query = query.where(or_(InternshipPosition.title.contains(term, autoescape=True),
                EmpCompany.name.contains(term, autoescape=True), InternshipPosition.work_location.contains(term, autoescape=True)))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        current_page, size = max(1, int(page)), max(1, min(50, int(page_size)))
        rows = db.execute(query.order_by(InternshipPosition.id).offset((current_page-1)*size).limit(size)).all()
        can_apply = (_is_active_record(record, batch) and record.status in ('PREPARING', 'READY')
                     and not record.position_id and record.destination_type not in ('ASSIGNED', 'SELF_ARRANGED', 'EXEMPTED'))
        items = []
        for position, company in rows:
            rights = evaluate_position_publishability(position, company, batch, student, operation='APPLY', db=db, record=record)
            items.append({'id': str(position.id), 'title': position.title, 'companyName': company.name,
                'workLocation': position.work_location or '', 'remaining': max(0, position.headcount-position.allocated_count),
                'canSelect': bool(can_apply and rights['passed']),
                'selectionReason': ('当前实习记录仅可查看岗位' if not can_apply else '；'.join(
                    item.get('reason') or item.get('label') or '请联系学校核验' for item in rights['blockers']+rights['unknowns']))})
        return {'items': items, 'total': total, 'page': current_page, 'pageSize': size,
                'hasMore': current_page*size < total, 'batchId': str(bid), 'internshipId': str(record.id)}


def _expected(payload: dict, current: int, *, required: bool) -> int:
    raw = (payload or {}).get("expectedVersion", (payload or {}).get("version"))
    if raw is None:
        if required:
            raise AppException("DATA_CONFLICT", "缺少申请版本，请刷新后重试")
        return int(current or 0)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "版本必须是整数")
    if value != int(current or 0):
        raise AppException("DATA_CONFLICT", "实习申请已被其他用户修改，请刷新后重试")
    return value


def _student_record(db, user, *, for_write: bool, payload: dict):
    if payload:
        record, student, _batch_id = require_explicit_context(
            db, user, payload, for_write=for_write)
        return record, student
    return legacy._record_for_student(
        db, (user or {}).get("studentNo"), for_write=for_write)


def _reject_campaign_position(position) -> None:
    if getattr(position, "campaign_id", None):
        raise AppException(
            "DATA_CONFLICT",
            "招聘季岗位必须通过三志愿原子接口保存/提交，不能逐条写入正式申请",
            http_status=409,
        )


def list_my(user: dict, *, batch_id=None, internship_id=None) -> list[dict]:
    with session() as db:
        payload = (
            {"batchId": batch_id, "internshipId": internship_id}
            if batch_id is not None or internship_id is not None else {}
        )
        record, student = _student_record(
            db, user, for_write=False, payload=payload)
        rows = db.scalars(select(InternshipApplication).where(
            InternshipApplication.tenant_id == _tid(),
            InternshipApplication.record_id == record.id,
            InternshipApplication.student_id == student.id,
            or_(InternshipApplication.batch_id.is_(None), InternshipApplication.batch_id == record.batch_id),
            InternshipApplication.campaign_id.is_(None),
            InternshipApplication.is_deleted.is_(False),
        ).order_by(
            InternshipApplication.volunteer_no.asc(),
            InternshipApplication.id.desc(),
        )).all()
        return [legacy._row(db, row, record, student) for row in rows]


def save(user: dict, body: dict) -> dict:
    payload = body or {}
    application_type = str(payload.get("applicationType") or "").upper()
    if application_type not in legacy.TYPE_LABEL:
        raise AppException(
            "VALIDATION_ERROR", "applicationType 必须是 POSITION、SELF_ARRANGED 或 EXEMPTION")
    with session() as db:
        record, student = _student_record(
            db, user, for_write=True, payload=payload)
        if record.status not in ("PREPARING", "READY"):
            raise AppException("DATA_CONFLICT", "当前实习状态不可新增或修改申请")
        if record.position_id or record.destination_type in ("SELF_ARRANGED", "EXEMPTED"):
            raise AppException("DATA_CONFLICT", "实习去向已落实，不可再新增或修改申请")

        app_id = payload.get("id")
        row = None
        if app_id:
            row = db.scalar(select(InternshipApplication).where(
                InternshipApplication.id == _as_id(app_id),
                InternshipApplication.tenant_id == _tid(),
                InternshipApplication.campaign_id.is_(None),
                InternshipApplication.is_deleted.is_(False),
            ).with_for_update())
            if not row:
                # Do not reveal whether the supplied id belongs to a campaign-scoped V3 row.
                raise AppException("NOT_FOUND", "实习申请不存在")
            if not legacy._application_matches_record(row, record, student):
                raise no_permission("只能修改本人的实习申请")
            if row.status not in _EDITABLE:
                raise AppException("DATA_CONFLICT", "当前申请不可修改")
            _expected(payload, row.version, required=True)
            if row.application_type != application_type:
                raise AppException("VALIDATION_ERROR", "申请类型不可变更，请新建申请")
        else:
            if application_type == "SELF_ARRANGED":
                volunteer = 0
            elif application_type == "EXEMPTION":
                volunteer = -1
            else:
                volunteer = int(payload.get("volunteerNo") or 1)
            if application_type == "POSITION" and volunteer not in (1, 2, 3):
                raise AppException("VALIDATION_ERROR", "岗位志愿顺序只能为1至3")
            row = db.scalar(select(InternshipApplication).where(
                InternshipApplication.tenant_id == _tid(),
                InternshipApplication.record_id == record.id,
                InternshipApplication.campaign_id.is_(None),
                InternshipApplication.volunteer_no == volunteer,
                InternshipApplication.is_deleted.is_(False),
            ).with_for_update())
            if row:
                if row.status not in _EDITABLE:
                    raise AppException("DATA_CONFLICT", "该志愿已有进行中的申请")
                raise AppException(
                    "DATA_CONFLICT", "检测到已有可编辑申请，请刷新页面后继续修改")
            row = InternshipApplication(
                tenant_id=_tid(), record_id=record.id, student_id=student.id,
                batch_id=record.batch_id, campaign_id=None, application_type=application_type,
                volunteer_no=volunteer, status="DRAFT")
            db.add(row)
            db.flush()

        before = {
            "status": row.status, "version": int(row.version or 0),
            "positionId": str(row.position_id or ""),
            "evidenceFileId": row.evidence_file_id or "",
            "companyName": row.company_name or "",
            "companyCreditCode": row.company_credit_code or "",
        }
        before_company_identity = (row.company_name or "", row.company_credit_code or "")
        row.application_note = str(payload.get("applicationNote") or "").strip() or None
        if application_type == "POSITION":
            position, company = legacy._position(db, payload.get("positionId"))
            _reject_campaign_position(position)
            duplicate = db.scalar(select(InternshipApplication.id).where(
                InternshipApplication.tenant_id == _tid(),
                InternshipApplication.record_id == record.id,
                InternshipApplication.campaign_id.is_(None),
                InternshipApplication.position_id == position.id,
                InternshipApplication.status.in_(legacy._ACTIVE),
                InternshipApplication.id != row.id,
                InternshipApplication.is_deleted.is_(False),
            ))
            if duplicate:
                raise AppException("DATA_CONFLICT", "同一岗位无需重复申请")
            row.position_id = position.id
            legacy._apply_position_snapshot(row, position, company)
            row.contact_phone = None
            row.evidence_file_id = None
        elif application_type == "EXEMPTION":
            if record.position_id:
                raise AppException("DATA_CONFLICT", "已分配校内岗位，请通过正式变更流程处理免实习")
            row.position_id = None
            legacy._clear_exemption_company_snapshot(row)
            for field, value in legacy._clean_exemption(
                    payload, require_complete=False).items():
                setattr(row, field, value)
        else:
            row.position_id = None
            for field, value in legacy._clean_self_arranged(
                    payload, require_complete=False).items():
                setattr(row, field, value)
            if before_company_identity != (row.company_name or "", row.company_credit_code or ""):
                row.registry_verification_status = "UNVERIFIED"
                row.registry_verification_provider = None
                row.registry_reference = None
                row.registry_verified_at = None

        row.status = "DRAFT"
        row.submitted_at = None
        row.reviewed_by_name = None
        row.reviewed_at = None
        row.review_comment = None
        row.version = int(row.version or 0) + 1
        db.flush()
        legacy._bind_application_files(db, row, user)
        legacy._trail(db, row.id, "SAVE_DRAFT_VERSIONED", {
            "before": before,
            "afterVersion": int(row.version or 0),
            "applicationType": application_type,
            "volunteerNo": int(row.volunteer_no or 0),
            "companyCreditCode": row.company_credit_code or "",
            "registryStatus": row.registry_verification_status or "UNVERIFIED",
        }, user)
        db.commit()
        return legacy._row(db, row, record, student)


def submit(user: dict, app_id, body: dict) -> dict:
    payload = body or {}
    with session() as db:
        record, student = _student_record(
            db, user, for_write=True, payload=payload)
        row = db.scalar(select(InternshipApplication).where(
            InternshipApplication.id == _as_id(app_id),
            InternshipApplication.tenant_id == _tid(),
            InternshipApplication.campaign_id.is_(None),
            InternshipApplication.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise AppException("NOT_FOUND", "实习申请不存在")
        if not legacy._application_matches_record(row, record, student):
            raise no_permission("只能提交本人的实习申请")
        _expected(payload, row.version, required=True)
        if row.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "仅草稿申请可提交")
        if row.application_type != "EXEMPTION" and len(str(row.application_note or "").strip()) < 5:
            raise AppException("VALIDATION_ERROR", "申请说明不少于5字")
        if row.application_type == "POSITION":
            position, company = legacy._position(db, row.position_id)
            _reject_campaign_position(position)
            legacy._apply_position_snapshot(row, position, company)
        elif row.application_type == "EXEMPTION":
            values = legacy._clean_exemption(
                legacy._snapshot_body(row), require_complete=True)
            for field, value in values.items():
                setattr(row, field, value)
        else:
            values = legacy._clean_self_arranged(
                legacy._snapshot_body(row), require_complete=True)
            for field, value in values.items():
                setattr(row, field, value)
        row.status = "PENDING_REVIEW"
        row.submitted_at = datetime.utcnow()
        row.version = int(row.version or 0) + 1
        legacy._bind_application_files(db, row, user)
        legacy._trail(db, row.id, "SUBMIT_VERSIONED", {
            "applicationType": row.application_type,
            "newVersion": int(row.version or 0),
        }, user)
        db.commit()
        return legacy._row(db, row, record, student)


def withdraw(user: dict, app_id, body: dict) -> dict:
    payload = body or {}
    with session() as db:
        record, student = _student_record(
            db, user, for_write=True, payload=payload)
        row = db.scalar(select(InternshipApplication).where(
            InternshipApplication.id == _as_id(app_id),
            InternshipApplication.tenant_id == _tid(),
            InternshipApplication.campaign_id.is_(None),
            InternshipApplication.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise AppException("NOT_FOUND", "实习申请不存在")
        if not legacy._application_matches_record(row, record, student):
            raise no_permission("只能撤回本人的实习申请")
        _expected(payload, row.version, required=True)
        if row.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅待审核申请可撤回")
        if row.application_type == "POSITION" and row.position_id:
            position, _company = legacy._position(db, row.position_id)
            _reject_campaign_position(position)
        row.status = "WITHDRAWN"
        row.version = int(row.version or 0) + 1
        legacy._trail(db, row.id, "WITHDRAW_VERSIONED", {
            "newVersion": int(row.version or 0),
        }, user)
        db.commit()
        return legacy._row(db, row, record, student)
