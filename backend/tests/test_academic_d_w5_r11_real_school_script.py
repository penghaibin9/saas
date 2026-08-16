from __future__ import annotations

import inspect


def test_d_w5_r11_real_school_runner_uses_only_canonical_r11_mutations():
    from scripts import academic_d_w5_r11_real_school as runner

    source = inspect.getsource(runner)
    for required in (
        "r11.create_pilot(",
        "r11.run_check(",
        "r11.complete_pilot(",
        'confirm_text="CONFIRM_REAL_SEMESTER_COMPLETED"',
        'persisted["pilotStatus"] != "COMPLETED"',
        'persisted["checkpointCount"] != 6',
        'persisted["checkpointCodes"] != [code for code, _name in r11._STAGE_ORDER]',
    ):
        assert required in source

    for forbidden in (
        '.status = "COMPLETED"',
        ".status='COMPLETED'",
        "AaSemesterPilot(",
        "AaSemesterPilotCheckpoint(",
        "db.add(",
        "db.commit(",
    ):
        assert forbidden not in source


def test_d_w5_r11_real_school_runner_is_local_sandbox_only():
    from scripts import academic_d_w5_r11_real_school as runner

    source = inspect.getsource(runner._assert_safe_target)
    assert runner.EXPECTED_DATABASE == "sandbox_20k_gate"
    assert runner.SANDBOX_TENANT_CODE == "sandbox-school"
    assert runner.SANDBOX_TENANT_ID == 1000000000000000007
    assert 'parsed.hostname not in {"127.0.0.1", "localhost", "::1"}' in source
    assert 'APP_ENV=production' in source
    assert 'DEPLOYMENT_MODE=production' in source
    assert 'MOCK_LOGIN_ENABLED=false' in source


def test_d_w5_r11_candidate_selection_is_ranked_but_completion_is_exact_six_stage_only():
    from scripts import academic_d_w5_r11_real_school as runner

    rank_source = inspect.getsource(runner._rank_candidates)
    ready_source = inspect.getsource(runner._selected_ready)
    assert 'int(item[1]["passedStageCount"])' in rank_source
    assert '-int(item[1]["blockerCount"])' in rank_source
    assert 'int(selected.get("stageCount") or 0) == 6' in ready_source
    assert 'int(selected.get("passedStageCount") or 0) == 6' in ready_source
    assert 'int(selected.get("blockerCount") or 0) == 0' in ready_source


def test_d_w5_r11_red_run_writes_full_blocker_inventory_before_failing():
    from scripts import academic_d_w5_r11_real_school as runner

    source = inspect.getsource(runner.run)
    assert '_write_output(output, base_payload)' in source
    assert 'if not _selected_ready(selected):' in source
    assert '"failedStages": [stage for stage in row.get("stages", []) if not stage.get("passed")]' in source
    assert '"blockers"] = blockers' in source
    assert 'blocker inventory written to' in source
    assert source.index('_write_output(output, base_payload)') < source.index('if not _selected_ready(selected):')


def test_d_w5_r11_preflight_evidence_keeps_stage_hashes_and_raw_blockers():
    from scripts import academic_d_w5_r11_real_school as runner

    source = inspect.getsource(runner._candidate)
    for token in (
        '"stageCode": row["stageCode"]',
        '"blockers": list(row.get("blockers") or [])',
        '"warnings": list(row.get("warnings") or [])',
        '"evidence": row.get("evidence") or {}',
        '"evidenceHash": row.get("evidenceHash") or ""',
    ):
        assert token in source
