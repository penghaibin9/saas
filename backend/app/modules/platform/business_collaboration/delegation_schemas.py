from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TodoDelegationCreateRequest(BaseModel):
    delegate_user_id: int = Field(gt=0)
    scope_type: str
    scope: dict = Field(default_factory=dict)
    effective_from: datetime
    effective_until: datetime
    reason: str = Field(min_length=2, max_length=500)


class TodoDelegationRevokeRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


class TodoDelegationView(BaseModel):
    delegation_id: str
    delegator_user_id: str
    delegate_user_id: str
    scope_type: str
    effective_from: datetime
    effective_until: datetime
    status: str
    revoked_at: datetime | None = None


class ActingAuthorizationView(BaseModel):
    delegation_id: str
    actor_user_id: str
    on_behalf_of_user_id: str
    action: str


class SlaProjection(BaseModel):
    state: str
    due_at: datetime | None = None
    source: str
    remaining_seconds: int | None = None
