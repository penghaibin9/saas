"""INT evidence-integrity contracts for Program import success receipts."""
from __future__ import annotations

import copy

import pytest


ROW_DIGEST = "a" * 64
DEF_HASH = "b" * 64
REL_HASH = "c" * 64


def _receipt():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_receipt as receipt
    return receipt


def _preview():
    return {"totalRows": 4, "validRows": 4, "invalidRows": 0}


def _definition(*, action="CREATE", imported=1, reused=0):
    return {
        "phase": "DEFINITION",
        "reconciliationSafe": True,
        "importedPrograms": imported,
        "reusedPrograms": reused,
        "rejectedPrograms": 0,
        "conflictPrograms": 0,
        "programCount": imported + reused,
        "items": [{
            "programKey": "SERIES:SER-A:v1",
            "programId": "501",
            "action": action,
            "definitionHash": DEF_HASH,
            "rereadDefinitionHash": DEF_HASH,
            "hashMatch": True,
            "relationship": {"prevProgramId": "", "expectedPrevProgramId": ""},
        }],
        "errors": [],
    }


def _binding(*, action="CREATE", created=1, reused=0):
    return {
        "phase": "BINDING",
        "reconciliationSafe": True,
        "createdBindings": created,
        "reusedBindings": reused,
        "bindingCount": created + reused,
        "activeRelationshipHash": REL_HASH,
        "items": [{
            "programKey": "SERIES:SER-A:v1",
            "programId": "501",
            "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
            "action": action,
            "activeRelationshipMatch": True,
            "supersedeRelationshipMatch": True,
            "targetStatusMatch": True,
        }],
        "errors": [],
    }


def test_definition_receipt_rejects_item_action_count_drift():
    reconciliation = _definition(action="REUSE", imported=1, reused=0)
    with pytest.raises(ValueError, match="item actions do not match imported/reused counts"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=reconciliation,
            mutation_write_count=1,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("programKey", "", "requires programKey/programId"),
        ("programId", "", "requires programKey/programId"),
        ("definitionHash", "", "requires SHA-256 definition hashes"),
        ("rereadDefinitionHash", "x" * 64, "requires SHA-256 definition hashes"),
    ],
)
def test_definition_receipt_rejects_missing_identity_or_invalid_hash_evidence(field, value, message):
    reconciliation = _definition()
    reconciliation["items"][0][field] = value
    with pytest.raises(ValueError, match=message):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=reconciliation,
            mutation_write_count=1,
        )


def test_definition_receipt_rejects_hash_drift_even_when_hash_match_flag_is_true():
    reconciliation = _definition()
    reconciliation["items"][0]["rereadDefinitionHash"] = "d" * 64
    reconciliation["items"][0]["hashMatch"] = True
    with pytest.raises(ValueError, match="every definition hash to match"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=reconciliation,
            mutation_write_count=1,
        )


def test_binding_receipt_rejects_item_action_count_drift():
    reconciliation = _binding(action="REUSE", created=1, reused=0)
    with pytest.raises(ValueError, match="item actions do not match created/reused counts"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=reconciliation,
            mutation_write_count=1,
        )


@pytest.mark.parametrize("field", ["programKey", "programId", "scopeKey"])
def test_binding_receipt_requires_complete_relationship_identity(field):
    reconciliation = _binding()
    reconciliation["items"][0][field] = ""
    with pytest.raises(ValueError, match="requires programKey/programId/scopeKey"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=reconciliation,
            mutation_write_count=1,
        )


def test_receipt_rejects_unsupported_item_actions_in_both_phases():
    definition = _definition()
    definition["items"][0]["action"] = "UPSERT"
    with pytest.raises(ValueError, match="unsupported action: UPSERT"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=definition,
            mutation_write_count=1,
        )

    binding = copy.deepcopy(_binding())
    binding["items"][0]["action"] = "SUPERSEDE"
    with pytest.raises(ValueError, match="unsupported action: SUPERSEDE"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=binding,
            mutation_write_count=1,
        )
