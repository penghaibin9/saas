from __future__ import annotations

from pydantic import BaseModel, Field


class TodoClaimRequest(BaseModel):
    expected_version: int = Field(ge=0)


class TodoReleaseRequest(BaseModel):
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=2, max_length=500)


class TodoAssignmentView(BaseModel):
    assignment_id: str
    todo_id: str
    assignment_type: str
    owner_user_id: str
    status: str
    claimed_at: str | None = None
    released_at: str | None = None


class EffectiveOwnerView(BaseModel):
    ownership_mode: str
    owner_user_id: str | None = None
    assignment_id: str | None = None
