from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "academic_d_w5_same_head_matrix.py"
SPEC = importlib.util.spec_from_file_location("academic_d_w5_same_head_matrix", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _run(name: str, *, run_id: int, status: str = "completed", conclusion: str | None = "success", sha: str = "d-head", attempt: int = 1):
    return {
        "id": run_id,
        "run_attempt": attempt,
        "run_number": run_id,
        "name": name,
        "head_sha": sha,
        "status": status,
        "conclusion": conclusion,
        "html_url": f"https://example.invalid/{run_id}",
    }


def _all_success_runs(sha: str = "d-head"):
    return [
        _run(name, run_id=index + 10, sha=sha)
        for index, name in enumerate(MODULE.REQUIRED_SAME_HEAD_WORKFLOWS)
    ]


def _replay_evidence(**overrides):
    evidence = {
        "w5_phase": "PRE_GOLD_REPLAY_COMPLETE",
        "replay_success": "true",
        "clean_tenant_schema_proven": "true",
        "migrated_tenant_schema_proven": "true",
        "migrated_tenant_contracts_proven": "true",
        "a_commit": "a" * 40,
        "b_commit": "b" * 40,
        "c_commit": "c" * 40,
        "main_alembic_version": "main-head",
        "integrated_alembic_version": "integrated-head",
        "migrated_probe_digest": "d" * 64,
        "final_browser_gold_proven_on_w5_head": "false",
    }
    evidence.update({key: str(value).lower() if isinstance(value, bool) else str(value) for key, value in overrides.items()})
    return evidence


def _upstream_frozen(value: bool = True, **head_overrides):
    heads = {
        "A": "a" * 40,
        "B": "b" * 40,
        "C": "c" * 40,
    }
    heads.update(head_overrides)
    return {
        "schemaVersion": 1,
        "allFrozen": value,
        "lines": {
            line: {"headSha": sha, "allContractsFrozen": value}
            for line, sha in heads.items()
        },
        "blockers": [] if value else ["A:contract_not_explicitly_frozen:A-C5"],
    }


def test_latest_runs_are_exact_sha_and_latest_attempt_only():
    name = MODULE.REQUIRED_SAME_HEAD_WORKFLOWS[0]
    runs = [
        _run(name, run_id=1, sha="other-head"),
        _run(name, run_id=2, status="completed", conclusion="failure", attempt=1),
        _run(name, run_id=3, status="completed", conclusion="success", attempt=2),
    ]
    selected = MODULE.latest_runs_by_name(runs, "d-head")
    assert selected[name]["id"] == 3
    assert MODULE.classify_workflow(name, selected[name])["state"] == "SUCCESS"


def test_missing_pending_and_failure_are_all_fail_closed():
    missing = MODULE.classify_workflow("missing", None)
    pending = MODULE.classify_workflow("pending", _run("pending", run_id=4, status="in_progress", conclusion=None))
    failed = MODULE.classify_workflow("failed", _run("failed", run_id=5, conclusion="failure"))
    assert missing["state"] == "MISSING" and missing["ready"] is False
    assert pending["state"] == "PENDING" and pending["ready"] is False
    assert failed["state"] == "FAILURE" and failed["ready"] is False


def test_pre_gold_can_be_ready_without_claiming_final_gold():
    matrix = MODULE.build_matrix(
        sha="d-head",
        runs=_all_success_runs(),
        evidence=_replay_evidence(),
        upstream_freeze=_upstream_frozen(False),
    )
    assert matrix["localReplayReady"] is True
    assert matrix["localRequirements"]["migratedTenantSchema"] is True
    assert matrix["externalSameHeadReady"] is True
    assert matrix["preGoldReady"] is True
    assert matrix["finalGold"] is False
    assert matrix["migrationEvidence"]["mainAlembicVersion"] == "main-head"
    assert "upstream_contract_heads_not_frozen" in matrix["blockers"]
    assert "upstream:A:contract_not_explicitly_frozen:A-C5" in matrix["blockers"]
    assert "integrated_final_browser_gold_not_proven" in matrix["blockers"]


def test_migrated_tenant_schema_is_a_hard_pre_gold_requirement():
    matrix = MODULE.build_matrix(
        sha="d-head",
        runs=_all_success_runs(),
        evidence=_replay_evidence(migrated_tenant_schema_proven=False),
        upstream_freeze=_upstream_frozen(False),
    )
    assert matrix["localReplayReady"] is False
    assert matrix["preGoldReady"] is False
    assert "local_requirement:migratedTenantSchema:false" in matrix["blockers"]


def test_final_gold_requires_external_owner_freeze_evidence_not_local_boolean():
    runs = _all_success_runs()
    runs.append(_run(MODULE.AUXILIARY_BROWSER_WORKFLOW, run_id=90, conclusion="failure"))
    matrix = MODULE.build_matrix(
        sha="d-head",
        runs=runs,
        evidence=_replay_evidence(
            upstream_contract_heads_frozen=True,  # legacy local claim must not be authoritative
            final_browser_gold_proven_on_w5_head=True,
        ),
        upstream_freeze=_upstream_frozen(True),
    )
    # Raw-head global Playwright is auxiliary: integrated browser evidence is the final authority.
    assert matrix["auxiliaryRawHeadBrowser"]["state"] == "FAILURE"
    assert matrix["preGoldReady"] is True
    assert matrix["upstreamContractFreezeDeclared"] is True
    assert matrix["upstreamFreezeHeadsMatchReplay"] is True
    assert matrix["upstreamContractHeadsFrozen"] is True
    assert matrix["finalGold"] is True
    assert matrix["blockers"] == []


def test_frozen_owner_contract_on_old_head_cannot_promote_new_replay_head():
    matrix = MODULE.build_matrix(
        sha="d-head",
        runs=_all_success_runs(),
        evidence=_replay_evidence(final_browser_gold_proven_on_w5_head=True),
        upstream_freeze=_upstream_frozen(True, A="f" * 40),
    )
    assert matrix["upstreamContractFreezeDeclared"] is True
    assert matrix["upstreamFreezeHeadsMatchReplay"] is False
    assert matrix["upstreamContractHeadsFrozen"] is False
    assert matrix["finalGold"] is False
    assert any(
        blocker.startswith("upstream_freeze_head_mismatch:A:")
        for blocker in matrix["blockers"]
    )


def test_missing_upstream_freeze_evidence_is_fail_closed_even_if_local_evidence_claims_true():
    matrix = MODULE.build_matrix(
        sha="d-head",
        runs=_all_success_runs(),
        evidence=_replay_evidence(
            upstream_contract_heads_frozen=True,
            final_browser_gold_proven_on_w5_head=True,
        ),
        upstream_freeze={},
    )
    assert matrix["preGoldReady"] is True
    assert matrix["upstreamContractHeadsFrozen"] is False
    assert matrix["finalGold"] is False
    assert "upstream_contract_heads_not_frozen" in matrix["blockers"]


def test_failed_replay_records_phase_layer_and_blocks_pre_gold():
    evidence = _replay_evidence(
        replay_success=False,
        clean_tenant_schema_proven=False,
        migrated_tenant_schema_proven=False,
        migrated_tenant_contracts_proven=False,
        w5_phase="MERGE_INT",
        failed_layer="INT",
    )
    matrix = MODULE.build_matrix(
        sha="d-head",
        runs=_all_success_runs(),
        evidence=evidence,
        upstream_freeze=_upstream_frozen(False),
    )
    assert matrix["localReplayReady"] is False
    assert matrix["preGoldReady"] is False
    assert matrix["finalGold"] is False
    assert "pre_gold_replay_not_green:phase=MERGE_INT:layer=INT" in matrix["blockers"]


def test_actions_api_error_blocks_same_head_readiness_even_with_green_local_replay():
    matrix = MODULE.build_matrix(
        sha="d-head",
        runs=_all_success_runs(),
        evidence=_replay_evidence(),
        upstream_freeze=_upstream_frozen(True),
        api_error="HTTPError:403",
    )
    assert matrix["externalSameHeadReady"] is False
    assert matrix["preGoldReady"] is False
    assert matrix["finalGold"] is False
    assert matrix["blockers"][0].startswith("actions_api_error:")


def test_key_value_parser_ignores_comments_and_malformed_lines(tmp_path):
    evidence = tmp_path / "evidence.txt"
    evidence.write_text(
        "# comment\nreplay_success=true\nmalformed\nfailed_layer=INT=overlay\n",
        encoding="utf-8",
    )
    parsed = MODULE.parse_key_value_evidence(evidence)
    assert parsed == {"replay_success": "true", "failed_layer": "INT=overlay"}


def test_json_evidence_parser_is_fail_closed_for_missing_or_non_object(tmp_path):
    missing = tmp_path / "missing.json"
    assert MODULE.parse_json_evidence(missing) == {}
    bad = tmp_path / "bad.json"
    bad.write_text("[]", encoding="utf-8")
    assert MODULE.parse_json_evidence(bad) == {}
    good = tmp_path / "good.json"
    good.write_text('{"allFrozen": true}', encoding="utf-8")
    assert MODULE.parse_json_evidence(good) == {"allFrozen": True}
