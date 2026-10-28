"""Shared PC/mobile guidance and per-student batch contract."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class GuidanceFields(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    batchId: int = Field(gt=0)
    guidanceDate: str = Field(pattern=r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$', strict=True)
    method: Literal['ONLINE', 'PHONE', 'ONSITE', 'ENTERPRISE_FEEDBACK', 'VIDEO']
    content: str = Field(min_length=2, max_length=8000, strict=True)
    topic: str | None = Field(default=None, max_length=200)
    problemType: str | None = Field(default=None, max_length=50)
    suggestion: str | None = Field(default=None, max_length=1000)
    nextFollowDate: str | None = Field(default=None, pattern=r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
    toRisk: StrictBool = False
    notifyCounselor: StrictBool = False

    @field_validator('topic', 'problemType', 'suggestion', 'nextFollowDate', mode='before')
    @classmethod
    def empty_optional(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator('guidanceDate', 'nextFollowDate')
    @classmethod
    def valid_date(cls, value):
        if value is not None:
            date.fromisoformat(value)
        return value


class GuidanceTarget(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    internshipId: str = Field(pattern=r'^[0-9]{1,19}$', strict=True)
    requestKey: str = Field(pattern=r'^[A-Za-z0-9_-]{16,64}$', strict=True)
    fileId: str | None = Field(default=None, pattern=r'^[0-9]{1,19}$', strict=True)

    @field_validator('fileId', mode='before')
    @classmethod
    def empty_file(cls, value):
        return None if value == '' else value


class GuidanceCreate(GuidanceFields, GuidanceTarget):
    pass


class GuidanceBatch(GuidanceFields):
    items: list[GuidanceTarget] = Field(min_length=1, max_length=100)

    @field_validator('items')
    @classmethod
    def distinct_students(cls, items):
        if len({item.internshipId for item in items}) != len(items):
            raise ValueError('同一批量操作不能重复选择学生')
        return items
