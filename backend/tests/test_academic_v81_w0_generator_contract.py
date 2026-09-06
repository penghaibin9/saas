"""Academic V8.1 W0 refresh must fail closed around shared IAM authority."""
from pathlib import Path


def _source() -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "scripts/audit/generate-academic-v81-w0.mjs").read_text(encoding="utf-8")


def test_w0_classifies_the_shared_iam_branch_as_required_authority():
    source = _source()
    assert "head === 'codex/control-plane-iam-menu-v1'" in source
    assert "return ['IAM_AUTHORITY'" in source
    assert "requiredBeforeAcademicV81" in source
    assert "OWNER_MERGE_IAM_PR_" in source


def test_w0_never_claims_or_performs_the_owner_iam_merge():
    source = _source()
    assert "Do not merge this shared authority from the Academic worktree" in source
    assert "PR_OPEN_DRAFT_CHECKS_PENDING" in source
    assert "git(['merge'" not in source
    assert "git(['push'" not in source


def test_w0_browser_manifest_uses_real_workspace_captures_without_claiming_login():
    source = _source()
    assert "01-staff-login.png" in source
    assert "02-student-login.png" in source
    assert "03-teacher-mini-login-viewport.png" in source
    assert "No password submission is claimed by this W0 baseline" in source
    assert "MULTI_SURFACE_LOGIN_CAPTURED_ROLE_REPLAY_PENDING" in source


def test_w0_captures_pr245_and_exact_head_release_pr_mergeability():
    source = _source()
    assert "githubJson('/pulls/245')" in source
    assert "githubPullWithMergeability" in source
    assert "featurePullRequest" in source
    assert "mergeableState" in source
    assert "current exact-head Academic V8.1 release pull request" in source
