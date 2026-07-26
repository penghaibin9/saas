"""毕业设计中心 · 答辩评分请求 DTO。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class DefenseScoreEntryRequest(BaseModel):
    gdStudentId: str
    judgeName: str = Field(..., min_length=1)
    expertId: Optional[str] = None
    score: Optional[int] = Field(None, ge=0, le=100)
    comment: Optional[str] = None
    absent: bool = Field(default=False)
    absentReason: Optional[str] = None

    @model_validator(mode="after")
    def validate_attendance_score(self):
        if self.absent:
            if not (self.absentReason or "").strip():
                raise ValueError("评委缺席时必须填写 absentReason")
            if self.score is not None:
                raise ValueError("评委缺席时不得填写 score")
        elif self.score is None:
            raise ValueError("非缺席评委必须填写 score")
        return self


class SecondDefenseRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="二次答辩原因，至少 5 字")


class DefenseConfirmationRevokeRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="撤回答辩确认原因，至少 5 字")
