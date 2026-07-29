"""V2-03 排课规则独立路由。

旧总路由将 ruleValue 锁死为 dict，列表、整数、布尔规则会在进入 service 前被 422 拒绝。
本路由保持原 URL 和权限不变，只纠正请求体类型；最终规则目录和值域仍由 service 裁定。
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.academic_affairs.services import academic_affairs_scheduling_service as scheduling_service

router = APIRouter(prefix="/academic-affairs/scheduling", tags=["教务中心-排课规则"])

_RULE_MANAGE = require_permission("academicAffairs.schedule.rule.manage")
_RULE_VIEW = require_permission("academicAffairs.schedule.view")


class SchedulingRuleBody(BaseModel):
    ruleKey: str = Field(..., min_length=1, max_length=100)
    termId: Optional[int] = Field(default=None, gt=0)
    batchId: Optional[int] = Field(default=None, gt=0)
    ruleValue: Any = None
    remark: Optional[str] = Field(default=None, max_length=500)


@router.put("/rules", summary="保存排课规则（对象/列表/整数/布尔）")
def scheduling_rule_save(body: SchedulingRuleBody, user=Depends(_RULE_MANAGE)):
    return success(scheduling_service.save_rule(user, body), message="已保存")


@router.get("/rules", summary="排课规则列表")
def scheduling_rule_list(
    termId: Optional[int] = None,
    batchId: Optional[int] = None,
    user=Depends(_RULE_VIEW),
):
    return success({"items": scheduling_service.list_rules(user, termId, batchId)})


@router.delete("/rules/{rule_id}", summary="删除排课规则")
def scheduling_rule_delete(rule_id: int = Path(..., gt=0), user=Depends(_RULE_MANAGE)):
    return success(scheduling_service.delete_rule(user, rule_id), message="已删除")
