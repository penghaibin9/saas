"""岗位实习中心 · 岗位库 API（/api/v1/internship/positions/*）。

独立 router 文件，与实习域/批次 API 隔离；在 router.py 汇总处单独 include。
写操作落审计。静态子路由（stats/import/export）声明在 /{position_id} 之前。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.internship_position import (PositionCreate, PositionImport, PositionRiskRequest,
                                             PositionStatusAction, PositionUpdate)
from app.services import audit_log
from app.services import internship_position_service as pos

router = APIRouter(prefix="/internship", tags=["岗位实习-岗位库"])


@router.get("/positions", summary="岗位库列表（分页+筛选）")
def positions(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, status: Optional[str] = None,
              companyId: Optional[str] = None, risk: Optional[bool] = None,
              user=Depends(get_current_user)):
    items, total = pos.list_positions(page, pageSize, keyword=keyword, status=status,
                                      company_id=companyId, risk=risk)
    return success(paginate(items, total, page, pageSize))


@router.get("/positions/stats", summary="岗位库统计（按状态/风险/容量）")
def position_stats(user=Depends(get_current_user)):
    return success(pos.position_stats())


@router.post("/positions/import/dry-run", summary="岗位导入·预校验（企业须能匹配，不写库）")
def position_import_dry_run(body: PositionImport, user=Depends(get_current_user)):
    return success(pos.import_dry_run(body.rows))


@router.post("/positions/import/confirm", summary="岗位导入·确认（整批事务，预校验须全通过）")
def position_import_confirm(body: PositionImport, user=Depends(get_current_user)):
    result = pos.import_confirm(body.rows)
    audit_log.record("导入岗位库", "internship-position:import", detail=result)
    return success(result, message="导入完成")


@router.post("/positions/export", summary="岗位库导出 CSV（写审计）")
def position_export(keyword: Optional[str] = None, status: Optional[str] = None,
                    companyId: Optional[str] = None, user=Depends(get_current_user)):
    data = pos.export_positions(keyword=keyword, status=status, company_id=companyId)
    audit_log.record("导出岗位库", "internship-position:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.post("/positions", summary="新增岗位（草稿；必须关联企业）")
def create_position(body: PositionCreate, user=Depends(get_current_user)):
    result = pos.create_position(body)
    audit_log.record("新增岗位", f"internship-position:{result['id']}", detail={"title": result["title"]})
    return success(result, message="已创建")


@router.get("/positions/{position_id}", summary="岗位详情（含企业合作状态/导师/审计）")
def position_detail(position_id: str, user=Depends(get_current_user)):
    return success(pos.get_position(position_id))


@router.put("/positions/{position_id}", summary="编辑岗位（已归档不可编辑）")
def update_position(position_id: str, body: PositionUpdate, user=Depends(get_current_user)):
    result = pos.update_position(position_id, body)
    audit_log.record("编辑岗位", f"internship-position:{position_id}")
    return success(result, message="已保存")


@router.post("/positions/{position_id}/status",
             summary="岗位状态机（提交/上架/下架/暂停/归档；黑名单·停用企业不能上架）")
def position_status(position_id: str, body: PositionStatusAction, user=Depends(get_current_user)):
    result = pos.set_status(position_id, body.action, body.reason or "")
    audit_log.record("岗位状态变更", f"internship-position:{position_id}", detail={"action": body.action})
    return success(result, message="已更新")


@router.post("/positions/{position_id}/risk", summary="风险岗位标记/解除（标记须说明）")
def position_risk(position_id: str, body: PositionRiskRequest, user=Depends(get_current_user)):
    result = pos.mark_risk(position_id, body.on, body.note or "")
    audit_log.record("岗位风险标记", f"internship-position:{position_id}", detail={"on": body.on})
    return success(result, message="已更新")
