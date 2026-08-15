"""Enterprise E9 internship-collaboration facade.

Separate from recruitment routes so closed recruitment campaigns do not disable an active
INTERNSHIP_COLLAB grant. The resource scope is always server-derived.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.response import success
from app.modules.internship.dependencies.enterprise_context import (
    EnterprisePrincipal,
    require_enterprise_permission as require_permission,
    resolve_internship_collab_context,
)
from app.modules.internship.services import internship_enterprise_collaboration_service as collab_svc
from app.services.db_service import session

router = APIRouter(prefix="/internship/enterprise-portal", tags=["岗位实习-企业协同端"])


class EnterpriseOnlineEvaluationBody(BaseModel):
    attendanceScore: int = Field(ge=0, le=100)
    skillScore: int = Field(ge=0, le=100)
    attitudeScore: int = Field(ge=0, le=100)
    collaborationScore: int = Field(ge=0, le=100)
    safetyScore: int = Field(ge=0, le=100)
    overallComment: str = Field(min_length=1, max_length=2000)
    recommendHire: bool = False
    expectedVersion: int | None = Field(default=None, ge=0)


@router.get("/internship-students")
def internship_students(
    batchId: int = Query(..., ge=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=100),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=100),
    principal: EnterprisePrincipal = Depends(require_permission("internship.student.view")),
):
    context = resolve_internship_collab_context(principal, batch_id=batchId)
    with session() as db:
        return success(collab_svc.list_students_in_tx(
            db,
            context=context,
            page=page,
            page_size=pageSize,
            status=status,
            keyword=keyword,
        ))


@router.get("/internship-students/{internship_id}")
def internship_student_detail(
    internship_id: int,
    batchId: int = Query(..., ge=1),
    principal: EnterprisePrincipal = Depends(require_permission("internship.student.view")),
):
    context = resolve_internship_collab_context(principal, batch_id=batchId)
    with session() as db:
        return success(collab_svc.get_student_in_tx(db, context=context, internship_id=internship_id))


@router.get("/evaluation-tasks")
def evaluation_tasks(
    batchId: int = Query(..., ge=1),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=100),
    status: str | None = Query(default=None),
    principal: EnterprisePrincipal = Depends(require_permission("internship.eval.enterprise.manage")),
):
    context = resolve_internship_collab_context(principal, batch_id=batchId)
    with session() as db:
        return success(collab_svc.list_evaluation_tasks_in_tx(
            db,
            context=context,
            page=page,
            page_size=pageSize,
            status=status,
        ))


@router.post("/evaluation-tasks/{internship_id}/submit")
def submit_evaluation(
    internship_id: int,
    body: EnterpriseOnlineEvaluationBody,
    batchId: int = Query(..., ge=1),
    principal: EnterprisePrincipal = Depends(require_permission("internship.eval.enterprise.manage")),
):
    context = resolve_internship_collab_context(principal, batch_id=batchId)
    with session() as db:
        result = collab_svc.submit_evaluation_in_tx(
            db,
            context=context,
            internship_id=internship_id,
            payload=body.model_dump(exclude_unset=True),
        )
        db.commit()
        return success(result, message="企业评价已提交学校审核")
