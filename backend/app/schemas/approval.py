"""审批任务 DTO。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ApprovalActionRequest(BaseModel):
    comment: Optional[str] = Field(None, description="审批意见（通过时可选）")


class ApprovalRejectRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="驳回原因（必填 ≥5 字，冻结册 §1.4）")


class ApprovalTransferRequest(BaseModel):
    targetUserId: str = Field(..., description="转办目标用户")
    comment: Optional[str] = Field(None, description="转办说明")
