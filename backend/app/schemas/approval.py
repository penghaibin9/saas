"""审批任务 DTO。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ApprovalActionRequest(BaseModel):
    comment: Optional[str] = Field(None, description="审批意见（通过时可选）")
    version: int = Field(..., ge=0, description="乐观锁版本，必填")


class ApprovalRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="驳回原因（必填；最小长度由平台规则中心决定）")
    version: int = Field(..., ge=0, description="乐观锁版本，必填")


class ApprovalReturnRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="退回修改原因（必填；与驳回终止语义严格区分）")
    version: int = Field(..., ge=0, description="乐观锁版本，必填")


class ApprovalTransferRequest(BaseModel):
    targetUserId: str = Field(..., min_length=1, description="转办目标用户")
    comment: Optional[str] = Field(None, description="转办说明")
    version: int = Field(..., ge=0, description="乐观锁版本，必填")


class ApprovalResubmitRequest(BaseModel):
    version: int = Field(..., ge=0, description="审批实例乐观锁版本")
    comment: Optional[str] = Field(None, description="重新提交说明")


class ApprovalBatchItem(BaseModel):
    taskId: str = Field(..., min_length=1)
    version: int = Field(..., ge=0)


class ApprovalBatchRequest(BaseModel):
    action: str = Field(..., description="APPROVE/RETURN/REJECT/TRANSFER")
    items: list[ApprovalBatchItem] = Field(..., min_length=1, max_length=100)
    reason: Optional[str] = None
    comment: Optional[str] = None
    targetUserId: Optional[str] = None


class ApprovalTemplateNodeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    role: str = Field(..., min_length=1, max_length=50)
    sla: int = Field(..., ge=1, le=720)
    nodeCode: Optional[str] = Field(None, max_length=100)


class ApprovalTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    bizType: str = Field(..., min_length=1, max_length=100)
    nodes: list[ApprovalTemplateNodeRequest] = Field(..., min_length=1, max_length=30)


class ApprovalTemplateUpdateRequest(ApprovalTemplateCreateRequest):
    version: int = Field(..., ge=0, description="模板行乐观锁版本")


class ApprovalTemplateVoidRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)
    version: int = Field(..., ge=0)


class ApprovalExportRequest(BaseModel):
    scope: str = Field(..., description="TODO/DONE/RETURNED/CC/TEMPLATE")
    purpose: str = Field(..., min_length=5, max_length=200)


class ApprovalExportTicketRequest(BaseModel):
    expectedVersion: int = Field(..., ge=0, description="导出任务乐观锁版本")
