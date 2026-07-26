"""教师微信小程序毕业设计批次上下文与分页门禁。

本 Router 必须注册在历史 mobile 聚合 Router 之前：
- 所有列表明确绑定 batchId，并提供 page/pageSize；
- 所有详情/写操作在调用既有稳定身份 Service 前再次校验记录所属批次；
- 不复制状态机，真正写入仍复用 mobile_teacher_service / 毕设域 Service。
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.core.response import success
from app.core.security import get_current_user
from app.models import (
    GraduationBatch,
    GraduationFinal,
    GraduationProposal,
    GraduationReview,
    GraduationStudent,
    GraduationTopicChangeRequest,
    GraduationTopicChoice,
)
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids
from app.services import mobile_teacher_service as tea
from app.services.db_service import _iso, _tid, session

router = APIRouter(prefix="/mobile/teacher/graduation", tags=["教师移动端-毕业设计批次上下文"])


def _page(page: int, page_size: int) -> tuple[int, int]:
    return max(1, int(page or 1)), min(100, max(1, int(page_size or 20)))


def _require_batch(batch_id: int | None) -> int:
    if not batch_id:
        raise AppException("VALIDATION_ERROR", "请先选择毕业设计批次")
    return int(batch_id)


def _student(db, gd_student_id: Any, batch_id: int) -> GraduationStudent:
    try:
        sid = int(gd_student_id)
    except (TypeError, ValueError):
        raise not_found("毕设学生不存在") from None
    row = db.scalars(select(GraduationStudent).where(
        GraduationStudent.id == sid,
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.batch_id == int(batch_id),
        GraduationStudent.is_deleted.is_(False),
    )).first()
    if not row:
        raise AppException("DATA_CONFLICT", "该记录不属于当前毕业设计批次，请刷新批次上下文")
    return row


def _student_id_from_row(row: dict) -> str:
    return str(row.get("gdStudentId") or row.get("projectId") or row.get("studentId") or row.get("id") or "")


def _filter_rows(rows: list | None, batch_id: int, *, page: int = 1, page_size: int = 20) -> dict:
    page, page_size = _page(page, page_size)
    values = []
    with session() as db:
        for raw in rows or []:
            row = raw if isinstance(raw, dict) else {}
            sid = _student_id_from_row(row)
            if not sid.isdigit():
                continue
            found = db.scalars(select(GraduationStudent.id).where(
                GraduationStudent.id == int(sid),
                GraduationStudent.tenant_id == _tid(),
                GraduationStudent.batch_id == int(batch_id),
                GraduationStudent.is_deleted.is_(False),
            ).limit(1)).first()
            if found is not None:
                values.append(row)
    total = len(values)
    start = (page - 1) * page_size
    items = values[start:start + page_size]
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasMore": start + len(items) < total,
    }


def _material_student(model, record_id: str, batch_id: int) -> GraduationStudent:
    with session() as db:
        try:
            rid = int(record_id)
        except (TypeError, ValueError):
            raise not_found("毕业设计材料不存在") from None
        record = db.scalars(select(model).where(
            model.id == rid,
            model.tenant_id == _tid(),
            model.is_deleted.is_(False),
        )).first()
        if not record:
            raise not_found("毕业设计材料不存在")
        return _student(db, record.gd_student_id, batch_id)


def _review_student(review_id: str, batch_id: int) -> GraduationStudent:
    with session() as db:
        row = db.scalars(select(GraduationReview).where(
            GraduationReview.id == int(review_id),
            GraduationReview.tenant_id == _tid(),
            GraduationReview.is_deleted.is_(False),
        )).first()
        if not row:
            raise not_found("评阅任务不存在")
        return _student(db, row.gd_student_id, batch_id)


def _choice_student(choice_id: str, batch_id: int) -> GraduationStudent:
    with session() as db:
        row = db.scalars(select(GraduationTopicChoice).where(
            GraduationTopicChoice.id == int(choice_id),
            GraduationTopicChoice.tenant_id == _tid(),
            GraduationTopicChoice.is_deleted.is_(False),
        )).first()
        if not row:
            raise not_found("志愿不存在")
        return _student(db, row.gd_student_id, batch_id)


def _change_student(request_id: str, batch_id: int) -> GraduationStudent:
    with session() as db:
        row = db.scalars(select(GraduationTopicChangeRequest).where(
            GraduationTopicChangeRequest.id == int(request_id),
            GraduationTopicChangeRequest.tenant_id == _tid(),
            GraduationTopicChangeRequest.is_deleted.is_(False),
        )).first()
        if not row:
            raise not_found("变更申请不存在")
        return _student(db, row.gd_student_id, batch_id)


def _paged_service(fn: Callable, user: dict, batch_id: int, page: int, page_size: int) -> dict:
    return _filter_rows(fn(user), batch_id, page=page, page_size=page_size)


@router.get("/batches", summary="教师·可处理的毕业设计批次")
def teacher_graduation_batches(user=Depends(get_current_user)):
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        if not scope_ids:
            return success({"items": [], "selectedBatchId": None})
        batch_ids = [int(x) for x in db.scalars(select(GraduationStudent.batch_id).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.id.in_(scope_ids),
            GraduationStudent.batch_id.is_not(None),
            GraduationStudent.is_deleted.is_(False),
        ).distinct()).all() if x]
        rows = db.scalars(select(GraduationBatch).where(
            GraduationBatch.tenant_id == _tid(),
            GraduationBatch.id.in_(batch_ids or [-1]),
            GraduationBatch.is_deleted.is_(False),
            GraduationBatch.status.in_(("DRAFT", "RUNNING", "CLOSED")),
        ).order_by(GraduationBatch.status == "RUNNING" desc(), GraduationBatch.id.desc())).all()
        items = [{
            "id": str(row.id),
            "batchNo": row.batch_no,
            "batchName": row.batch_name,
            "status": row.status,
            "academicYear": row.academic_year or "",
            "gradeYear": row.grade_year or "",
            "startDate": _iso(row.start_date) if row.start_date else "",
            "endDate": _iso(row.end_date) if row.end_date else "",
        } for row in rows]
        selected = next((item["id"] for item in items if item["status"] == "RUNNING"), items[0]["id"] if items else None)
        return success({"items": items, "selectedBatchId": selected})


@router.get("", summary="教师·毕业设计工作台（当前批次分页）")
def teacher_graduation(
    batchId: int = Query(..., ge=1), page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100), user=Depends(get_current_user),
):
    batch_id = _require_batch(batchId)
    raw = tea.graduation(user) or {}
    students = _filter_rows(raw.get("students") or [], batch_id, page=page, page_size=pageSize)
    proposals = _filter_rows(raw.get("reviewDetail") or [], batch_id, page=page, page_size=pageSize)
    finals = _filter_rows(raw.get("finalDetail") or [], batch_id, page=page, page_size=pageSize)
    return success({
        "batchId": str(batch_id),
        "students": students["items"], "studentTotal": students["total"],
        "reviewDetail": proposals["items"], "proposalTotal": proposals["total"],
        "finalDetail": finals["items"], "finalTotal": finals["total"],
        "page": students["page"], "pageSize": students["pageSize"],
        "hasMore": students["hasMore"] or proposals["hasMore"] or finals["hasMore"],
        "hasData": bool(students["total"] or proposals["total"] or finals["total"]),
    })


@router.get("/my-students", summary="过程指导·本人指导学生（当前批次分页）")
def teacher_graduation_my_students(
    batchId: int = Query(..., ge=1), page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100), user=Depends(get_current_user),
):
    return success(_paged_service(tea.graduation_my_students, user, batchId, page, pageSize))


@router.get("/proposal/{proposal_id}")
def teacher_proposal_detail(proposal_id: str, batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    _material_student(GraduationProposal, proposal_id, batchId)
    return success(tea.proposal_detail(user, proposal_id))


@router.post("/proposal/{proposal_id}/review")
def teacher_proposal_review(proposal_id: str, body: dict = Body(...), batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    _material_student(GraduationProposal, proposal_id, batchId)
    return success(tea.proposal_review(user, proposal_id, str(body.get("action") or "").upper(), body.get("comment") or ""), message="批阅完成")


@router.get("/final/{final_id}")
def teacher_final_detail(final_id: str, batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    _material_student(GraduationFinal, final_id, batchId)
    return success(tea.final_detail(user, final_id))


@router.post("/final/{final_id}/review")
def teacher_final_review(final_id: str, body: dict = Body(...), batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    _material_student(GraduationFinal, final_id, batchId)
    return success(tea.final_review(user, final_id, str(body.get("action") or "").upper(), body.get("comment") or ""), message="批阅完成")


@router.get("/midterm/queue")
def teacher_midterm_queue(batchId: int = Query(..., ge=1), page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), user=Depends(get_current_user)):
    return success(_paged_service(tea.graduation_midterm_queue, user, batchId, page, pageSize))


@router.get("/midterm/{gd_student_id}")
def teacher_midterm_detail(gd_student_id: str, batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    with session() as db: _student(db, gd_student_id, batchId)
    return success(tea.graduation_midterm_detail(user, gd_student_id))


@router.post("/midterm/{gd_student_id}/check")
def teacher_midterm_check(gd_student_id: str, body: dict = Body(...), batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    with session() as db: _student(db, gd_student_id, batchId)
    return success(tea.graduation_midterm_check(user, gd_student_id, body.get("conclusion") or "", body.get("comment") or "", body.get("rectifyDeadline")), message="已提交中期结论")


@router.post("/midterm/{gd_student_id}/rectify-review")
def teacher_midterm_rectify_review(gd_student_id: str, body: dict = Body(...), batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    with session() as db: _student(db, gd_student_id, batchId)
    return success(tea.graduation_midterm_rectify_review(user, gd_student_id, body.get("action") or "", body.get("comment") or ""), message="复核完成")


@router.get("/reviews/my")
def teacher_reviews_my(batchId: int = Query(..., ge=1), page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), user=Depends(get_current_user)):
    return success(_paged_service(tea.graduation_my_reviews, user, batchId, page, pageSize))


@router.post("/review/{review_id}/submit")
def teacher_review_submit(review_id: str, body: dict = Body(...), batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    _review_student(review_id, batchId)
    return success(tea.graduation_review_submit(user, review_id, body.get("score"), body.get("opinion") or ""), message="评阅已提交")


@router.get("/defense/arrangements")
def teacher_defense_arrangements(batchId: int = Query(..., ge=1), page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), user=Depends(get_current_user)):
    return success(_paged_service(tea.graduation_defense_arrangements, user, batchId, page, pageSize))


@router.get("/grade/queue")
def teacher_grade_queue(batchId: int = Query(..., ge=1), page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), user=Depends(get_current_user)):
    return success(_paged_service(tea.graduation_grade_queue, user, batchId, page, pageSize))


@router.get("/grade/{gd_student_id}")
def teacher_grade_detail(gd_student_id: str, batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    with session() as db: _student(db, gd_student_id, batchId)
    return success(tea.graduation_grade_detail(user, gd_student_id))


@router.post("/grade/{gd_student_id}/review")
def teacher_grade_review(gd_student_id: str, body: dict = Body(...), batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    with session() as db: _student(db, gd_student_id, batchId)
    return success(tea.graduation_grade_review(user, gd_student_id, body.get("action") or "", body.get("comment") or ""), message="复核完成")


@router.get("/choices/pending")
def teacher_graduation_choices_pending(batchId: int = Query(..., ge=1), page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), user=Depends(get_current_user)):
    return success(_paged_service(tea.graduation_choices_pending, user, batchId, page, pageSize))


@router.post("/choices/{choice_id}/review")
def teacher_graduation_choice_review(choice_id: str, body: dict = Body(...), batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    _choice_student(choice_id, batchId)
    return success(tea.graduation_choice_review(user, choice_id, str(body.get("action") or "").upper(), body.get("reason") or ""), message="处理完成")


@router.get("/change-requests/pending")
def teacher_graduation_change_requests_pending(batchId: int = Query(..., ge=1), page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), user=Depends(get_current_user)):
    return success(_paged_service(tea.graduation_change_requests_pending, user, batchId, page, pageSize))


@router.post("/change-requests/{request_id}/review")
def teacher_graduation_change_request_review(request_id: str, body: dict = Body(...), batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    _change_student(request_id, batchId)
    return success(tea.graduation_change_request_review(user, request_id, str(body.get("action") or "").upper(), body.get("comment") or ""), message="处理完成")


@router.post("/{gd_student_id}/guidance")
def teacher_graduation_guidance_create(gd_student_id: str, body: dict = Body(...), batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    with session() as db: _student(db, gd_student_id, batchId)
    return success(tea.graduation_guidance_create(user, gd_student_id, body), message="已记录")


@router.get("/taskbooks")
def teacher_graduation_taskbook_list(batchId: int = Query(..., ge=1), page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), user=Depends(get_current_user)):
    return success(_paged_service(tea.graduation_taskbook_list, user, batchId, page, pageSize))


@router.post("/taskbooks/{gd_student_id}/issue")
def teacher_graduation_taskbook_issue(gd_student_id: str, body: dict = Body(...), batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    with session() as db: _student(db, gd_student_id, batchId)
    return success(tea.graduation_taskbook_issue(user, gd_student_id, body), message="任务书已下达")


@router.post("/taskbooks/{gd_student_id}/change")
def teacher_graduation_taskbook_change(gd_student_id: str, body: dict = Body(...), batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    with session() as db: _student(db, gd_student_id, batchId)
    return success(tea.graduation_taskbook_change(user, gd_student_id, body), message="已提交变更")


@router.get("/defense/pending")
def teacher_graduation_defense_score_pending(batchId: int = Query(..., ge=1), page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100), user=Depends(get_current_user)):
    return success(_paged_service(tea.graduation_defense_score_pending, user, batchId, page, pageSize))


@router.post("/defense/{gd_student_id}/score")
def teacher_graduation_defense_score_entry(gd_student_id: str, body: dict = Body(...), batchId: int = Query(..., ge=1), user=Depends(get_current_user)):
    with session() as db: _student(db, gd_student_id, batchId)
    return success(tea.graduation_defense_score_entry(user, gd_student_id, body), message="已保存")
