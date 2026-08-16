"""INT contract for Program File Exchange result/replay receipts."""
from __future__ import annotations

import inspect

import pytest


def _receipt():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_receipt as receipt
    return receipt


ROW_DIGEST = "a" * 64
DEF_HASH = "b" * 64
REL_HASH = "c" * 64


def _preview():
    return {
        "totalRows": 4,
        "validRows": 4,
        "invalidRows": 0,
    }


def _definition_reconciliation(*, action="CREATE", imported=1, reused=0):
    return {
        "phase": "DEFINITION",
        "reconciliationSafe": True,
        "importedPrograms": imported,
        "reusedPrograms": reused,
        "rejectedPrograms": 0,
        "conflictPrograms": 0,
        "programCount": 1,
        "items": [{
            "programKey": "SERIES:SER-A:v1",
            "programId": "501",
            "action": action,
            "definitionHash": DEF_HASH,
            "rereadDefinitionHash": DEF_HASH,
            "hashMatch": True,
            "relationship": {
                "prevProgramId": "",
                "expectedPrevProgramId": "",
            },
        }],
        "errors": [],
    }


def test_definition_receipt_separates_processed_rows_from_domain_writes():
    result = _receipt().build_program_import_receipt(
        row_digest=ROW_DIGEST,
        preview=_preview(),
        reconciliation=_definition_reconciliation(),
        mutation_write_count=4,
    )
    assert result["contractVersion"] == "program-import-receipt-v1"
    assert result["phase"] == "DEFINITION"
    assert result["sourceRowDigest"] == ROW_DIGEST
    assert result["confirmedRows"] == 4
    assert result["processedRows"] == 4
    assert result["importedPrograms"] == 1
    assert result["reusedPrograms"] == 0
    assert result["domainMutationWriteCount"] == 4
    assert result["relationshipReconciled"] is True
    assert len(result["reconciliationHash"]) == 64
    assert result["idempotency"] == {
        "sourceDigestOwner": "ACADEMIC_FILE_EXCHANGE",
        "crossJobDigestShortCircuit": False,
        "replayPolicy": "REVALIDATE_THEN_STABLE_KEY_REUSE",
        "stableKeyReconciliation": True,
        "fullDefinitionHashReconciliation": True,
        "replayNoOp": False,
    }


def test_identical_new_job_is_revalidated_then_full_definition_reuse_zero_write():
    # Matching rowDigest alone never short-circuits a new ImportJob. After the
    # normal authority preflight/reread sees the exact same stable definition,
    # all Programs are REUSE and the domain mutation count is zero.
    result = _receipt().build_program_import_receipt(
        row_digest=ROW_DIGEST,
        preview=_preview(),
        reconciliation=_definition_reconciliation(
            action="REUSE",
            imported=0,
            reused=1,
        ),
        mutation_write_count=0,
    )
    assert result["confirmedRows"] == 4
    assert result["importedPrograms"] == 0
    assert result["reusedPrograms"] == 1
    assert result["domainMutationWriteCount"] == 0
    assert result["idempotency"]["crossJobDigestShortCircuit"] is False
    assert result["idempotency"]["replayPolicy"] == "REVALIDATE_THEN_STABLE_KEY_REUSE"
    assert result["idempotency"]["replayNoOp"] is True


def test_binding_receipt_uses_authoritative_relationship_hash_and_can_be_noop_reuse():
    reconciliation = {
        "phase": "BINDING",
        "reconciliationSafe": True,
        "createdBindings": 0,
        "reusedBindings": 1,
        "bindingCount": 1,
        "activeRelationshipHash": REL_HASH,
        "items": [{
            "programKey": "SERIES:SER-A:v1",
            "programId": "501",
            "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
            "action": "REUSE",
            "activeRelationshipMatch": True,
            "supersedeRelationshipMatch": True,
            "targetStatusMatch": True,
        }],
        "errors": [],
    }
    result = _receipt().build_program_import_receipt(
        row_digest=ROW_DIGEST,
        preview=_preview(),
        reconciliation=reconciliation,
        mutation_write_count=0,
    )
    assert result["phase"] == "BINDING"
    assert result["createdBindings"] == 0
    assert result["reusedBindings"] == 1
    assert result["reconciliationHash"] == REL_HASH
    assert result["domainMutationWriteCount"] == 0
    assert result["idempotency"]["replayNoOp"] is True


@pytest.mark.parametrize("digest", ["", "abc", "g" * 64, "a" * 63])
def test_receipt_never_accepts_non_file_exchange_sha256_digest(digest):
    with pytest.raises(ValueError, match="shared File Exchange SHA-256"):
        _receipt().build_program_import_receipt(
            row_digest=digest,
            preview=_preview(),
            reconciliation=_definition_reconciliation(),
            mutation_write_count=4,
        )


def test_receipt_fails_closed_on_invalid_preview_or_reconciliation_evidence():
    with pytest.raises(ValueError, match="must equal totalRows"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview={"totalRows": 4, "validRows": 3, "invalidRows": 0},
            reconciliation=_definition_reconciliation(),
            mutation_write_count=4,
        )

    unsafe = _definition_reconciliation()
    unsafe["reconciliationSafe"] = False
    unsafe["errors"] = [{"businessCode": "DRIFT"}]
    with pytest.raises(ValueError, match="successful authoritative reread reconciliation"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=unsafe,
            mutation_write_count=4,
        )

    hash_drift = _definition_reconciliation()
    hash_drift["items"][0]["hashMatch"] = False
    with pytest.raises(ValueError, match="every definition hash to match"):
        _receipt().build_program_import_receipt(
            row_digest=ROW_DIGEST,
            preview=_preview(),
            reconciliation=hash_drift,
            mutation_write_count=4,
        )


def test_receipt_is_not_a_second_job_digest_or_idempotency_store():
    source = inspect.getsource(_receipt())
    assert "_row_digest(rows" not in source
    assert "get_sessionmaker" not in source
    assert "ImportJob(" not in source
    assert "FileObject(" not in source
    assert "idempotency_key" not in source
    assert "db.add" not in source
    assert "db.commit" not in source
    assert "data_exchange_confirm_service" not in source
    assert "data_exchange_confirm_legacy" not in source
