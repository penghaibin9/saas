"""毕业设计中心 · 毕设批次 API（/api/v1/graduation/batches/*）。

独立 router 文件，与毕业设计域其它 API 隔离；在 router.py 汇总处单独 include。
写操作落审计；Excel 台账导出经 base64 返回。静态子路由（export/stats）声明在 /{bid} 之前。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.schemas.graduation_batch import (BatchCreate, BatchUpdate, RulesRequest, StagesRequest,
                                           VoidBatchRequest)
from app.services import audit_log
from app.services import graduation_batch_service as svc

router = APIRouter(prefix="/graduation", tags=["毕业设计-毕设批次"])


@router.post("/batches/export", summary="导出毕设批次台账 Excel（写审计）")
def batch_export(keyword: Optional[str] = None, status: Optional[str] = None,
                 user=Depends(get_current_user)):
    data = svc.export_batches_xlsx(keyword=keyword, status=status)
    audit_log.record("导出毕设批次台账", "graduation-batch:export", detail={"rowCount": data["rowCount"]})
    return success(data)


@router.get("/batches/stats", summary="毕设批次统计（按状态）")
def batch_stats(user=Depends(get_current_user)):
    return success(svc.batch_stats())


@router.get("/batches", summary="毕设批次列表（分页+筛选）")
def batches(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
            keyword: Optional[str] = None, status: Optional[str] = None,
            user=Depends(get_current_user)):
    items, total = svc.list_batches(page, pageSize, keyword=keyword, status=status)
    return success(paginate(items, total, page, pageSize))


@router.post("/batches", summary="新建毕设批次（草稿态，批次编号租户内唯一）")
def batch_create(body: BatchCreate, user=Depends(get_current_user)):
    result = svc.create_batch(body.model_dump())
    audit_log.record("新建毕设批次", f"graduation-batch:{result['id']}", detail={"batchName": body.batchName})
    return success(result, message="已新建")


@router.get("/batches/{bid}", summary="批次详情（含阶段时间轴/规则配置/审计留痕）")
def batch_detail(bid: str, user=Depends(get_current_user)):
    return success(svc.get_batch(bid))


@router.put("/batches/{bid}", summary="编辑批次（已结束/已归档/已作废不可编辑）")
def batch_update(bid: str, body: BatchUpdate, user=Depends(get_current_user)):
    result = svc.update_batch(bid, body.model_dump(exclude_unset=True))
    audit_log.record("编辑毕设批次", f"graduation-batch:{bid}")
    return success(result, message="已保存")


@router.post("/batches/{bid}/stages", summary="配置阶段时间轴")
def batch_stages(bid: str, body: StagesRequest, user=Depends(get_current_user)):
    result = svc.set_stages(bid, body.stages)
    audit_log.record("配置毕设批次阶段", f"graduation-batch:{bid}")
    return success(result, message="已保存")


@router.post("/batches/{bid}/rules", summary="配置规则（查重/评阅/答辩/成绩）")
def batch_rules(bid: str, body: RulesRequest, user=Depends(get_current_user)):
    result = svc.set_rules(bid, body.rules)
    audit_log.record("配置毕设批次规则", f"graduation-batch:{bid}")
    return success(result, message="已保存")


@router.post("/batches/{bid}/activate", summary="启用批次（草稿→进行中）")
def batch_activate(bid: str, user=Depends(get_current_user)):
    result = svc.activate_batch(bid)
    audit_log.record("启用毕设批次", f"graduation-batch:{bid}")
    return success(result, message="已启用")


@router.post("/batches/{bid}/close", summary="结束批次（进行中→已结束）")
def batch_close(bid: str, user=Depends(get_current_user)):
    result = svc.close_batch(bid)
    audit_log.record("结束毕设批次", f"graduation-batch:{bid}")
    return success(result, message="已结束")


@router.post("/batches/{bid}/archive", summary="归档批次（已结束→已归档）")
def batch_archive(bid: str, user=Depends(get_current_user)):
    result = svc.archive_batch(bid)
    audit_log.record("归档毕设批次", f"graduation-batch:{bid}")
    return success(result, message="已归档")


@router.post("/batches/{bid}/void", summary="作废批次（仅草稿可作废，原因≥5字）")
def batch_void(bid: str, body: VoidBatchRequest, user=Depends(get_current_user)):
    result = svc.void_batch(bid, body.reason)
    audit_log.record("作废毕设批次", f"graduation-batch:{bid}", detail={"reason": body.reason})
    return success(result, message="已作废")
