"""毕业设计中心 · 题目库请求 DTO。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class GdTopicCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=300)
    batchId: Optional[str] = None
    topicNo: Optional[str] = None
    sourceType: str = Field(default="TEACHER", description="TEACHER/ENTERPRISE/STUDENT/ADMIN")
    advisorName: Optional[str] = None
    collegeId: Optional[str] = None
    majorId: Optional[str] = None
    majorName: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    enterpriseName: Optional[str] = None
    requirements: Optional[str] = None
    outcome: Optional[str] = None
    skills: Optional[str] = None
    capacity: int = Field(default=1, ge=1, le=99)
    attachments: Optional[list[dict]] = None
    submitReview: bool = Field(default=False, description="创建后是否直接提交审核")


class GdTopicUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=300)
    batchId: Optional[str] = None
    topicNo: Optional[str] = None
    advisorName: Optional[str] = None
    collegeId: Optional[str] = None
    majorId: Optional[str] = None
    majorName: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    enterpriseName: Optional[str] = None
    requirements: Optional[str] = None
    outcome: Optional[str] = None
    skills: Optional[str] = None
    capacity: Optional[int] = Field(None, ge=1, le=99)
    attachments: Optional[list[dict]] = None


class GdTopicReviewRequest(BaseModel):
    action: Literal["APPROVE", "REJECT"]
    comment: Optional[str] = ""


class GdTopicDisableRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=300)


class GdTopicArchiveRequest(BaseModel):
    reason: Optional[str] = ""


class GdTopicAttachmentsUpdate(BaseModel):
    attachments: list[dict] = Field(default_factory=list, description="附件元数据 [{name,url,size,uploadedAt}]")


class GdTopicCapacityUpdate(BaseModel):
    capacity: int = Field(..., ge=1, le=99)
