"""Teacher mini-program internship access and batch context.

The teacher mini-program previously used local role constants and opened student
pickers without a batch id. This endpoint provides one server-authoritative
payload for permission-driven quick actions and scoped batch selection.
"""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.permissions import (
    get_effective_access_context,
    require_module,
    require_permission,
)
from app.core.response import success
from app.models import InternshipBatch, InternshipRecord
from app.modules.internship.services.internship_scope import apply_internship_record_scope
from app.services.db_service import _iso, _tid, session

router = APIRouter(
    prefix="/mobile/teacher/internship/context",
    tags=["教师移动端-岗位实习上下文"],
    dependencies=[Depends(require_module("internship"))],
)


def _choose_default_batch(items: list[dict]) -> str:
    running = [x for x in items if x.get("status") == "RUNNING"]
    pool = running or [x for x in items if x.get("status") != "VOIDED"] or items
    return str(pool[0]["id"]) if pool else ""


@router.get("", summary="教师岗位实习权限与批次上下文")
def teacher_internship_context(
    user=Depends(require_permission("internship.dashboard.view")),
):
    with session() as db:
        query = select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False),
            InternshipRecord.batch_id.is_not(None),
        )
        records = db.scalars(
            apply_internship_record_scope(query, user).order_by(InternshipRecord.id.desc())
        ).all()
        counts = Counter(int(x.batch_id) for x in records if x.batch_id)
        batch_ids = list(counts)
        batches = []
        if batch_ids:
            rows = db.scalars(select(InternshipBatch).where(
                InternshipBatch.tenant_id == _tid(),
                InternshipBatch.id.in_(batch_ids),
                InternshipBatch.is_deleted.is_(False),
            ).order_by(
                InternshipBatch.start_date.desc(), InternshipBatch.id.desc()
            )).all()
            batches = [{
                "id": str(x.id),
                "name": x.batch_name,
                "batchNo": x.batch_no,
                "status": x.status,
                "academicYear": x.academic_year or "",
                "term": x.term or "",
                "startDate": _iso(x.start_date),
                "endDate": _iso(x.end_date),
                "studentCount": int(counts.get(int(x.id), 0)),
            } for x in rows]

    access = get_effective_access_context(user)
    return success({
        "roleCode": access.get("roleCode"),
        "permissionPatterns": access.get("permissionPatterns") or [],
        "permissionVersion": access.get("permissionVersion"),
        "moduleAccessHealthy": access.get("moduleAccessHealthy", True),
        "moduleAccessError": access.get("moduleAccessError") or "",
        "batches": batches,
        "defaultBatchId": _choose_default_batch(batches),
    })
