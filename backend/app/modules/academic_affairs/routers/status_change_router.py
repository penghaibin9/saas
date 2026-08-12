"""D3-S 学籍异动 Move Only 正式 Router。

只迁仍属于 legacy base 的 status-change 入口；future-effective `/scheduled`
继续由 status_change_temporal_router 持有，安全 guard / canonical service / fact 链不改。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.routers import academic_affairs as legacy
from app.modules.academic_affairs.services import academic_affairs_change_service as change_svc

router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])

# Move Only：沿用历史 DTO 对象，避免 Pydantic/OpenAPI 合同漂移。
StatusChangeSubmit = legacy.StatusChangeSubmit
AaReviewBody = legacy.AaReviewBody

_SC_APPLY = legacy._SC_APPLY
_SC_VIEW = legacy._SC_VIEW
_SC_COUNSELOR = legacy._SC_COUNSELOR
_SC_COLLEGE = legacy._SC_COLLEGE
_SC_OFFICE = legacy._SC_OFFICE
_SC_LIST_VIEW = legacy._SC_LIST_VIEW
_SC_REVIEW_ANY = legacy._SC_REVIEW_ANY


@router.post("/status-changes", summary="发起学籍异动（含休学/复学/退学/转专业/转班分类申请入口，changeType 区分）")
def status_change_submit(body: StatusChangeSubmit, user=Depends(require_permission(_SC_APPLY))):
    return success(change_svc.submit(body, user), message="异动已提交")


@router.get("/status-changes", summary="学籍异动列表（台账/分类申请记录/异动生效均复用，范围过滤）")
def status_changes(changeType: Optional[str] = None, status: Optional[str] = None,
                   studentId: Optional[str] = None, dateFrom: Optional[str] = None,
                   dateTo: Optional[str] = None, page: int = 1, pageSize: int = 20,
                   user=Depends(_SC_LIST_VIEW)):
    items, total = change_svc.list_changes(user, changeType, status, studentId, dateFrom, dateTo, page, pageSize)
    return success(paginate(items, total, page, pageSize))


# 字面量必须先于 /status-changes/{changeId}，保持历史 FastAPI 匹配顺序。
@router.get("/status-changes/stats", summary="学籍异动统计（按类型/状态/在途节点聚合，范围过滤）")
def status_change_stats(termCode: Optional[str] = None, user=Depends(require_permission(_SC_VIEW))):
    return success(change_svc.stats(user, termCode))


@router.get("/status-changes/{changeId}", summary="异动详情")
def status_change_detail(changeId: int = Path(...), user=Depends(_SC_LIST_VIEW)):
    return success(change_svc.get_change(changeId, user))


@router.post("/status-changes/{changeId}/review", summary="异动审批（多节点，终审经单一入口生效；节点授权见 service）")
def status_change_review(body: AaReviewBody, changeId: int = Path(...), user=Depends(_SC_REVIEW_ANY)):
    return success(
        change_svc.review(
            changeId,
            user,
            body.action,
            body.reason or "",
            expected_decision_version=body.expectedDecisionVersion,
        ),
        message="已处理",
    )
