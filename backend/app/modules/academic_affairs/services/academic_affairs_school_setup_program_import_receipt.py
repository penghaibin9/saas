"""INT Program import result/receipt contract for Academic File Exchange.

The shared File Exchange owns the source FileObject, ImportJob, rowDigest,
expectedVersion lease, and SUCCEEDED replay behavior. Program domain code must
not invent a second digest/idempotency registry. Instead every new job is
revalidated and stable-key/full-definition reconciliation makes an identical
re-import a zero-write REUSE.

This pure module turns a successful Program post-confirm reconciliation into the
result_json payload the shared ImportJob may persist later. It never recomputes
the File Exchange rowDigest and never treats matching digest as permission to
skip authority checks.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping

from .academic_affairs_school_setup_program_binding_policy import (
    PHASE_BINDING,
    PHASE_DEFINITION,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _non_negative_int(value: object, *, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a non-negative integer") from exc
    if parsed < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return parsed


def _row_digest(value: object) -> str:
    digest = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(digest):
        raise ValueError("row_digest must be the shared File Exchange SHA-256 digest")
    return digest


def _sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _preview_counts(preview: Mapping[str, object]) -> tuple[int, int, int]:
    total = _non_negative_int(preview.get("totalRows") or 0, field="preview.totalRows")
    valid = _non_negative_int(preview.get("validRows") or 0, field="preview.validRows")
    invalid = _non_negative_int(preview.get("invalidRows") or 0, field="preview.invalidRows")
    if valid + invalid != total:
        raise ValueError("preview validRows + invalidRows must equal totalRows")
    return total, valid, invalid


def _require_successful_reconciliation(
    reconciliation: Mapping[str, object],
    *,
    expected_phase: str,
) -> dict:
    phase = str(reconciliation.get("phase") or "").strip().upper()
    if phase != expected_phase:
        raise ValueError(f"receipt requires {expected_phase} reconciliation")
    if not bool(reconciliation.get("reconciliationSafe")):
        raise ValueError("receipt requires successful authoritative reread reconciliation")
    if reconciliation.get("errors"):
        raise ValueError("successful reconciliation must not contain errors")
    return dict(reconciliation)


def build_program_import_receipt(
    *,
    row_digest: object,
    preview: Mapping[str, object],
    reconciliation: Mapping[str, object],
    mutation_write_count: object,
) -> dict:
    """Build deterministic result_json evidence for DEFINITION or BINDING confirm.

    ``mutation_write_count`` is supplied by the eventual transactional writer;
    it counts domain mutations, not processed workbook rows. This distinction is
    required for idempotency evidence because a repeated identical Program job
    can process all rows while performing zero writes.
    """
    digest = _row_digest(row_digest)
    total_rows, valid_rows, invalid_rows = _preview_counts(preview)
    if invalid_rows:
        raise ValueError("successful Program receipt cannot contain invalid preview rows")
    write_count = _non_negative_int(mutation_write_count, field="mutation_write_count")

    phase = str(reconciliation.get("phase") or "").strip().upper()
    if phase == PHASE_DEFINITION:
        evidence = _require_successful_reconciliation(
            reconciliation,
            expected_phase=PHASE_DEFINITION,
        )
        imported = _non_negative_int(
            evidence.get("importedPrograms") or 0,
            field="reconciliation.importedPrograms",
        )
        reused = _non_negative_int(
            evidence.get("reusedPrograms") or 0,
            field="reconciliation.reusedPrograms",
        )
        rejected = _non_negative_int(
            evidence.get("rejectedPrograms") or 0,
            field="reconciliation.rejectedPrograms",
        )
        conflicts = _non_negative_int(
            evidence.get("conflictPrograms") or 0,
            field="reconciliation.conflictPrograms",
        )
        program_count = _non_negative_int(
            evidence.get("programCount") or 0,
            field="reconciliation.programCount",
        )
        if imported + reused + rejected + conflicts != program_count:
            raise ValueError("Program reconciliation counts do not add up")
        if rejected or conflicts:
            raise ValueError("successful Program reconciliation cannot contain reject/conflict counts")

        items = [dict(item) for item in (evidence.get("items") or ())]
        if len(items) != program_count:
            raise ValueError("Program reconciliation item count mismatch")
        if any(not bool(item.get("hashMatch")) for item in items):
            raise ValueError("Program reconciliation receipt requires every definition hash to match")
        relationship_facts = [
            {
                "programKey": str(item.get("programKey") or ""),
                "programId": str(item.get("programId") or ""),
                "action": str(item.get("action") or "").upper(),
                "definitionHash": str(item.get("definitionHash") or ""),
                "prevProgramId": str((item.get("relationship") or {}).get("prevProgramId") or ""),
            }
            for item in items
        ]
        reconciliation_hash = _sha256(sorted(
            relationship_facts,
            key=lambda item: (item["programKey"], item["programId"]),
        ))
        replay_noop = bool(program_count > 0 and imported == 0 and reused == program_count and write_count == 0)
        return {
            "contractVersion": "program-import-receipt-v1",
            "phase": PHASE_DEFINITION,
            "sourceRowDigest": digest,
            "confirmedRows": total_rows,
            "processedRows": total_rows,
            "validRows": valid_rows,
            "invalidRows": 0,
            "importedPrograms": imported,
            "reusedPrograms": reused,
            "rejectedPrograms": 0,
            "conflictPrograms": 0,
            "programCount": program_count,
            "domainMutationWriteCount": write_count,
            "reconciliationHash": reconciliation_hash,
            "relationshipReconciled": True,
            "idempotency": {
                "sourceDigestOwner": "ACADEMIC_FILE_EXCHANGE",
                "crossJobDigestShortCircuit": False,
                "replayPolicy": "REVALIDATE_THEN_STABLE_KEY_REUSE",
                "stableKeyReconciliation": True,
                "fullDefinitionHashReconciliation": True,
                "replayNoOp": replay_noop,
            },
        }

    if phase == PHASE_BINDING:
        evidence = _require_successful_reconciliation(
            reconciliation,
            expected_phase=PHASE_BINDING,
        )
        created = _non_negative_int(
            evidence.get("createdBindings") or 0,
            field="reconciliation.createdBindings",
        )
        reused = _non_negative_int(
            evidence.get("reusedBindings") or 0,
            field="reconciliation.reusedBindings",
        )
        binding_count = _non_negative_int(
            evidence.get("bindingCount") or 0,
            field="reconciliation.bindingCount",
        )
        if created + reused != binding_count:
            raise ValueError("Program binding reconciliation counts do not add up")
        relationship_hash = str(evidence.get("activeRelationshipHash") or "").strip().lower()
        if not _SHA256_RE.fullmatch(relationship_hash):
            raise ValueError("BINDING reconciliation requires activeRelationshipHash")
        items = [dict(item) for item in (evidence.get("items") or ())]
        if len(items) != binding_count:
            raise ValueError("Program binding reconciliation item count mismatch")
        if any(
            not bool(item.get("activeRelationshipMatch"))
            or not bool(item.get("supersedeRelationshipMatch"))
            or not bool(item.get("targetStatusMatch"))
            for item in items
        ):
            raise ValueError("Program binding receipt requires every relationship reread to match")
        replay_noop = bool(binding_count > 0 and created == 0 and reused == binding_count and write_count == 0)
        return {
            "contractVersion": "program-import-receipt-v1",
            "phase": PHASE_BINDING,
            "sourceRowDigest": digest,
            "confirmedRows": total_rows,
            "processedRows": total_rows,
            "validRows": valid_rows,
            "invalidRows": 0,
            "createdBindings": created,
            "reusedBindings": reused,
            "bindingCount": binding_count,
            "domainMutationWriteCount": write_count,
            "reconciliationHash": relationship_hash,
            "relationshipReconciled": True,
            "idempotency": {
                "sourceDigestOwner": "ACADEMIC_FILE_EXCHANGE",
                "crossJobDigestShortCircuit": False,
                "replayPolicy": "REVALIDATE_THEN_STABLE_KEY_REUSE",
                "stableKeyReconciliation": True,
                "fullDefinitionHashReconciliation": True,
                "replayNoOp": replay_noop,
            },
        }

    raise ValueError(f"unsupported Program receipt phase: {phase}")
