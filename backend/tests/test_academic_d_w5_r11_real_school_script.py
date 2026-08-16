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


def test_d_w5_r11_candidate_selection_is_fail_closed_not_best_effort():
    from scripts import academic_d_w5_r11_real_school as runner

    source = inspect.getsource(runner._choose_candidate)
    assert 'int(selected["passedStageCount"]) != 6' in source
    assert 'int(selected["blockerCount"]) != 0' in source
    assert "no existing real term satisfies all R11 stages" in source
