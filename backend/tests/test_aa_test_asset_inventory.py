"""S0-T contract for the machine-readable academic-affairs pytest inventory."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_SCRIPT = REPO_ROOT / "scripts" / "check" / "academic_affairs_test_inventory.py"


def _inventory() -> dict:
    completed = subprocess.run(
        [sys.executable, str(INVENTORY_SCRIPT), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    return json.loads(completed.stdout)


def test_s0_test_asset_inventory_is_nonempty_valid_and_ledger_aware():
    inventory = _inventory()
    assert inventory["validation_errors"] == []
    assert inventory["test_file_count"] > 0
    assert inventory["nodeid_count"] >= inventory["test_file_count"]
    assert inventory["known_failure_ledger"] == "scripts/check/backend-known-failures-main.txt"
    assert inventory["known_failure_count"] == 0

    expected_patterns = {
        "test_aa_*.py",
        "*academic*.py",
        "*graduation*.py",
        "*selection*.py",
    }
    assert set(inventory["scan_patterns"]) == expected_patterns
    assert all(inventory["matched_files_by_pattern"][pattern] > 0 for pattern in expected_patterns)


def test_s0_test_asset_inventory_covers_structural_contract_and_all_domain_buckets():
    inventory = _inventory()
    rows = inventory["tests"]
    nodeids = {row["nodeid"] for row in rows}

    assert any(
        nodeid.startswith("backend/tests/test_aa_post_pr58_refactor_contracts.py::")
        for nodeid in nodeids
    )
    assert any(
        nodeid.startswith("backend/tests/test_aa_test_asset_inventory.py::")
        for nodeid in nodeids
    )

    allowed_kinds = {"BLACKBOX", "WHITEBOX", "COMPAT", "CI_DEBT"}
    assert {row["test_kind"] for row in rows} <= allowed_kinds
    assert all(row["production_owner"] for row in rows)

    # The inventory must remain useful for domain-scoped selection.  Every primary
    # construction domain needs at least one discoverable node before P0 proceeds.
    domains = {row["business_domain"] for row in rows}
    for domain in (
        "D1_TERM_CALENDAR",
        "D2_ROSTER_REGISTRATION",
        "D3_STATUS_CHANGE",
        "D4_PROGRAM_COURSE_TASK",
        "D5_SCHEDULE_RESOURCE",
        "D6_SELECTION",
        "D7_EXAM_MAKEUP",
        "D8_GRADE",
        "D9_FINAL_DOMAINS",
    ):
        assert domain in domains, f"missing machine-selected tests for {domain}"
