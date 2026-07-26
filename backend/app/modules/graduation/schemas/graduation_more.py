"""毕业设计互查、专家与申诉写请求 DTO。"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PeerAssignRequest(BaseModel):
    gdStudentId: str
    reviewerGdStudentId: str


class PeerSubmitRequest(BaseModel):
    opinion: str = Field(..., min_length=5)


class PeerRectifyRequest(BaseModel):
    note: str = Field(..., min_length=5)


class ExpertCreateRequest(BaseModel):
    expertName: str = Field(..., min_length=1)
    title: Optional[str] = None
    collegeName: Optional[str] = None
    isExternal: bool = False
    avoidNote: Optional[str] = None


class ExpertStatusRequest(BaseModel):
    action: Literal["ENABLE", "DISABLE"]


class AppealReviewRequest(BaseModel):
    action: Literal["APPROVE", "REJECT"]
    comment: Optional[str] = None


class DefenseNotifyRequest(BaseModel):
    defenseGroupId: str
