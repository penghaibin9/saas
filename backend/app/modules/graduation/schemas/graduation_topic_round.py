"""毕业设计中心 · 选题轮次/志愿 DTO。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class GdTopicRoundCreate(BaseModel):
    roundName: str = Field(..., min_length=2, max_length=100)
    batchId: Optional[str] = None
    roundNo: int = Field(default=1, ge=1)
    maxChoices: int = Field(default=3, ge=1, le=10)
    startAt: Optional[str] = None
    endAt: Optional[str] = None
    collegeScope: Optional[str] = None
    remark: Optional[str] = None


class GdTopicChoiceItem(BaseModel):
    topicId: str
    choiceOrder: int = Field(..., ge=1, le=10)


class GdTopicChoiceSubmit(BaseModel):
    gdStudentId: str
    choices: list[GdTopicChoiceItem] = Field(..., min_length=1)


class GdTopicChoiceReview(BaseModel):
    reason: Optional[str] = None
