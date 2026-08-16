"""Static safety contract for the production interaction E2E workflow."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "playwright-production-e2e.yml"
RESET_SCRIPT = ROOT / "backend" / "scripts" / "e2e_reset_graduation_passwords.py"
VERIFY_SCRIPT = ROOT / "backend" / "scripts" / "e2e_verify_graduation_accounts.py"
BOOTSTRAP_SCRIPT = ROOT / "backend" / "scripts" / "e2e_bootstrap_graduation_accounts_ci.py"
COUNSELOR_BOOTSTRAP = ROOT / "backend" / "scripts" / "e2e_bootstrap_affairs_counselor_ci.py"
INTERNSHIP_SEED = ROOT / "backend" / "scripts" / "e2e_seed_internship_sandbox.py"


def test_playwright_artifacts_never_collect_backend_tmp_wildcards():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "backend/tmp/*.json" not in text
    assert "backend/tmp/**/*.json" not in text
    assert "e2e_graduation_credentials" not in text


def test_ci_account_chain_never_persists_plaintext_password_maps():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (RESET_SCRIPT, VERIFY_SCRIPT, BOOTSTRAP_SCRIPT, COUNSELOR_BOOTSTRAP)
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


def test_counselor_bootstrap_uses_canonical_teacher_identity_pipeline():
    counselor = COUNSELOR_BOOTSTRAP.read_text(encoding="utf-8")
    canonical = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")

    assert "build_teacher_template" in counselor
    assert "_canonical_import(" in counselor
    assert 'kind="teachers"' in counselor
    assert 'idempotency_namespace="e2e-affairs-counselor"' in counselor
    assert "/system/identity-import/template" not in counselor
    assert "/system/identity-import/validate-file" not in counselor
    assert "/system/identity-import/confirm-batch" not in counselor

    assert 'idempotency_namespace: str = "e2e-graduation"' in canonical
    assert 'upload_key = f"{namespace}-{kind}-canonical-v3"' in canonical
    assert 'f"{namespace}-{kind}-confirm-v3"' in canonical
