"""毕业设计补充请求 DTO。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ProposalDefenseBody(BaseModel):
    result: Literal["PASS", "FAIL"]
    comment: Optional[str] = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def require_fail_comment(self):
        if self.result == "FAIL" and len((self.comment or "").strip()) < 5:
            raise ValueError("开题答辩不通过时评语必填且不少于 5 字")
        return self
