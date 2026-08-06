"""Static safety contract for the production interaction E2E workflow."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "playwright-production-e2e.yml"
RESET_SCRIPT = ROOT / "backend" / "scripts" / "e2e_reset_graduation_passwords.py"
VERIFY_SCRIPT = ROOT / "backend" / "scripts" / "e2e_verify_graduation_accounts.py"
BOOTSTRAP_SCRIPT = ROOT / "backend" / "scripts" / "e2e_bootstrap_graduation_accounts_ci.py"
INTERNSHIP_SEED = ROOT / "backend" / "scripts" / "e2e_seed_internship_sandbox.py"


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


def test_internship_seed_only_creates_prerequisites_in_local_e2e_database():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    seed = INTERNSHIP_SEED.read_text(encoding="utf-8")

    assert "python scripts/e2e_seed_internship_sandbox.py" in workflow
    assert "E2E_ALLOW_DESTRUCTIVE_TESTS=true is required" in seed
    assert "DATABASE_URL must contain e2e or test" in seed
    assert "internship E2E seed only accepts a local database" in seed
    assert "require_tenant(db)" in seed
    assert "refusing internship E2E seed" in seed
    assert "tenant.tenant_code != TENANT_CODE" in seed

    # Leave state and its audit trail must be produced by visible browser interactions.
    assert "InternshipLeave(" not in seed
    assert "InternshipAuditTrail(" not in seed
    assert '"password"' not in seed
    assert "password_hash" not in seed
