from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


FocusMode = Literal["DETAIL", "LIST_FOCUS", "NONE"]
SearchClient = Literal["pc", "studentPc", "teacherMini", "studentMini"]


@dataclass(frozen=True, slots=True)
class NavigationTarget:
    """Server-authored, client-specific destination.

    Providers return this value and never assemble a raw URL themselves.
    ``exact=False`` is required whenever the resolver can prove only a list or
    safe module landing page.
    """

    route_name: str | None
    route_params: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)
    path: str | None = None
    focus_mode: FocusMode = "NONE"
    exact: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "routeName": self.route_name,
            "routeParams": dict(self.route_params),
            "query": dict(self.query),
            "path": self.path,
            "focusMode": self.focus_mode,
            "exact": self.exact,
        }


@dataclass(frozen=True, slots=True)
class SearchContext:
    tenant_id: int
    actor: dict[str, Any]
    keyword: str
    client: SearchClient = "pc"
    limit: int = 10


class SearchHit(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider: str
    type: str
    object_id: str
    dedupe_key: str
    title: str
    secondary: str | None = None
    module_code: str
    status: str | None = None
    badges: list[str] = Field(default_factory=list)
    target: NavigationTarget | None = None
    allowed_actions: list[str] = Field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        value = self.model_dump(exclude={"target"})
        value.update({
            "objectId": value.pop("object_id"),
            "dedupeKey": value.pop("dedupe_key"),
            "moduleCode": value.pop("module_code"),
            "allowedActions": value.pop("allowed_actions"),
            "target": self.target.as_dict() if self.target else None,
        })
        return value


class ProviderError(BaseModel):
    provider: str
    code: Literal["TIMEOUT", "FAILED", "DENIED"]


class SearchFederationResult(BaseModel):
    hits: list[SearchHit] = Field(default_factory=list)
    provider_errors: list[ProviderError] = Field(default_factory=list)
    partial: bool = False
    elapsed_ms: int = 0
