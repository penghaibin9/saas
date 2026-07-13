"""岗位实习中心 · 实习协议模板库 API（/api/v1/internship/agreement-templates/*）。

独立 router，与实习域/批次/岗位库隔离；在 router.py 汇总处单独 include。
写操作落审计。静态子路由（stats/variables）声明在 /{template_id} 之前，避免被动态段吞掉。
权限：登录校验（get_current_user）；细粒度 permission key（internship.agreementTemplate.*）随全局 RBAC 上线前补，
本模块权限 key 已在路由 summary 标注，数据范围按租户隔离（校级配置主数据）。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.internship.schemas.internship_agreement_template import (AgreementTemplateCreate, AgreementTemplateUpdate,
                                                       SetDefaultRequest, StatusAction)
from app.services import audit_log
from app.modules.internship.services import internship_agreement_template_service as svc

router = APIRouter(prefix="/internship", tags=["岗位实习-协议模板库"])

_BASE = "/agreement-templates"
# 协议模板是校级配置主数据，查看与编辑统一 internship.agreement.template.manage（管理员/学院负责人）
_P = "internship.agreement.template.manage"


@router.get(_BASE, summary="协议模板列表（分页+筛选：关键词/状态/类型/学院/专业/年级/批次）")
def templates(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
              keyword: Optional[str] = None, status: Optional[str] = None,
              category: Optional[str] = None, collegeId: Optional[str] = None,
              majorId: Optional[str] = None, grade: Optional[str] = None,
              batchId: Optional[str] = None, user=Depends(require_permission(_P))):
    items, total = svc.list_templates(page, pageSize, keyword=keyword, status=status,
                                      category=category, college_id=collegeId, major_id=majorId,
                                      grade=grade, batch_id=batchId)
    return success(paginate(items, total, page, pageSize))


@router.get(f"{_BASE}/stats", summary="协议模板统计（按状态/默认数）")
def template_stats(user=Depends(require_permission(_P))):
    return success(svc.template_stats())


@router.get(f"{_BASE}/variables", summary="协议模板标准变量字典（学生姓名/企业名称/岗位名称/实习时间等）")
def template_variables(user=Depends(require_permission(_P))):
    return success(svc.variable_presets())


@router.post(_BASE, summary="新建协议模板（初始草稿）")
def create_template(body: AgreementTemplateCreate, user=Depends(require_permission(_P))):
    result = svc.create_template(body)
    audit_log.record("新建协议模板", f"internship-agreement-template:{result['id']}",
                     detail={"name": result["name"]})
    return success(result, message="已创建")


@router.get(f"{_BASE}/{{template_id}}", summary="协议模板详情（含正文/变量/适用范围/审计）")
def template_detail(template_id: str, user=Depends(require_permission(_P))):
    return success(svc.get_template(template_id))


@router.put(f"{_BASE}/{{template_id}}", summary="编辑协议模板（已归档不可编辑）")
def update_template(template_id: str, body: AgreementTemplateUpdate, user=Depends(require_permission(_P))):
    result = svc.update_template(template_id, body)
    audit_log.record("编辑协议模板", f"internship-agreement-template:{template_id}")
    return success(result, message="已保存")


@router.post(f"{_BASE}/{{template_id}}/status",
             summary="协议模板状态机（ENABLE 启用 / DISABLE 停用 / ARCHIVE 归档）")
def template_status(template_id: str, body: StatusAction, user=Depends(require_permission(_P))):
    result = svc.set_status(template_id, body.action, body.reason or "")
    audit_log.record("协议模板状态变更", f"internship-agreement-template:{template_id}",
                     detail={"action": body.action})
    return success(result, message="已更新")


@router.post(f"{_BASE}/{{template_id}}/default", summary="设为/取消默认模板（设默认须启用中；同类型唯一）")
def template_default(template_id: str, body: SetDefaultRequest, user=Depends(require_permission(_P))):
    result = svc.set_default(template_id, body.on)
    audit_log.record("设置默认协议模板" if body.on else "取消默认协议模板",
                     f"internship-agreement-template:{template_id}", detail={"on": body.on})
    return success(result, message="已更新")
