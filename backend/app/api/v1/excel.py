"""公共 Excel 底座 · 通用端点（/api/v1/excel/*）。

目前提供「通用导入记录」查询——跨模块导入作业台账（t_excel_import_job），供运维/审计追溯。
底座能力本身以库形式被各业务模块 import 使用（见 app.services.excel）；本 router 只暴露通用查询。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.services.excel import job_service

router = APIRouter(prefix="/excel", tags=["excel-底座"])


@router.get("/import-jobs", summary="通用导入记录（跨模块导入作业台账，分页）")
def import_jobs(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                moduleKey: Optional[str] = None, bizType: Optional[str] = None,
                status: Optional[str] = None, user=Depends(get_current_user)):
    items, total = job_service.list_jobs(page, pageSize, module_key=moduleKey,
                                         biz_type=bizType, status=status)
    return success(paginate(items, total, page, pageSize))
