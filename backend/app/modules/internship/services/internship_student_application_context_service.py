"""学生本人批次化正式实习申请。

该服务是学生小程序和学生 PC 的权威写入口：显式实习记录、真实岗位/附件校验、
行锁、乐观锁和同事务审计。旧无版本移动端写接口不得继续承载生产写操作。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission
from app.models import InternshipApplication
from app.modules.internship.services import internship_application_service as legacy
from app.modules.internship.services.internship_student_context_guard import (
    require_explicit_context,
)
from app.services.db_service import _as_id, _tid, session

_EDITABLE = {"DRAFT", "REJECTED", "WITHDRAWN"}


def _expected(payload: dict, current: int, *, required: bool) -> int:
    raw = (payload or {}).get("expectedVersion", (payload or {}).get("version"))
    if raw is None:
        if required:
            raise AppException("DATA_CONFLICT", "缺少申请版本，请刷新后重试")
        return int(current or 0)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "expectedVersion 必须是整数")
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
            "VALIDATION_ERROR", "applicationType 必须是 POSITION 或 SELF_ARRANGED")
    with session() as db:
        record, student = _student_record(
            db, user, for_write=True, payload=payload)
        if record.status not in ("PREPARING", "READY"):
            raise AppException("DATA_CONFLICT", "当前实习状态不可新增或修改申请")
        if record.position_id or record.destination_type == "SELF_ARRANGED":
            raise AppException("DATA_CONFLICT", "实习去向已落实，不可再新增或修改申请")

        app_id = payload.get("id")
        row = None
        if app_id:
            row = db.scalar(select(InternshipApplication).where(
                InternshipApplication.id == _as_id(app_id),
                InternshipApplication.tenant_id == _tid(),
                InternshipApplication.is_deleted.is_(False),
            ).with_for_update())
            if not row:
                raise AppException("NOT_FOUND", "实习申请不存在")
            if row.record_id != record.id or row.student_id != student.id:
                raise no_permission("只能修改本人的实习申请")
            if row.status not in _EDITABLE:
                raise AppException("DATA_CONFLICT", "当前申请不可修改")
            _expected(payload, row.version, required=True)
            if row.application_type != application_type:
                raise AppException("VALIDATION_ERROR", "申请类型不可变更，请新建申请")
        else:
            volunteer = 0 if application_type == "SELF_ARRANGED" else int(
                payload.get("volunteerNo") or 1)
            if application_type == "SELF_ARRANGED" and volunteer != 0:
                raise AppException("VALIDATION_ERROR", "自主实习志愿序号必须为0")
            if application_type == "POSITION" and volunteer not in (1, 2, 3):
                raise AppException("VALIDATION_ERROR", "岗位志愿顺序只能为1至3")
            row = db.scalar(select(InternshipApplication).where(
                InternshipApplication.tenant_id == _tid(),
                InternshipApplication.record_id == record.id,
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
                batch_id=record.batch_id, application_type=application_type,
                volunteer_no=volunteer, status="DRAFT")
            db.add(row)
            db.flush()

        before = {
            "status": row.status, "version": int(row.version or 0),
            "positionId": str(row.position_id or ""),
            "evidenceFileId": row.evidence_file_id or "",
        }
        row.application_note = str(payload.get("applicationNote") or "").strip() or None
        if application_type == "POSITION":
            position, company = legacy._position(db, payload.get("positionId"))
            duplicate = db.scalar(select(InternshipApplication.id).where(
                InternshipApplication.tenant_id == _tid(),
                InternshipApplication.record_id == record.id,
                InternshipApplication.position_id == position.id,
                InternshipApplication.status.in_(legacy._ACTIVE),
                InternshipApplication.id != row.id,
                InternshipApplication.is_deleted.is_(False),
            ))
            if duplicate:
                raise AppException("DATA_CONFLICT", "同一岗位无需重复申请")
            row.position_id = position.id
            row.company_name = company.name
            row.position_name = position.title
            row.work_address = position.work_location
            row.contact_name = None
            row.contact_phone = None
            row.evidence_file_id = None
        else:
            row.position_id = None
            for field, value in legacy._clean_self_arranged(
                    payload, require_complete=False).items():
                setattr(row, field, value)

        row.status = "DRAFT"
        row.submitted_at = None
        row.reviewed_by_name = None
        row.reviewed_at = None
        row.review_comment = None
        row.version = int(row.version or 0) + 1
        legacy._trail(db, row.id, "SAVE_DRAFT_VERSIONED", {
            "before": before,
            "afterVersion": int(row.version or 0),
            "applicationType": application_type,
            "volunteerNo": int(row.volunteer_no or 0),
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
            InternshipApplication.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise AppException("NOT_FOUND", "实习申请不存在")
        if row.record_id != record.id or row.student_id != student.id:
            raise no_permission("只能提交本人的实习申请")
        _expected(payload, row.version, required=True)
        if row.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "仅草稿申请可提交")
        if len(str(row.application_note or "").strip()) < 5:
            raise AppException("VALIDATION_ERROR", "申请说明不少于5字")
        if row.application_type == "POSITION":
            position, company = legacy._position(db, row.position_id)
            row.company_name = company.name
            row.position_name = position.title
            row.work_address = position.work_location
        else:
            values = legacy._clean_self_arranged({
                "companyName": row.company_name,
                "positionName": row.position_name,
                "workAddress": row.work_address,
                "contactName": row.contact_name,
                "contactPhone": row.contact_phone,
                "evidenceFileId": row.evidence_file_id,
            }, require_complete=True)
            for field, value in values.items():
                setattr(row, field, value)
        row.status = "PENDING_REVIEW"
        row.submitted_at = datetime.utcnow()
        row.version = int(row.version or 0) + 1
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
            InternshipApplication.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise AppException("NOT_FOUND", "实习申请不存在")
        if row.record_id != record.id or row.student_id != student.id:
            raise no_permission("只能撤回本人的实习申请")
        _expected(payload, row.version, required=True)
        if row.status != "PENDING_REVIEW":
            raise AppException("DATA_CONFLICT", "仅待审核申请可撤回")
        row.status = "WITHDRAWN"
        row.version = int(row.version or 0) + 1
        legacy._trail(db, row.id, "WITHDRAW_VERSIONED", {
            "newVersion": int(row.version or 0),
        }, user)
        db.commit()
        return legacy._row(db, row, record, student)
