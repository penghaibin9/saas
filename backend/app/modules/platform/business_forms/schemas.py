"""Contracts for immutable schema-assisted form versions."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.platform.compliance_federation.schemas import PolicyRef


class FormClient(str, Enum):
    STAFF_PC = "STAFF_PC"
    STUDENT_PC = "STUDENT_PC"
    TEACHER_MINIAPP = "TEACHER_MINIAPP"
    STUDENT_MINIAPP = "STUDENT_MINIAPP"


class FormFieldType(str, Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    SELECT = "select"
    DATE = "date"
    DATETIME = "datetime"
    FILE = "file"
    STUDENT_PICKER = "student-picker"


class SelectOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: str | int | float | bool


class FormFieldDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    code: str
    type: FormFieldType
    label: str
    help_text: str | None = Field(default=None, alias="helpText")
    placeholder: str | None = None
    required: bool = False
    readonly: bool = False
    multiple: bool = False
    min_value: float | None = Field(default=None, alias="min")
    max_value: float | None = Field(default=None, alias="max")
    max_length: int | None = Field(default=None, alias="maxLength")
    options: list[SelectOption] = Field(default_factory=list)
    visible_when: dict[str, Any] | None = Field(default=None, alias="visibleWhen")
    required_when: dict[str, Any] | None = Field(default=None, alias="requiredWhen")
    readonly_when: dict[str, Any] | None = Field(default=None, alias="readonlyWhen")


class BusinessFormVersionDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    form_code: str
    version_id: int
    version_no: int
    schema_hash: str
    schema_version: str
    supported_clients: set[FormClient]
    policy_refs: list[PolicyRef] = Field(default_factory=list)
    domain_data_adapter: str
    domain_command_adapter: str
    fields: list[FormFieldDefinition]
    conditions: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("form_code", "schema_version", "domain_data_adapter", "domain_command_adapter")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("value cannot be blank")
        return normalized
