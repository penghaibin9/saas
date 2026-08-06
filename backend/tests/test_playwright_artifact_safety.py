"""Static safety contract for the production interaction E2E workflow."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "playwright-production-e2e.yml"
RESET_SCRIPT = ROOT / "backend" / "scripts" / "e2e_reset_graduation_passwords.py"
VERIFY_SCRIPT = ROOT / "backend" / "scripts" / "e2e_verify_graduation_accounts.py"
BOOTSTRAP_SCRIPT = ROOT / "backend" / "scripts" / "e2e_bootstrap_graduation_accounts_ci.py"


def test_playwright_artifacts_never_collect_backend_tmp_wildcards():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "backend/tmp/*.json" not in text
    assert "backend/tmp/**/*.json" not in text
    assert "e2e_graduation_credentials" not in text


def test_ci_account_chain_never_persists_plaintext_password_maps():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (RESET_SCRIPT, VERIFY_SCRIPT, BOOTSTRAP_SCRIPT)
    )
    forbidden = (
        "CRED_PATH.write_text",
        "passwords\": pwd_map",
        "read_text(encoding=\"utf-8\")",
        "credentials written to",
    )
    for marker in forbidden:
        assert marker not in combined


def test_workflow_keeps_mock_login_disabled_and_isolated_database_guarded():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "MOCK_LOGIN_ENABLED: 'false'" in text
    assert "E2E_ALLOW_DESTRUCTIVE_TESTS: 'true'" in text
    assert "student_lifecycle_e2e" in text
    assert "APP_ENV: test" in text
