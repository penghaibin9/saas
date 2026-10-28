"""学生调岗、换单位与退岗的批次化权威写入口。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, no_permission, not_found
from app.models import EmpCompany, InternshipBatch, InternshipChangeRequest, InternshipPosition
from app.modules.internship.services import internship_change_service as legacy
from app.modules.internship.services.internship_student_context_guard import (
    require_expected_version,
    require_explicit_context,
)
from app.services.db_service import _as_id, _tid, session
from app.modules.internship.services import internship_todo_helper as ix_todo
from app.modules.internship.services.internship_version import versioned_update
from app.modules.internship.services.internship_record_resolver import _is_active_record


def list_my(user: dict, *, batch_id, internship_id, page=1, page_size=20) -> dict:
    with session() as db:
        record, student, selected_batch_id = require_explicit_context(
            db,
            user,
            {"batchId": batch_id, "internshipId": internship_id},
            for_write=False,
        )
        query = select(InternshipChangeRequest).where(
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.internship_id == record.id,
            InternshipChangeRequest.student_id == student.id,
            InternshipChangeRequest.is_deleted.is_(False),
        )
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        current_page, size = max(1, int(page)), max(1, min(50, int(page_size)))
        rows = db.scalars(query.order_by(InternshipChangeRequest.id.desc())
                          .offset((current_page - 1) * size).limit(size)).all()
        return {
            "items": [legacy._row(row, record, student) for row in rows],
            "total": total, "page": current_page, "pageSize": size,
            "hasMore": current_page * size < total,
            "batchId": str(selected_batch_id),
            "internshipId": str(record.id),
        }


def list_target_positions(user: dict, *, batch_id, internship_id, keyword="",
                          change_type="CHANGE_POSITION", page=1, page_size=20) -> dict:
    """Canonical change candidates; unlike first placement catalog, assigned students may read it."""
    selected_type = str(change_type or "CHANGE_POSITION").upper()
    if selected_type not in ("CHANGE_POSITION", "CHANGE_ENTERPRISE"):
        raise AppException("VALIDATION_ERROR", "仅换岗或换单位可选择目标岗位")
    with session() as db:
        record, student, selected_batch_id = require_explicit_context(
            db, user, {"batchId": batch_id, "internshipId": internship_id}, for_write=False)
        batch = db.get(InternshipBatch, selected_batch_id)
        writable = _is_active_record(record, batch)
        query = select(InternshipPosition, EmpCompany).join(
            EmpCompany,
            (EmpCompany.id == InternshipPosition.company_id)
            & (EmpCompany.tenant_id == InternshipPosition.tenant_id),
        ).where(
            InternshipPosition.tenant_id == _tid(),
            InternshipPosition.batch_id == selected_batch_id,
            InternshipPosition.status == "PUBLISHED",
            InternshipPosition.allocated_count < InternshipPosition.headcount,
            InternshipPosition.is_deleted.is_(False),
            EmpCompany.tenant_id == _tid(),
            EmpCompany.coop_status == "ACTIVE",
            EmpCompany.blacklist.is_(False),
            EmpCompany.is_deleted.is_(False),
        )
        if record.position_id:
            query = query.where(InternshipPosition.id != record.position_id)
        if selected_type == "CHANGE_ENTERPRISE" and record.enterprise_id:
            query = query.where(InternshipPosition.company_id != record.enterprise_id)
        term = str(keyword or "").strip()
        if term:
            like = f"%{term}%"
            query = query.where(or_(
                InternshipPosition.title.like(like),
                InternshipPosition.work_location.like(like),
                EmpCompany.name.like(like),
            ))
        current_page = max(1, int(page or 1))
        size = max(1, min(50, int(page_size or 20)))
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = db.execute(query.order_by(
            EmpCompany.name.asc(), InternshipPosition.title.asc(), InternshipPosition.id.asc()
        ).offset((current_page - 1) * size).limit(size)).all()
        from app.modules.internship.services.internship_position_rights import evaluate_position_publishability
        eligible = []
        for position, company in rows:
            rights = evaluate_position_publishability(
                position, company, batch, student, operation="CHANGE_APPLY", db=db)
            remaining = max(0, int(position.headcount or 0) - int(position.allocated_count or 0))
            eligible.append({
                "id": str(position.id), "positionId": str(position.id),
                "title": position.title, "companyId": str(company.id),
                "companyName": company.name, "workLocation": position.work_location or "",
                "headcount": int(position.headcount or 0),
                "allocatedCount": int(position.allocated_count or 0),
                "remaining": remaining, "status": position.status,
                "canSelect": bool(writable and rights["passed"]),
                "selectionReason": "当前实习记录或批次已结束，仅可查看" if not writable else
                    "；".join(item.get("reason") or item.get("label") or "需学校核验"
                    for item in [*(rights.get("blockers") or []), *(rights.get("unknowns") or [])]),
            })
        return {
            "items": eligible, "total": total,
            "page": current_page, "pageSize": size,
            "hasMore": current_page * size < total,
            "batchId": str(selected_batch_id), "internshipId": str(record.id),
            "changeType": selected_type,
        }


def _application_values(db, record, student, payload):
    change_type = str(payload.get("changeType") or "").upper()
    if change_type not in legacy.TYPE_LABEL:
        raise AppException("VALIDATION_ERROR", "请选择有效的变更类型")
    reason = str(payload.get("reason") or "").strip()
    if not 5 <= len(reason) <= 500:
        raise AppException("VALIDATION_ERROR", "变更原因须填写 5 至 500 字")
    if change_type in ("CHANGE_POSITION", "CHANGE_ENTERPRISE") and not payload.get("targetPositionId"):
        label = "换单位" if change_type == "CHANGE_ENTERPRISE" else "换岗"
        raise AppException("VALIDATION_ERROR", f"{label}必须选择目标岗位")
    target_position = target_company = None
    if change_type in ("CHANGE_POSITION", "CHANGE_ENTERPRISE"):
        target_position, target_company = legacy.validate_target_position(
            db, record, student, payload.get("targetPositionId"), change_type=change_type)
    enterprise_name = str(payload.get("targetEnterpriseName") or "").strip()
    position_name = str(payload.get("targetPositionName") or "").strip()
    if change_type == "SELF_ARRANGED" and (not 2 <= len(enterprise_name) <= 200
                                          or not 2 <= len(position_name) <= 100):
        raise AppException("VALIDATION_ERROR", "请填写完整的自主实习企业与岗位名称")
    return {
        "change_type": change_type, "reason": reason,
        "target_enterprise_id": target_company.id if target_company else None,
        "target_position_id": target_position.id if target_position else None,
        "target_enterprise_name": target_company.name if target_company else (
            enterprise_name if change_type == "SELF_ARRANGED" else None),
        "target_position_name": target_position.title if target_position else (
            position_name if change_type == "SELF_ARRANGED" else None),
        "record_version_snapshot": int(record.version or 0),
        "status": "PENDING",
    }


def _commit(db):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uk_ix_change_active_pending" not in str(exc.orig):
            raise
        raise AppException("DATA_CONFLICT", legacy._DUP_PENDING_MSG, http_status=409) from exc


def apply(user: dict, body: dict) -> dict:
    payload = body or {}
    require_expected_version(payload.get("expectedVersion"), 0, entity_name="变更申请上下文")

    with session() as db:
        record, student, _batch_id = require_explicit_context(
            db, user, payload, for_write=True)
        pending = db.scalar(select(InternshipChangeRequest).where(
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.internship_id == record.id,
            InternshipChangeRequest.status == "PENDING",
            InternshipChangeRequest.is_deleted.is_(False),
        ).with_for_update())
        if pending:
            raise AppException(
                "DATA_CONFLICT", "已有待审核的变更申请，请等待处理或撤回", http_status=409)

        row = InternshipChangeRequest(
            tenant_id=_tid(),
            internship_id=record.id,
            student_id=student.id,
            **_application_values(db, record, student, payload),
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            if "uk_ix_change_active_pending" not in str(exc.orig):
                raise
            raise AppException("DATA_CONFLICT", legacy._DUP_PENDING_MSG, http_status=409) from exc
        legacy._trail(
            db,
            row.id,
            "APPLY_VERSIONED",
            {
                "changeType": row.change_type,
                "batchId": str(record.batch_id or ""),
                "internshipId": str(record.id),
                "expectedVersion": 0,
                "reason": row.reason,
                "targetEnterpriseId": str(row.target_enterprise_id or ""),
                "targetPositionId": str(row.target_position_id or ""),
                "targetEnterpriseName": row.target_enterprise_name or "",
                "targetPositionName": row.target_position_name or "",
                "recordVersionSnapshot": row.record_version_snapshot,
            },
            operator=legacy._op_name(user),
        )
        ix_todo.push_change_todo(db, row, record)
        _commit(db)
        return legacy._row(row, record, student)


def resubmit(user: dict, change_id, body: dict) -> dict:
    payload = body or {}
    with session() as db:
        record, student, _batch_id = require_explicit_context(db, user, payload, for_write=True)
        row = db.scalar(select(InternshipChangeRequest).where(
            InternshipChangeRequest.id == _as_id(change_id),
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise not_found("变更申请不存在")
        if row.internship_id != record.id or row.student_id != student.id:
            raise no_permission("只能补正本人当前批次的变更申请")
        require_expected_version(payload.get("expectedVersion"), row.version, entity_name="变更申请")
        if row.status != "REJECTED":
            raise AppException("DATA_CONFLICT", "仅退回的申请可在原单补正重交", http_status=409)
        if str(payload.get("changeType") or "").upper() != row.change_type:
            raise AppException("VALIDATION_ERROR", "原单补正须保留原变更类型")
        pending = db.scalar(select(InternshipChangeRequest.id).where(
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.internship_id == record.id,
            InternshipChangeRequest.status == "PENDING",
            InternshipChangeRequest.is_deleted.is_(False),
        ).with_for_update())
        if pending:
            raise AppException("DATA_CONFLICT", legacy._DUP_PENDING_MSG, http_status=409)
        before = {"reason": row.reason, "reviewComment": row.review_comment or "",
                  "targetPositionId": str(row.target_position_id or ""),
                  "targetEnterpriseId": str(row.target_enterprise_id or ""),
                  "targetEnterpriseName": row.target_enterprise_name or "",
                  "targetPositionName": row.target_position_name or "",
                  "recordVersionSnapshot": int(row.record_version_snapshot or 0),
                  "version": int(row.version or 0)}
        values = _application_values(db, record, student, payload)
        try:
            new_version = versioned_update(db, InternshipChangeRequest, entity_id=row.id,
                tenant_id=_tid(), expected_version=payload.get("expectedVersion"),
                expected_status="REJECTED", values={**values, "review_comment": None,
                    "reviewed_by_name": None, "reviewed_at": None})
        except IntegrityError as exc:
            db.rollback()
            if "uk_ix_change_active_pending" not in str(exc.orig):
                raise
            raise AppException("DATA_CONFLICT", legacy._DUP_PENDING_MSG, http_status=409) from exc
        legacy._trail(db, row.id, "RESUBMIT_VERSIONED", {
            "before": before, "reason": values["reason"], "newVersion": new_version,
            "batchId": str(record.batch_id), "internshipId": str(record.id),
            "recordVersionSnapshot": values["record_version_snapshot"],
            "targetPositionId": str(values["target_position_id"] or ""),
            "targetEnterpriseId": str(values["target_enterprise_id"] or ""),
            "targetEnterpriseName": values["target_enterprise_name"] or "",
            "targetPositionName": values["target_position_name"] or "",
        }, operator=legacy._op_name(user))
        # 复用原待办，受理教师发生变化时先关闭旧受理人的待办。
        ix_todo.todo_done(db, biz_id=row.id, todo_type=ix_todo.change_todo_type(row))
        ix_todo.push_change_todo(db, row, record)
        _commit(db)
        return legacy._row(row, record, student)


def withdraw(user: dict, change_id, body: dict) -> dict:
    payload = body or {}
    with session() as db:
        record, student, _batch_id = require_explicit_context(
            db, user, payload, for_write=True)
        row = db.scalar(select(InternshipChangeRequest).where(
            InternshipChangeRequest.id == _as_id(change_id),
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.is_deleted.is_(False),
        ).with_for_update())
        if not row:
            raise not_found("变更申请不存在")
        if row.internship_id != record.id or row.student_id != student.id:
            raise no_permission("只能撤回本人当前批次的变更申请")
        require_expected_version(
            payload.get("expectedVersion"), row.version, entity_name="变更申请")
        if row.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审核申请可撤回", http_status=409)
        new_version = versioned_update(db, InternshipChangeRequest, entity_id=row.id,
            tenant_id=_tid(), expected_version=payload.get("expectedVersion"),
            expected_status="PENDING", values={"status": "WITHDRAWN"})
        legacy._trail(
            db,
            row.id,
            "WITHDRAW_VERSIONED",
            {
                "batchId": str(record.batch_id or ""),
                "internshipId": str(record.id),
                "newVersion": new_version,
            },
            operator=legacy._op_name(user),
        )
        ix_todo.todo_done(db, biz_id=row.id, todo_type=ix_todo.change_todo_type(row))
        db.commit()
        return {
            "id": str(row.id),
            "status": row.status,
            "statusLabel": legacy.STATUS_LABEL.get(row.status, row.status),
            "version": int(row.version or 0),
        }
