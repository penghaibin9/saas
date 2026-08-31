"""The Academic V8.1 final ledger must remain fail closed."""
from scripts import academic_v81_completion_audit as audit


def test_authority_gate_parser_requires_exact_1_through_74(tmp_path):
    authority = tmp_path / "authority.md"
    authority.write_text(
        "\n".join(
            f"{number}. **D-GATE-AA-{number:02d}** — gate {number}"
            for number in range(1, 75)
        ),
        encoding="utf-8",
    )
    rows = audit._authority_gates(authority)
    assert len(rows) == 74
    assert rows[0]["code"] == "D-GATE-AA-01"
    assert rows[-1]["code"] == "D-GATE-AA-74"


def test_d70_cannot_pass_without_both_mysql_and_browser_performance():
    common = dict(
        w0_pass=True,
        iam_pass=True,
        journeys_pass=True,
        browser_state_pass=True,
        final_same_head=True,
        final_main=True,
    )
    status, _ = audit._gate_status(
        70, d70_pass=True, browser_perf_pass=False, **common
    )
    assert status == "PENDING_BROWSER_LONG_TASK"
    status, _ = audit._gate_status(
        70, d70_pass=True, browser_perf_pass=True, **common
    )
    assert status == "PASS"


def test_iam_journeys_recovery_and_final_main_are_independent_seals():
    base = dict(
        w0_pass=True,
        iam_pass=False,
        journeys_pass=False,
        d70_pass=True,
        browser_perf_pass=True,
        browser_state_pass=False,
        final_same_head=False,
        final_main=False,
    )
    assert audit._gate_status(4, **base)[0] == "PENDING_IAM_AUTHORITY"
    assert audit._gate_status(11, **base)[0] == "PENDING_12_OF_12_L4"
    assert audit._gate_status(71, **base)[0] == "PENDING_BROWSER_STATE_RECOVERY"
    assert audit._gate_status(73, **base)[0] == "PENDING_FINAL_EXACT_HEAD"
    assert audit._gate_status(74, **base)[0] == "PENDING_IAM_OWNER_MERGE"


def test_all_28_capabilities_have_explicit_journey_coverage():
    assert set(audit.CAPABILITY_JOURNEYS) == {
        f"CP-AA-{number:02d}" for number in range(1, 29)
    }
    assert all(audit.CAPABILITY_JOURNEYS.values())
