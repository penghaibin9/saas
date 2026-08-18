"""INT privileged baseline migration policy for historical Program versions.

Ordinary Program import must prove a complete v1 -> ... -> vN series and creates
DRAFT definitions. A legacy school may instead have only an already-approved vN
snapshot. Such a snapshot must never be laundered through ordinary import by
inventing v1/v2 predecessors or by treating (major, grade, version) as identity.

This module freezes the separate privileged migration evidence contract only. It
performs no database/file/audit writes and remains non-executable until the
shared Program series/formation schema and a privileged migration owner exist.
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping

from .academic_affairs_school_setup_import_contract import program_series_key

SCHEMA_PREREQUISITES = (
    "AaProgram.series_key",
    "AaProgramCourse.formation_mode",
)

MIGRATION_MODE = "PRIVILEGED_PROGRAM_BASELINE"
APPROVED_DECISION = "APPROVED"


def _required_text(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _positive_int(value: object, *, field: str) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def _aware_datetime(value: object, *, field: str) -> str:
    text = _required_text(value, field=field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include timezone offset")
    return parsed.isoformat()


def _approval_evidence(value: object) -> dict:
    if not isinstance(value, Mapping):
        raise ValueError("sourceApprovalEvidence must be an object")
    evidence = {
        "decision": _required_text(value.get("decision"), field="sourceApprovalEvidence.decision").upper(),
        "evidenceRef": _required_text(value.get("evidenceRef"), field="sourceApprovalEvidence.evidenceRef"),
        "approvedByRef": _required_text(value.get("approvedByRef"), field="sourceApprovalEvidence.approvedByRef"),
        "approvedAt": _aware_datetime(value.get("approvedAt"), field="sourceApprovalEvidence.approvedAt"),
    }
    if evidence["decision"] != APPROVED_DECISION:
        raise ValueError("sourceApprovalEvidence.decision must be APPROVED")
    return evidence


def build_program_baseline_migration_policy(evidence: Mapping[str, object]) -> dict:
    """Validate evidence for a historical non-v1 Program baseline.

    The returned object is intentionally a policy artifact, not a mutation plan.
    A later privileged owner must still rerun tenant-scoped reference/definition
    validation and write an audit record in the same transaction as migration.
    """
    if not isinstance(evidence, Mapping):
        raise ValueError("baseline migration evidence must be an object")

    # Privileged migration may bypass unavailable historical predecessors, never
    # the immutable Program series identity grammar used by ordinary program-v2.
    series_key = program_series_key(evidence.get("programSeriesKey"))
    baseline_version = _positive_int(evidence.get("baselineVersion"), field="baselineVersion")
    if baseline_version <= 1:
        raise ValueError("baselineVersion must be > 1; v1 belongs to ordinary Program import")

    source_system = _required_text(evidence.get("sourceSystem"), field="sourceSystem")
    source_record_id = _required_text(evidence.get("sourceRecordId"), field="sourceRecordId")
    source_approval = _approval_evidence(evidence.get("sourceApprovalEvidence"))
    effective_at = _aware_datetime(evidence.get("effectiveAt"), field="effectiveAt")
    audit_ticket = _required_text(evidence.get("auditTicket"), field="auditTicket")
    migration_reason = _required_text(evidence.get("migrationReason"), field="migrationReason")

    effective_dt = datetime.fromisoformat(effective_at)
    approved_dt = datetime.fromisoformat(source_approval["approvedAt"])
    if effective_dt < approved_dt:
        raise ValueError("effectiveAt must not precede source approval time")

    return {
        "mode": MIGRATION_MODE,
        "programSeriesKey": series_key,
        "baselineVersion": baseline_version,
        "ordinaryImportAllowed": False,
        "inventMissingPredecessorsAllowed": False,
        "naturalIdentityFallbackAllowed": False,
        "bindingIdentityFallbackAllowed": False,
        "sourceProvenance": {
            "sourceSystem": source_system,
            "sourceRecordId": source_record_id,
            "approval": source_approval,
            "effectiveAt": effective_at,
        },
        "audit": {
            "ticket": audit_ticket,
            "migrationReason": migration_reason,
            "requiredAction": "PROGRAM_BASELINE_MIGRATE",
        },
        "requiredValidation": [
            "TENANT_SCOPE",
            "EXACT_MAJOR_REFERENCE",
            "EXACT_COURSE_VERSION_REFERENCES",
            "FULL_DEFINITION_SNAPSHOT",
            "FORMATION_PROVENANCE",
            "SERIES_KEY_COLLISION",
            "BINDING_SCOPE_COLLISION",
        ],
        "sharedTransactionRequired": True,
        "appendOnlyAuditRequired": True,
        "executable": False,
        "schemaPrerequisites": list(SCHEMA_PREREQUISITES),
    }
