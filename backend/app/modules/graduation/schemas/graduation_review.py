"""毕业设计中心 · 查重记录 / 教师评阅 请求 DTO。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PlagiarismSubmitRequest(BaseModel):
    gdFinalId: Optional[str] = None


class PlagiarismResultRequest(BaseModel):
    rate: str = Field(..., description="重复率，如 12.5")
    reportUrl: Optional[str] = None


class PlagiarismDisputeRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="复查申请理由，至少 5 字")


class PlagiarismDisputeReview(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    comment: Optional[str] = None


class ReviewAssignRequest(BaseModel):
    gdStudentId: str
    reviewerName: Optional[str] = Field(default=None, description="评阅人姓名快照（有 reviewerMentorId 时可空）")
    reviewerMentorId: Optional[int] = Field(default=None, description="评阅人→t_gd_mentor.id（优先）")
    gdFinalId: Optional[str] = None


class ReviewSubmitRequest(BaseModel):
    score: int = Field(..., ge=0, le=100)
    opinion: str = Field(..., min_length=2, max_length=2000)


class ReviewReturnRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="退回原因，至少 5 字")
