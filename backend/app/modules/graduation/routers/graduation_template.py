"""毕业设计中心 · 材料模板中心 API（/api/v1/graduation/gd-templates/*）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.response import paginate, success
from app.core.security import get_current_user
from app.services import audit_log
from app.modules.graduation.services import graduation_template_service as svc

router = APIRouter(prefix="/graduation/gd-templates", tags=["毕业设计-模板中心"])


@router.get("", summary="模板列表（按类型/状态/关键词）")
def list_templates(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                   templateType: Optional[str] = None, status: Optional[str] = None,
                   keyword: Optional[str] = None, user=Depends(get_current_user)):
    i, t = svc.list_templates(page, pageSize, template_type=templateType, status=status, keyword=keyword)
    return success(paginate(i, t, page, pageSize))


@router.get("/variables", summary="各类型可用占位变量字典")
def variables(user=Depends(get_current_user)):
    return success(svc.variable_dict())


@router.get("/stats", summary="模板统计")
def stats(templateType: Optional[str] = None, user=Depends(get_current_user)):
    return success(svc.stats(template_type=templateType))


@router.get("/{tid}", summary="模板详情")
def detail(tid: str, user=Depends(get_current_user)):
    return success(svc.get_template(tid))


@router.post("", summary="新建模板")
def create(body: dict = Body(...), user=Depends(get_current_user)):
    data = svc.create_template(body.get("templateType"), body.get("name"), body.get("content"),
                               body.get("variables"), body.get("applicableNote"),
                               body.get("version"), body.get("remark"))
    audit_log.record("新建毕设模板", f"graduation-template:{data['id']}")
    return success(data, message="已创建")


@router.put("/{tid}", summary="编辑模板")
def update(tid: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(svc.update_template(tid, body.get("name"), body.get("content"), body.get("variables"),
                   body.get("applicableNote"), body.get("version"), body.get("remark")), message="已保存")


@router.post("/{tid}/status", summary="状态机（ENABLE/DISABLE/ARCHIVE）")
def set_status(tid: str, body: dict = Body(...), user=Depends(get_current_user)):
    return success(svc.set_status(tid, str(body.get("action") or "").upper()), message="已更新")


@router.post("/{tid}/default", summary="设为默认模板（同类型唯一）")
def set_default(tid: str, user=Depends(get_current_user)):
    return success(svc.set_default(tid), message="已设为默认")
