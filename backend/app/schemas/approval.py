"""审批任务 DTO。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ApprovalActionRequest(BaseModel):
    comment: Optional[str] = Field(None, description="审批意见（通过时可选）")
    version: int = Field(..., description="乐观锁版本，必填")


class ApprovalRejectRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="驳回原因（必填；最小长度由平台规则中心 approval.rejectReasonMinLength 决定，默认 5）")
    version: int = Field(..., description="乐观锁版本，必填")


class ApprovalTransferRequest(BaseModel):
    targetUserId: str = Field(..., description="转办目标用户")
    comment: Optional[str] = Field(None, description="转办说明")
    version: int = Field(..., description="乐观锁版本，必填")
