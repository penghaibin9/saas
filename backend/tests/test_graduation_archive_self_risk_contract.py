from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def section(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_gd_r12_archive_self_risk_does_not_deadlock_freeze_but_other_open_risks_still_block():
    manifest = text("backend/app/modules/graduation/materials/manifest_service.py")
    guard = section(manifest, "def _assert_no_open_risk", "def _active_manifest")

    # GD-R12 means "not archived yet" and is resolved by the filing transaction
    # itself. Counting it here creates a circular rule: not filed -> R12 open ->
    # filing forbidden. Only this self-referential risk may be ignored by the
    # pre-freeze risk guard.
    assert 'GraduationRiskCase.risk_code != "GD-R12"' in guard

    # Every other unresolved risk remains fail-closed.
    assert 'GraduationRiskCase.status.in_(("OPEN", "PROCESSING"))' in guard
    assert "GraduationRiskCase.is_deleted.is_(False)" in guard
    assert 'raise AppException("DATA_CONFLICT"' in guard
    assert "未关闭风险，不能归档" in guard


def test_gd_r12_is_still_a_real_risk_until_the_archive_becomes_filed():
    risk = text("backend/app/modules/graduation/services/graduation_risk_service.py")
    evaluate = section(risk, "def _eval_hits", "def _scan_one_student")

    # Do not delete or weaken GD-R12 itself. It must continue to be raised while
    # a published-grade student has no FILED archive; only the atomic filing
    # guard is allowed to exempt the risk it is about to resolve.
    assert 'if g and g.status == "PUBLISHED"' in evaluate
    assert 'if not ar or ar.status != "FILED"' in evaluate
    assert 'hits.append("GD-R12")' in evaluate
