"""R10 教务统计冻结快照接口。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_stats_snapshot_service as service

router = APIRouter(prefix="/academic-affairs/stats/snapshots", tags=["教务中心-统计快照"])


class StatsSnapshotCreateBody(BaseModel):
    snapshotType: str = Field(default="OVERVIEW", min_length=1, max_length=40)
    termId: int | None = Field(default=None, gt=0)
    collegeId: int | None = Field(default=None, gt=0)
    majorId: int | None = Field(default=None, gt=0)
    reason: str = Field(..., min_length=5, max_length=500)


@router.post("", summary="冻结当前教务统计快照")
def stats_snapshot_create(
    body: StatsSnapshotCreateBody,
    user=Depends(require_permission("academicAffairs.stats.view")),
):
    return success(
        service.create_snapshot(
            user,
            term_id=body.termId,
            college_id=body.collegeId,
            major_id=body.majorId,
            snapshot_type=body.snapshotType,
            reason=body.reason,
        ),
        message="统计快照已冻结",
    )


@router.get("", summary="统计快照列表")
def stats_snapshot_list(
    termId: int | None = Query(default=None, gt=0),
    snapshotType: str | None = Query(default=None, max_length=40),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=50, ge=1, le=100),
    user=Depends(require_permission("academicAffairs.stats.view")),
):
    rows, total = service.list_snapshots(
        user,
        term_id=termId,
        snapshot_type=snapshotType,
        page=page,
        page_size=pageSize,
    )
    return success({"list": rows, "total": total, "page": page, "pageSize": pageSize})


@router.get("/{snapshot_id}", summary="统计快照详情与哈希校验")
def stats_snapshot_detail(
    snapshot_id: int = Path(..., gt=0),
    user=Depends(require_permission("academicAffairs.stats.view")),
):
    return success(service.get_snapshot(user, snapshot_id))
