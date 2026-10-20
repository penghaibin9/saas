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


def test_w0_accepts_feature_head_only_when_latest_main_is_its_ancestor(monkeypatch):
    monkeypatch.setattr(audit, "_ref_sha", lambda _ref: "main-sha")
    monkeypatch.setattr(audit, "_is_ancestor", lambda ancestor, descendant: (
        ancestor, descendant
    ) in {("main-sha", "feature-sha"), ("pr245-merge-sha", "main-sha")})
    live = {
        "headSha": "feature-sha",
        "originMainSha": "main-sha",
        "githubEvidence": {"mode": "LIVE_GITHUB_API"},
        "pr245": {"merged": True, "mergeCommitSha": "pr245-merge-sha"},
    }
    prs = {"githubEvidence": {"mode": "LIVE_GITHUB_API"}}
    migration = {"alembicHeads": ["single-head"]}
    assert audit._w0_pass(live, prs, migration, "feature-sha") is True
    monkeypatch.setattr(audit, "_is_ancestor", lambda *_args: False)
    assert audit._w0_pass(live, prs, migration, "feature-sha") is False


def test_release_pr_must_be_open_exact_head_main_based_and_mergeable():
    live = {
        "featurePullRequest": {
            "number": 246,
            "url": "https://github.com/penghaibin9/saas/pull/246",
            "state": "open",
            "baseRef": "main",
            "headSha": "feature-sha",
            "mergeable": True,
        }
    }
    assert audit._release_pr_pass(live, "feature-sha") is True
    live["featurePullRequest"]["mergeable"] = None
    assert audit._release_pr_pass(live, "feature-sha") is False
    live["featurePullRequest"]["mergeable"] = True
    live["featurePullRequest"]["headSha"] = "stale-sha"
    assert audit._release_pr_pass(live, "feature-sha") is False


def test_evidence_files_must_exist_inside_artifact_root(tmp_path):
    artifact_root = tmp_path / "artifacts"
    seal_path = artifact_root / "browser-replay" / "AA-GJ-01-seal.json"
    screenshot = seal_path.parent / "journey.png"
    screenshot.parent.mkdir(parents=True)
    screenshot.write_bytes(b"real-evidence")
    assert audit._evidence_files_pass({"evidence": ["journey.png"]}, seal_path, artifact_root)
    assert not audit._evidence_files_pass({"evidence": ["missing.png"]}, seal_path, artifact_root)
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside")
    assert not audit._evidence_files_pass({"evidence": ["../../outside.png"]}, seal_path, artifact_root)
