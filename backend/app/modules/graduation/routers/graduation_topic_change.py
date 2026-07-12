"""毕业设计中心 · 选题变更申请 API（/api/v1/graduation/gd-topic-change-requests/*）。

独立 router，与题目库/选题轮次隔离；在 router.py 汇总处单独 include。
管理端/教师 Web 端通用入口（学生自服务走 /api/v1/mobile/graduation/*，见 mobile.py）。
写操作落审计。静态子路由声明在 /{request_id} 之前，避免被动态段吞掉。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.graduation.schemas.graduation_topic_change import GdTopicChangeRequestCreate, GdTopicChangeReview
from app.services import audit_log
from app.modules.graduation.services import graduation_topic_change_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-选题变更申请"])


@router.get("/gd-topic-change-requests", summary="选题变更申请列表（分页+筛选：学生/状态）")
def gd_topic_change_requests(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                             gdStudentId: Optional[str] = None, status: Optional[str] = None,
                             user=Depends(get_current_user)):
    items, total = svc.list_change_requests(page, pageSize, gd_student_id=gdStudentId, status=status)
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-topic-change-requests", summary="发起选题变更申请（管理端代提交，正式自服务见小程序端）")
def create_gd_topic_change_request(body: GdTopicChangeRequestCreate, user=Depends(get_current_user)):
    result = svc.request_change(body.gdStudentId, body.newTopicId, body.reason,
                                requested_by=(user or {}).get("realName", "管理员代提交"))
    audit_log.record("发起选题变更申请", f"graduation-topic-change:{result['id']}", detail=result)
    return success(result, message="已提交，等待审核")


@router.get("/gd-topic-change-requests/{request_id}", summary="变更申请详情")
def gd_topic_change_request_detail(request_id: str, user=Depends(get_current_user)):
    return success(svc.get_change_request(request_id))


@router.post("/gd-topic-change-requests/{request_id}/review",
             summary="审核变更申请（APPROVE 通过即迁移分配 / REJECT 驳回须≥5字理由，写审计）")
def review_gd_topic_change_request(request_id: str, body: GdTopicChangeReview,
                                   user=Depends(get_current_user)):
    result = svc.review_change(request_id, body.action, body.comment or "",
                               reviewer_name=(user or {}).get("realName", "管理员"))
    audit_log.record("审核选题变更申请", f"graduation-topic-change:{request_id}",
                     detail={"action": body.action})
    return success(result, message="已处理")
