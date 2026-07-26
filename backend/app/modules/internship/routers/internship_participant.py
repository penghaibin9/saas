"""岗位实习中心 · 批次参与人 API（/api/v1/internship/batches/{batchId}/participants/*）。

用组织范围选人替代反复导 Excel 名单。权限复用批次口径：
查看 internship.batch.view；改规则/预览/冻结/增减 internship.batch.manage。
不新增权限码——选人本就是"管这个批次"的一部分，另立门户会让学校要重配一遍角色。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.internship.services import internship_participant_service as svc

router = APIRouter(prefix="/internship/batches", tags=["岗位实习-批次参与人"])

_VIEW = require_permission("internship.batch.view")
_MANAGE = require_permission("internship.batch.manage")


class ScopeRuleBody(BaseModel):
    """选人规则。字段与前端组织选择器的产出一一对应，不需要中间映射。"""
    collegeIds: List[str] = Field(default_factory=list)
    majorIds: List[str] = Field(default_factory=list)
    classIds: List[str] = Field(default_factory=list)
    studentIds: List[str] = Field(default_factory=list)
    grades: List[str] = Field(default_factory=list)
    excludeCollegeIds: List[str] = Field(default_factory=list)
    excludeMajorIds: List[str] = Field(default_factory=list)
    excludeClassIds: List[str] = Field(default_factory=list)
    excludeStudentIds: List[str] = Field(default_factory=list)
    stages: List[str] = Field(default_factory=list)
    studentStatuses: List[str] = Field(default_factory=list)


class FreezeBody(BaseModel):
    rule: Optional[ScopeRuleBody] = Field(None, description="留空则用最近一次保存的规则")


class AddParticipantsBody(BaseModel):
    studentIds: List[str] = Field(..., min_length=1)
    reason: Optional[str] = Field("", max_length=500)


class RemoveParticipantBody(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)
    version: int = Field(..., description="乐观锁版本，必填")


@router.get("/{batchId}/participants/rule", summary="读取批次选人规则")
def get_rule(batchId: str = Path(...), user=Depends(_VIEW)):
    return success(svc.get_rule(batchId))


@router.post("/{batchId}/participants/preview", summary="按规则预览名单（不写名单）")
def preview(body: ScopeRuleBody, batchId: str = Path(...), user=Depends(_MANAGE)):
    return success(svc.preview(batchId, body.model_dump(), user))


@router.post("/{batchId}/participants/freeze", summary="冻结名单（幂等建实习记录，批次转进行中）")
def freeze(body: FreezeBody, batchId: str = Path(...), user=Depends(_MANAGE)):
    payload = {"rule": body.rule.model_dump() if body.rule else None}
    return success(svc.freeze(batchId, payload, user), message="名单已冻结")


@router.get("/{batchId}/participants", summary="批次参与人名单")
def list_participants(batchId: str = Path(...), page: int = Query(1, ge=1),
                      pageSize: int = Query(20, ge=1, le=200), keyword: Optional[str] = None,
                      includeRemoved: bool = False, user=Depends(_VIEW)):
    items, total = svc.list_participants(batchId, page, pageSize, keyword, includeRemoved)
    return success(paginate(items, total, page, pageSize))


@router.get("/{batchId}/participants/summary", summary="参与人概览")
def participant_summary(batchId: str = Path(...), user=Depends(_VIEW)):
    return success(svc.summary(batchId))


@router.post("/{batchId}/participants/add", summary="人工补录参与人")
def add_participants(body: AddParticipantsBody, batchId: str = Path(...), user=Depends(_MANAGE)):
    return success(svc.add_participants(batchId, body.studentIds, user, body.reason or ""),
                   message="已补录")


@router.post("/{batchId}/participants/{participantId}/remove", summary="移出参与人（保留追溯）")
def remove_participant(body: RemoveParticipantBody, batchId: str = Path(...),
                       participantId: str = Path(...), user=Depends(_MANAGE)):
    return success(svc.remove_participant(batchId, participantId, body.reason, body.version),
                   message="已移出")
