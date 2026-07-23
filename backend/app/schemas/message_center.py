"""消息中心 schemas（收件端 + 发布端最小契约）。"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class MessageReadAllBody(BaseModel):
    category: Optional[str] = None
    readState: Optional[str] = Field(default="UNREAD", description="仅对未读生效")
    priority: Optional[str] = None
    requestId: Optional[str] = None


class MessageReceiptBody(BaseModel):
    requestId: Optional[str] = None


class AudienceRuleIn(BaseModel):
    type: str = Field(..., description="CLASS/COLLEGE/ALL_STUDENT/...")
    includeOrExclude: str = Field(default="INCLUDE")
    targetIds: list[int] = Field(default_factory=list)
    targetCodes: list[str] = Field(default_factory=list)
    includeChildren: bool = True


class CampaignDraftBody(BaseModel):
    title: str = Field(..., min_length=4, max_length=100)
    contentPlain: str = Field(..., min_length=1)
    summary: Optional[str] = Field(default=None, max_length=120)
    category: str = Field(default="ANNOUNCEMENT")
    priority: str = Field(default="NORMAL")
    requireAck: bool = False
    pinned: bool = False
    emergency: bool = False
    publishMode: str = Field(default="IMMEDIATE")
    scheduledAt: Optional[str] = None
    effectiveAt: Optional[str] = None
    expireAt: Optional[str] = None
    ackDeadlineAt: Optional[str] = None
    contentHtml: Optional[str] = None
    actionKey: Optional[str] = None
    actionParams: Optional[dict[str, Any]] = None
    audiences: list[AudienceRuleIn] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=lambda: ["IN_APP"])
    idempotencyKey: Optional[str] = None
    requestId: Optional[str] = None
    version: Optional[int] = None


class CampaignAttachmentBody(BaseModel):
    fileId: int
    fileName: Optional[str] = None
    requestId: Optional[str] = None


class AudiencePreviewBody(BaseModel):
    audiences: list[AudienceRuleIn] = Field(default_factory=list)
    recipientTypes: list[str] = Field(default_factory=lambda: ["STUDENT"])


class CampaignPublishBody(BaseModel):
    previewToken: str
    audienceFingerprint: str
    version: int
    idempotencyKey: Optional[str] = None
    requestId: Optional[str] = None


class CampaignWithdrawBody(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)
    version: int
    requestId: Optional[str] = None


class CampaignReviewBody(BaseModel):
    version: int
    comment: Optional[str] = None
    reason: Optional[str] = Field(default=None, description="退回原因")
    requestId: Optional[str] = None
