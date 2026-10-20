"""Stable, domain-neutral contracts owned by PLAT-B."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProviderMode(str, Enum):
    NATIVE_ENGINE = "NATIVE_ENGINE"
    MATERIAL_POLICY = "MATERIAL_POLICY"
    EVIDENCE_ONLY = "EVIDENCE_ONLY"
    NOT_SUPPORTED = "NOT_SUPPORTED"


class ComplianceState(str, Enum):
    PASS = "PASS"
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    PENDING = "PENDING"
    NOT_EVALUATED = "NOT_EVALUATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EXEMPTED = "EXEMPTED"


class MaterialConstraintState(str, Enum):
    ENFORCED = "ENFORCED"
    UNSPECIFIED = "UNSPECIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PolicyRefBindingMode(str, Enum):
    PINNED = "PINNED"
    RESOLVE_ACTIVE = "RESOLVE_ACTIVE"


class SubjectRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    subject_type: str
    subject_id: str

    @field_validator("domain", "subject_type", "subject_id")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("subject reference values cannot be blank")
        return normalized


class PolicyRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_code: str
    authority_type: str
    authority_ref: str
    authority_version: str | None = None
    binding_mode: PolicyRefBindingMode = PolicyRefBindingMode.PINNED


class MaterialConstraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: MaterialConstraintState
    value: Any | None = None


class ComplianceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    state: ComplianceState
    applicable: bool
    required: bool
    severity: str
    reason: str | None = None
    policy_ref: PolicyRef | None = None
    evidence_ref: dict[str, Any] | None = None
    target: dict[str, Any] | None = None
    constraints: dict[str, MaterialConstraint] | None = None


class DomainComplianceAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_code: str
    provider_mode: ProviderMode
    subject_ref: SubjectRef
    operation: str
    policy_version: str | None = None
    items: list[ComplianceItem] = Field(default_factory=list)
    blocking: bool
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
