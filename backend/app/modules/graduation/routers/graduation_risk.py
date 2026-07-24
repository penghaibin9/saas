"""毕业设计中心 · 问题预警 API（/api/v1/graduation/gd-risks/*）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.modules.graduation.schemas.graduation_risk import RiskAcceptRequest, RiskCloseRequest, RiskProcessRequest
from app.services import audit_log
from app.modules.graduation.services import graduation_risk_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-问题预警"])


@router.get("/gd-risks/stats", summary="风险统计（按编码/等级）")
def gd_risk_stats(batchId: int | None = Query(default=None, ge=1),
                  user=Depends(get_current_user)):
    return success(svc.risk_stats(batch_id=batchId))


@router.post("/gd-risks/scan", summary="扫描生成风险项（须指定批次；幂等）")
def gd_risk_scan(batchId: int | None = Query(default=None, ge=1),
                 user=Depends(get_current_user)):
    result = svc.scan_risks(batch_id=batchId)
    audit_log.record("扫描毕设风险", "graduation-risk:scan", detail=result)
    return success(result, message=f"新发现 {result['newCasesCreated']} 项")


@router.get("/gd-risks", summary="风险列表（分页+筛选）")
def gd_risks(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            riskCode: Optional[str] = None, level: Optional[str] = None, status: Optional[str] = None,
            gdStudentId: Optional[str] = None, batchId: Optional[str] = None,
            user=Depends(get_current_user)):
    items, total = svc.list_risks(page, pageSize, risk_code=riskCode, level=level, status=status,
                                  gd_student_id=gdStudentId, batch_id=batchId)
    return success(paginate(items, total, page, pageSize))


@router.post("/gd-risks/{rid}/accept", summary="受理风险")
def gd_risk_accept(rid: str, body: RiskAcceptRequest, user=Depends(get_current_user)):
    result = svc.accept_risk(rid, body.assignee)
    audit_log.record("受理风险", f"graduation-risk:{rid}")
    return success(result, message="已受理")


@router.post("/gd-risks/{rid}/process", summary="记录处理过程")
def gd_risk_process(rid: str, body: RiskProcessRequest, user=Depends(get_current_user)):
    result = svc.process_risk(rid, body.note)
    audit_log.record("处理风险", f"graduation-risk:{rid}")
    return success(result, message="已记录")


@router.post("/gd-risks/{rid}/close", summary="关闭风险（原因≥5字）")
def gd_risk_close(rid: str, body: RiskCloseRequest, user=Depends(get_current_user)):
    result = svc.close_risk(rid, body.reason)
    audit_log.record("关闭风险", f"graduation-risk:{rid}", detail={"reason": body.reason})
    return success(result, message="已关闭")
