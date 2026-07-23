"""毕业设计中心 · 导师对学生过程评价 API（/api/v1/graduation/gd-student-evals/*）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.graduation.schemas.graduation_student_eval import StudentEvalCreate
from app.modules.graduation.services import graduation_student_eval_service as svc
from app.services import audit_log

router = APIRouter(prefix="/graduation", tags=["毕业设计-导师评价学生"])


@router.get("/gd-student-evals", summary="导师对学生评价列表")
def gd_student_evals(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                     gdStudentId: Optional[str] = None, user=Depends(get_current_user)):
    items, total = svc.list_evals(page, pageSize, gd_student_id=gdStudentId)
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-student-evals/{gd_student_id}", summary="创建/提交导师对学生评价")
def gd_student_eval_create(gd_student_id: str, body: StudentEvalCreate, user=Depends(get_current_user)):
    result = svc.create_eval(gd_student_id, body.model_dump())
    audit_log.record("导师评价学生", f"graduation-student-eval:{result['id']}")
    return success(result, message="已保存" if result.get("status") == "DRAFT" else "已提交评价")


@router.post("/gd-student-evals/records/{eval_id}/submit", summary="提交评价草稿")
def gd_student_eval_submit(eval_id: str, user=Depends(get_current_user)):
    result = svc.submit_eval(eval_id)
    audit_log.record("提交导师评价", f"graduation-student-eval:{eval_id}")
    return success(result, message="已提交评价")
