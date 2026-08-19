"""INT mutation-count invariants for Program import success receipts."""
from __future__ import annotations

import pytest


ROW_DIGEST = "a" * 64
DEF_HASH = "b" * 64
REL_HASH = "c" * 64


def _receipt():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_receipt as receipt
    return receipt


def _preview():
    return {"totalRows": 4, "validRows": 4, "invalidRows": 0}


def _definition(*, action: str, imported: int, reused: int) -> dict:
    return {
        "phase": "DEFINITION",
        "reconciliationSafe": True,
        "importedPrograms": imported,
        "reusedPrograms": reused,
        "rejectedPrograms": 0,
        "conflictPrograms": 0,
        "programCount": imported + reused,
        "items": [{
            "programKey": f"SERIES:SER-{index}:v1",
            "programId": str(500 + index),
            "action": action,
            "definitionHash": DEF_HASH,
            "rereadDefinitionHash": DEF_HASH,
            "hashMatch": True,
            "relationship": {"prevProgramId": "", "expectedPrevProgramId": ""},
        } for index in range(1, imported + reused + 1)],
        "errors": [],
    }


def _binding(*, created: int, reused: int) -> dict:
    actions = ["CREATE"] * created + ["REUSE"] * reused
    return {
        "phase": "BINDING",
        "reconciliationSafe": True,
        "createdBindings": created,
        "reusedBindings": reused,
        "bindingCount": created + reused,
        "activeRelationshipHash": REL_HASH,
        "items": [{
            "programKey": f"SERIES:SER-{index}:v1",
            "programId": str(500 + index),
            "scopeKey": f"MAJOR:{index}:GRADE:2026:MAJOR_GRADE",
            "action": action,
            "activeRelationshipMatch": True,
            "supersedeRelationshipMatch": True,
            "targetStatusMatch": True,
        } for index, action in enumerate(actions, 1)],
        "errors": [],
    }


def test_definition_reuse_only_receipt_rejects_any_domain_mutation():
    with pytest.raises(ValueError, match="REUSE-only Program reconciliation must have zero"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=_definition(action="REUSE", imported=0, reused=1),
            mutation_write_count=1,
        )


def test_binding_reuse_only_receipt_rejects_any_domain_mutation():
    with pytest.raises(ValueError, match="REUSE-only Program binding reconciliation must have zero"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=_binding(created=0, reused=1),
            mutation_write_count=1,
        )


@pytest.mark.parametrize(
    ("reconciliation", "message"),
    [
        (_definition(action="CREATE", imported=2, reused=0), "fewer domain mutations than imported Programs"),
        (_binding(created=2, reused=0), "fewer domain mutations than created bindings"),
    ],
)
def test_create_receipt_rejects_impossible_mutation_undercount(reconciliation, message):
    with pytest.raises(ValueError, match=message):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=reconciliation,
            mutation_write_count=1,
        )
