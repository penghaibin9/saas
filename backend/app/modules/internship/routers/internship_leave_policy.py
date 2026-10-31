"""实习批次请假审批配置，复用学校现有角色、范围与统一审批记录。"""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.core.permissions import require_permission
from app.core.response import success
from app.modules.internship.services import internship_leave_policy_service as service

router = APIRouter(prefix="/internship/leave-policies", tags=["实习请假审批配置"])


class ApprovalNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["GUIDE", "COLLEGE", "SCHOOL"]
    roleCode: str = Field(min_length=1, max_length=50)
    userId: str = Field(default="", pattern=r"^(?:[1-9][0-9]{0,18})?$")


class PolicyPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: list[ApprovalNode] = Field(min_length=1, max_length=3)


class PolicyPublish(PolicyPreview):
    expectedVersion: StrictInt = Field(ge=0)
    reason: str = Field(min_length=5, max_length=500)


class Handoff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batchId: str = Field(pattern=r"^[1-9][0-9]{0,18}$")
    userId: str = Field(pattern=r"^[1-9][0-9]{0,18}$")
    roleCode: str = Field(min_length=1, max_length=50)
    expectedVersion: StrictInt = Field(ge=0)
    reason: str = Field(min_length=5, max_length=500)


@router.get("/options")
def options(user=Depends(require_permission("internship.leave.policy.view"))):
    return success(service.available(user))


@router.get("/handoffs")
def handoffs(batchId: str, sourceId: str, page: int = Query(1, ge=1),
             pageSize: int = Query(30, ge=1, le=100), taskId: str = "",
             user=Depends(require_permission("internship.leave.handoff.view"))):
    return success(service.handoff_list(user, batchId, sourceId, page, pageSize, taskId))


@router.post("/handoffs/{task_id}")
def handoff(task_id: str, body: Handoff,
            user=Depends(require_permission("internship.leave.handoff.manage"))):
    return success(service.handoff(user, task_id, body.model_dump()))


@router.get("/{batch_id}")
def read(batch_id: str, user=Depends(require_permission("internship.leave.policy.view"))):
    return success(service.read(user, batch_id))


@router.post("/{batch_id}/preview")
def preview(batch_id: str, body: PolicyPreview,
            user=Depends(require_permission("internship.leave.policy.manage"))):
    return success(service.preview(user, batch_id, [node.model_dump() for node in body.nodes]))


@router.post("/{batch_id}/publish")
def publish(batch_id: str, body: PolicyPublish,
            user=Depends(require_permission("internship.leave.policy.manage"))):
    return success(service.publish(user, batch_id, body.model_dump()))
