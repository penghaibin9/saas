from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "academic_d_w5_upstream_freeze.py"
REPLAY = Path(__file__).resolve().parents[1] / "scripts" / "academic_d_w5_final_gold_replay.sh"
SPEC = importlib.util.spec_from_file_location("academic_d_w5_upstream_freeze", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _payload(
    number: int,
    branch: str,
    body: str,
    *,
    sha: str = "a" * 40,
    state: str = "open",
    draft: bool = True,
    merged: bool = False,
):
    return {
        "number": number,
        "state": state,
        "draft": draft,
        "merged": merged,
        "merged_at": "2026-08-18T03:49:37Z" if merged else None,
        "body": body,
        "head": {"ref": branch, "sha": sha},
    }


def test_contract_freeze_requires_explicit_local_freeze_language():
    assert MODULE._contract_frozen("A-C5 → next", "A-C5") is False
    assert MODULE._contract_frozen("A-C5 Program Import FROZEN @ deadbeef", "A-C5") is True
    assert MODULE._contract_frozen("A-C5 Program Import 已冻结。", "A-C5") is True


def test_current_style_a_body_stays_fail_closed_when_a_c1_a_c4_a_c5_are_missing():
    body = (
        "A-W2 / A-C2 Course Identity / A-C3 Program Execution FROZEN. "
        "A-W4 Course confirm FROZEN. next Program adapter → A-C5 → real-school sample"
    )
    row = MODULE.evaluate_pr(
        "A",
        _payload(145, "agent/academic-a-semester-core", body),
    )
    assert row["contracts"]["A-C2"] is True
    assert row["contracts"]["A-C3"] is True
    assert row["contracts"]["A-C5"] is False
    assert "A-C5" in row["missingContracts"]
    assert row["allContractsFrozen"] is False


def test_b_group_freeze_sentence_can_freeze_all_three_contracts():
    body = "B-C1 Published Schedule、B-C2 Selection Eligibility、B-C3 Student Selection Projection 已冻结。"
    row = MODULE.evaluate_pr(
        "B",
        _payload(146, "agent/academic-b-schedule-selection", body),
    )
    assert row["missingContracts"] == []
    assert row["allContractsFrozen"] is True


def test_c_only_c1_frozen_never_promotes_c2_c3():
    body = "C-C1 Attendance Consumer Contract 已冻结。后续 C-C2、C-C3 继续施工。"
    row = MODULE.evaluate_pr(
        "C",
        _payload(148, "agent/academic-c-teaching-execution", body),
    )
    assert row["contracts"]["C-C1"] is True
    assert row["contracts"]["C-C2"] is False
    assert row["contracts"]["C-C3"] is False
    assert row["allContractsFrozen"] is False


def test_merged_a_final_gold_can_replace_obsolete_per_contract_tokens():
    body = (
        "A-W1～A-W4 FROZEN / INT shared handoff FROZEN / Program shared FROZEN / "
        "A-C5 Gold FROZEN / Final same-head acceptance GOLD"
    )
    row = MODULE.evaluate_pr(
        "A",
        _payload(
            145,
            "agent/academic-a-semester-core",
            body,
            state="closed",
            draft=False,
            merged=True,
        ),
    )
    assert row["ownerFinalGold"] is True
    assert row["structuralOk"] is True
    assert row["missingContracts"] == []
    assert row["allContractsFrozen"] is True


def test_closed_unmerged_a_never_promotes_to_frozen():
    body = (
        "A-W1～A-W4 FROZEN / A-C5 Gold FROZEN / "
        "Final same-head acceptance GOLD"
    )
    row = MODULE.evaluate_pr(
        "A",
        _payload(
            145,
            "agent/academic-a-semester-core",
            body,
            state="closed",
            draft=False,
            merged=False,
        ),
    )
    assert row["ownerFinalGold"] is False
    assert row["structuralOk"] is False
    assert row["allContractsFrozen"] is False


def test_c_final_gold_can_replace_obsolete_c_c2_c_c3_labels_only_when_non_draft():
    body = (
        "SAME-HEAD C-W2 — GREEN\n"
        "SAME-HEAD C-W3/W4/W5 Final — GREEN\n"
        "Final judgment：GREEN / merge-ready。"
    )
    ready = MODULE.evaluate_pr(
        "C",
        _payload(
            148,
            "agent/academic-c-teaching-execution",
            body,
            draft=False,
        ),
    )
    draft = MODULE.evaluate_pr(
        "C",
        _payload(
            148,
            "agent/academic-c-teaching-execution",
            body,
            draft=True,
        ),
    )
    assert ready["ownerFinalGold"] is True
    assert ready["missingContracts"] == []
    assert ready["allContractsFrozen"] is True
    assert draft["ownerFinalGold"] is False
    assert draft["allContractsFrozen"] is False


def test_generic_green_words_do_not_promote_owner_final_gold():
    body = "GREEN / merge-ready"
    row = MODULE.evaluate_pr(
        "C",
        _payload(
            148,
            "agent/academic-c-teaching-execution",
            body,
            draft=False,
        ),
    )
    assert row["ownerFinalGold"] is False
    assert row["allContractsFrozen"] is False


def test_wrong_branch_blocks_freeze_even_if_body_claims_all_contracts():
    body = "A-C1 A-C2 A-C3 A-C4 A-C5 all FROZEN"
    wrong_branch = MODULE.evaluate_pr("A", _payload(145, "wrong/a", body))
    assert wrong_branch["structuralOk"] is False
    assert wrong_branch["allContractsFrozen"] is False


def test_matrix_requires_all_three_owner_lines_and_surfaces_exact_missing_contracts():
    payloads = {
        "A": _payload(
            145,
            "agent/academic-a-semester-core",
            "A-C1 FROZEN; A-C2 FROZEN; A-C3 FROZEN; A-C4 FROZEN; A-C5 → next",
        ),
        "B": _payload(
            146,
            "agent/academic-b-schedule-selection",
            "B-C1 Published、B-C2 Selection、B-C3 Projection 已冻结。",
        ),
        "C": _payload(
            148,
            "agent/academic-c-teaching-execution",
            "C-C1 FROZEN; C-C2 FROZEN; C-C3 continuing",
        ),
    }
    matrix = MODULE.build_freeze_matrix(payloads)
    assert matrix["allFrozen"] is False
    assert "A:contract_not_explicitly_frozen:A-C5" in matrix["blockers"]
    assert "C:contract_not_explicitly_frozen:C-C3" in matrix["blockers"]


def test_all_explicit_freezes_are_required_for_true():
    payloads = {
        line: _payload(
            int(config["pr"]),
            str(config["branch"]),
            "; ".join(f"{code} FROZEN" for code in config["contracts"]),
        )
        for line, config in MODULE.UPSTREAM.items()
    }
    matrix = MODULE.build_freeze_matrix(payloads)
    assert matrix["allFrozen"] is True
    assert matrix["blockers"] == []


def test_api_error_is_fail_closed_even_with_frozen_payloads():
    payloads = {
        line: _payload(
            int(config["pr"]),
            str(config["branch"]),
            "; ".join(f"{code} FROZEN" for code in config["contracts"]),
        )
        for line, config in MODULE.UPSTREAM.items()
    }
    matrix = MODULE.build_freeze_matrix(payloads, api_error="HTTPError:403")
    assert matrix["allFrozen"] is False
    assert matrix["blockers"][0] == "github_api_error:HTTPError:403"


def test_w5_replay_only_materializes_the_reviewed_two_head_no_ddl_convergence():
    source = REPLAY.read_text(encoding="utf-8")
    for token in (
        'B_C_DAG_HEAD_A="20260818_acad_main_int_merge"',
        'B_C_DAG_HEAD_C="20260818_merge_prog_grade_dl"',
        'B_C_DAG_REVISION="20260818_acad_bc_final"',
        'actual_heads="$(cd backend && alembic heads',
        'if [[ "$actual_heads" != "$expected_heads" ]]',
        'down_revision = (',
        '"20260818_acad_main_int_merge",',
        '"20260818_merge_prog_grade_dl",',
        'def upgrade() -> None:',
        'def downgrade() -> None:',
        'DAG_CONVERGENCE_PROVEN=true',
    ):
        assert token in source
    start = source.index('cat > "$B_C_DAG_PATH"')
    end = source.index("PY\n\n  git add", start)
    assert "op." not in source[start:end]
