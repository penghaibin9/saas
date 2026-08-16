"""INT non-empty and uniqueness invariants for Program success receipts."""
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


def _definition_item(program_key="SERIES:SER-A:v1", program_id="501"):
    return {
        "programKey": program_key,
        "programId": program_id,
        "action": "CREATE",
        "definitionHash": DEF_HASH,
        "rereadDefinitionHash": DEF_HASH,
        "hashMatch": True,
        "relationship": {"prevProgramId": "", "expectedPrevProgramId": ""},
    }


def _definition(items):
    return {
        "phase": "DEFINITION",
        "reconciliationSafe": True,
        "importedPrograms": len(items),
        "reusedPrograms": 0,
        "rejectedPrograms": 0,
        "conflictPrograms": 0,
        "programCount": len(items),
        "items": items,
        "errors": [],
    }


def _binding_item(program_key="SERIES:SER-A:v1", program_id="501", scope_key="MAJOR:10:GRADE:2026:MAJOR_GRADE"):
    return {
        "programKey": program_key,
        "programId": program_id,
        "scopeKey": scope_key,
        "action": "CREATE",
        "activeRelationshipMatch": True,
        "supersedeRelationshipMatch": True,
        "targetStatusMatch": True,
    }


def test_success_receipt_rejects_zero_validated_source_rows():
    with pytest.raises(ValueError, match="requires at least one validated source row"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview={"totalRows": 0, "validRows": 0, "invalidRows": 0},
            reconciliation=_definition([_definition_item()]),
            mutation_write_count=1,
        )


def test_success_receipt_rejects_zero_program_or_binding_projection():
    empty_definition = _definition([])
    with pytest.raises(ValueError, match="requires at least one Program"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=empty_definition,
            mutation_write_count=0,
        )

    empty_binding = {
        "phase": "BINDING",
        "reconciliationSafe": True,
        "createdBindings": 0,
        "reusedBindings": 0,
        "bindingCount": 0,
        "activeRelationshipHash": REL_HASH,
        "items": [],
        "errors": [],
    }
    with pytest.raises(ValueError, match="requires at least one binding"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=empty_binding,
            mutation_write_count=0,
        )


def test_definition_receipt_rejects_duplicate_program_key_or_program_id():
    duplicate_key = _definition([
        _definition_item("SERIES:SER-A:v1", "501"),
        _definition_item("SERIES:SER-A:v1", "502"),
    ])
    with pytest.raises(ValueError, match="duplicate programKey"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=duplicate_key,
            mutation_write_count=2,
        )

    duplicate_id = _definition([
        _definition_item("SERIES:SER-A:v1", "501"),
        _definition_item("SERIES:SER-B:v1", "501"),
    ])
    with pytest.raises(ValueError, match="duplicate programId"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=duplicate_id,
            mutation_write_count=2,
        )


def test_binding_receipt_rejects_duplicate_scope_key():
    scope = "MAJOR:10:GRADE:2026:MAJOR_GRADE"
    items = [
        _binding_item("SERIES:SER-A:v1", "501", scope),
        _binding_item("SERIES:SER-B:v1", "502", scope),
    ]
    reconciliation = {
        "phase": "BINDING",
        "reconciliationSafe": True,
        "createdBindings": 2,
        "reusedBindings": 0,
        "bindingCount": 2,
        "activeRelationshipHash": REL_HASH,
        "items": items,
        "errors": [],
    }
    with pytest.raises(ValueError, match="duplicate scopeKey"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=reconciliation,
            mutation_write_count=2,
        )
