"""AA-DASHBOARD-01 教务看板 readiness 与准备清单导出。"""
from __future__ import annotations

import io
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_dashboard_readiness_final_service as service

router = APIRouter(prefix="/academic-affairs/dashboard", tags=["教务看板 readiness"])
_VIEW = "academicAffairs.dashboard.view"
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/readiness", summary="当前学期阶段 readiness：正常/风险/阻断与责任入口")
def readiness(termId: int | None = Query(None), user=Depends(require_permission(_VIEW))):
    return success(service.readiness(user, termId))


@router.get("/readiness/export", summary="导出开学与学期运行准备清单（xlsx）")
def export_readiness(
    termId: int | None = Query(None),
    purpose: str = Query(..., min_length=5),
    user=Depends(require_permission(_VIEW)),
):
    content, filename = service.export_readiness_xlsx(user, termId, purpose)
    return StreamingResponse(
        io.BytesIO(content),
        media_type=_XLSX,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
