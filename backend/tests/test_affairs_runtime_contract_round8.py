from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_mobile_and_profile_leave_inputs_are_time_safe():
    for name in ("test_affairs_mobile.py", "test_affairs_profile.py"):
        text = read("backend/tests/" + name)
        assert "datetime.utcnow() + timedelta(days=10)" in text
        assert "学生因家庭事务申请短期请假" in text
        assert "ensure_workflow_assignees" in text
        assert '"2026-03-01"' not in text


def test_missing_version_negative_cases_stay_explicit():
    risk = read("backend/tests/test_affairs_risk.py")
    lock = read("backend/tests/test_affairs_optimistic_lock_round1.py")
    assert 'missing = client.post(f"{BASE}/risk/records/{rid}/process"' in risk
    assert 'missing = client.post(f"{BASE}/risk/records/{rid}/process"' in lock


def test_cockpit_failure_contract_uses_mysql_fixture():
    text = read("backend/tests/test_affairs_round1_trust.py")
    assert "def test_cockpit_domain_error_not_fake_zero(db_mode):" in text
