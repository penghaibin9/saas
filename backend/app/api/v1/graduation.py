"""毕业设计域 API（/api/v1/graduation/*）。真实走库；批阅/发布落域审计。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.graduation import ReviewBody
from app.services import graduation_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计"])


def _p(i, t, page, ps):
    return success(paginate(i, t, page, ps))


@router.get("/dashboard", summary="毕设看板")
def dashboard(user=Depends(get_current_user)):
    return success(svc.get_dashboard())


@router.get("/students", summary="毕设学生列表")
def students(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
             keyword: Optional[str] = None, classId: Optional[str] = None,
             stage: Optional[str] = None, riskLevel: Optional[str] = None,
             user=Depends(get_current_user)):
    i, t = svc.list_students(page, pageSize, keyword=keyword, class_id=classId, stage=stage,
                             risk_level=riskLevel)
    return _p(i, t, page, pageSize)


@router.get("/students/{sid}", summary="毕设学生详情")
def student_detail(sid: str, user=Depends(get_current_user)):
    return success(svc.get_student_detail(sid))


@router.get("/topics", summary="选题列表")
def topics(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
           keyword: Optional[str] = None, status: Optional[str] = None,
           user=Depends(get_current_user)):
    i, t = svc.list_topics(page, pageSize, keyword=keyword, status=status)
    return _p(i, t, page, pageSize)


@router.get("/proposals", summary="开题材料列表")
def proposals(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, status: Optional[str] = None,
              user=Depends(get_current_user)):
    i, t = svc.list_proposals(page, pageSize, keyword=keyword, status=status)
    return _p(i, t, page, pageSize)


@router.get("/proposals/{pid}", summary="开题批阅详情")
def proposal_detail(pid: str, user=Depends(get_current_user)):
    return success(svc.get_proposal_detail(pid))


@router.post("/proposals/{pid}/review", summary="批阅开题（驳回原因≥5字）")
def proposal_review(pid: str, body: ReviewBody, user=Depends(get_current_user)):
    return success(svc.review_proposal(pid, body.action, body.comment), message="已批阅")


@router.get("/finals", summary="成果提交列表")
def finals(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
           keyword: Optional[str] = None, status: Optional[str] = None,
           user=Depends(get_current_user)):
    i, t = svc.list_finals(page, pageSize, keyword=keyword, status=status)
    return _p(i, t, page, pageSize)


@router.post("/finals/{fid}/review", summary="批阅成果（驳回原因≥5字）")
def final_review(fid: str, body: ReviewBody, user=Depends(get_current_user)):
    return success(svc.review_final(fid, body.action, body.comment), message="已批阅")


@router.get("/defense-groups", summary="答辩安排列表")
def defense_groups(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                   keyword: Optional[str] = None, user=Depends(get_current_user)):
    i, t = svc.list_defense_groups(page, pageSize, keyword=keyword)
    return _p(i, t, page, pageSize)


@router.post("/defense-groups/{gid}/publish", summary="发布答辩安排（冲突/未安排完整则拒绝）")
def defense_publish(gid: str, user=Depends(get_current_user)):
    return success(svc.publish_defense(gid), message="已发布")


@router.get("/audit-logs", summary="毕设域审计")
def audit_logs(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
               bizType: Optional[str] = None, keyword: Optional[str] = None,
               user=Depends(get_current_user)):
    i, t = svc.list_audit(page, pageSize, biz_type=bizType, keyword=keyword)
    return _p(i, t, page, pageSize)
