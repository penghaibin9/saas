from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "seed_internship_capacity.py"
SPEC = importlib.util.spec_from_file_location("seed_internship_capacity", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_school_scale_defaults_are_realistic_and_deterministic():
    args = module.parse_args(["--dry-run"])
    expected = module.build_expected(args)
    assert args.students == 20_000
    assert args.active_interns == 8_000
    assert args.history_batches == 5
    assert expected == {
        "tenants": 1,
        "students": 20_000,
        "batches": 6,
        "internshipRecords": 48_000,
        "checkins": 1_440_000,
        "weeklyReports": 208_000,
        "guidances": 96_000,
        "batchPlans": 1,
        "planTaskProgress": 80_000,
        "processReports": 48_000,
        "risks": 240,
        "attendanceExceptions": 240,
    }
    manifest = module.build_manifest(args, seeded=False)
    assert manifest["fixture"] == "internship-school-scale-v1"
    assert manifest["currentBatchId"] == module._batch_id(6)
    assert manifest["expected"] == expected
    assert manifest["seeded"] is False
    students = list(module._student_rows(args))
    assert students[0]["current_stage"] == "INTERN"
    assert students[args.active_interns]["current_stage"] == "ENROLLED"


def test_invalid_scale_arguments_fail_closed():
    with pytest.raises(SystemExit):
        module.parse_args(["--students", "100", "--active-interns", "101", "--dry-run"])
    with pytest.raises(SystemExit):
        module.parse_args(["--risk-ratio", "1.1", "--dry-run"])
    with pytest.raises(SystemExit):
        module.parse_args(["--cleanup", "--replace"])
