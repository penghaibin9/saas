"""INT contract for privileged historical Program baseline migration evidence."""
from __future__ import annotations

import inspect

import pytest


def _policy():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_baseline_migration_policy as policy
    return policy


def _evidence(**overrides):
    value = {
        "programSeriesKey": "CS-SOFT",
        "baselineVersion": 3,
        "sourceSystem": "LEGACY_SIS",
        "sourceRecordId": "program-2026-soft-v3",
        "sourceApprovalEvidence": {
            "decision": "APPROVED",
            "evidenceRef": "legacy-approval-8891",
            "approvedByRef": "legacy-user-1008",
            "approvedAt": "2026-01-10T09:30:00+08:00",
        },
        "effectiveAt": "2026-02-01T00:00:00+08:00",
        "auditTicket": "MIG-2026-00017",
        "migrationReason": "旧教务系统只保留已批准的 V3 当前方案，历史 V1/V2 不可证明",
    }
    value.update(overrides)
    return value


def test_v3_only_baseline_is_privileged_non_executable_and_never_invents_history():
    result = _policy().build_program_baseline_migration_policy(_evidence())
    assert result["mode"] == "PRIVILEGED_PROGRAM_BASELINE"
    assert result["programSeriesKey"] == "CS-SOFT"
    assert result["baselineVersion"] == 3
    assert result["ordinaryImportAllowed"] is False
    assert result["inventMissingPredecessorsAllowed"] is False
    assert result["naturalIdentityFallbackAllowed"] is False
    assert result["bindingIdentityFallbackAllowed"] is False
    assert result["sharedTransactionRequired"] is True
    assert result["appendOnlyAuditRequired"] is True
    assert result["executable"] is False
    assert result["schemaPrerequisites"] == [
        "AaProgram.series_key",
        "AaProgramCourse.formation_mode",
    ]
    assert result["sourceProvenance"]["sourceSystem"] == "LEGACY_SIS"
    assert result["sourceProvenance"]["approval"]["decision"] == "APPROVED"
    assert result["audit"] == {
        "ticket": "MIG-2026-00017",
        "migrationReason": "旧教务系统只保留已批准的 V3 当前方案，历史 V1/V2 不可证明",
        "requiredAction": "PROGRAM_BASELINE_MIGRATE",
    }


def test_v1_is_rejected_from_privileged_baseline_policy():
    with pytest.raises(ValueError, match="v1 belongs to ordinary Program import"):
        _policy().build_program_baseline_migration_policy(_evidence(baselineVersion=1))


@pytest.mark.parametrize(
    "field",
    ["programSeriesKey", "sourceSystem", "sourceRecordId", "effectiveAt", "auditTicket", "migrationReason"],
)
def test_required_provenance_fields_fail_closed(field):
    evidence = _evidence()
    evidence[field] = ""
    with pytest.raises(ValueError, match=field):
        _policy().build_program_baseline_migration_policy(evidence)


def test_source_approval_must_be_explicit_approved_and_referenceable():
    rejected = _evidence(sourceApprovalEvidence={
        "decision": "REJECTED",
        "evidenceRef": "decision-1",
        "approvedByRef": "user-1",
        "approvedAt": "2026-01-10T09:30:00+08:00",
    })
    with pytest.raises(ValueError, match="decision must be APPROVED"):
        _policy().build_program_baseline_migration_policy(rejected)

    missing_ref = _evidence(sourceApprovalEvidence={
        "decision": "APPROVED",
        "evidenceRef": "",
        "approvedByRef": "user-1",
        "approvedAt": "2026-01-10T09:30:00+08:00",
    })
    with pytest.raises(ValueError, match="evidenceRef"):
        _policy().build_program_baseline_migration_policy(missing_ref)


def test_effective_and_approval_times_must_be_timezone_aware_and_ordered():
    with pytest.raises(ValueError, match="include timezone offset"):
        _policy().build_program_baseline_migration_policy(_evidence(effectiveAt="2026-02-01T00:00:00"))

    with pytest.raises(ValueError, match="must not precede source approval time"):
        _policy().build_program_baseline_migration_policy(_evidence(effectiveAt="2026-01-01T00:00:00+08:00"))


def test_policy_is_pure_and_does_not_claim_shared_migration_or_dispatcher_owner():
    source = inspect.getsource(_policy())
    assert "get_sessionmaker" not in source
    assert "session()" not in source
    assert "db.add" not in source
    assert "db.commit" not in source
    assert "op.add_column" not in source
    assert "data_exchange_confirm_service" not in source
    assert "data_exchange_confirm_legacy" not in source
    assert "AaProgram(" not in source
