"""Static safety contract for the production interaction E2E workflow."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "playwright-production-e2e.yml"
RESET_SCRIPT = ROOT / "backend" / "scripts" / "e2e_reset_graduation_passwords.py"
VERIFY_SCRIPT = ROOT / "backend" / "scripts" / "e2e_verify_graduation_accounts.py"
BOOTSTRAP_SCRIPT = ROOT / "backend" / "scripts" / "e2e_bootstrap_graduation_accounts_ci.py"
COUNSELOR_BOOTSTRAP = ROOT / "backend" / "scripts" / "e2e_bootstrap_affairs_counselor_ci.py"
INTERNSHIP_SEED = ROOT / "backend" / "scripts" / "e2e_seed_internship_sandbox.py"
SCHOOL_IAM_SEED = ROOT / "backend" / "scripts" / "e2e_seed_control_plane_school_iam.py"
ACADEMIC_B_SEEDS = (
    "e2e_seed_academic_b_selection.py",
    "e2e_seed_academic_b_w3_schedule.py",
    "e2e_seed_academic_b_w4_selection.py",
    "e2e_seed_academic_b_w4_formation.py",
    "e2e_seed_academic_b_w5_selection.py",
)
ACADEMIC_B_FIXTURES = (
    "academic-b-w3-fixture.json",
    "academic-b-w4-fixture.json",
    "academic-b-w4-formation-fixture.json",
    "academic-b-w5-fixture.json",
)


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


def test_playwright_runs_exact_head_and_real_school_iam_fixture_seed():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    seed = SCHOOL_IAM_SEED.read_text(encoding="utf-8")

    assert "E2E_EXPECTED_SHA: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow
    assert "Exact branch HEAD assertion" in workflow
    assert "python scripts/e2e_seed_control_plane_school_iam.py" in workflow
    assert workflow.index("python scripts/e2e_seed_playwright_tenants.py") < workflow.index(
        "python scripts/e2e_seed_control_plane_school_iam.py"
    )
    assert '"control-plane-school-iam.json"' in seed
    assert "reconcile_permission_catalog(" in seed
    assert "converge_published_system_templates(" in seed


def test_playwright_materializes_all_academic_b_runtime_fixtures_in_dependency_order():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for seed_name in ACADEMIC_B_SEEDS:
        assert (ROOT / "backend" / "scripts" / seed_name).is_file()
        assert f"python scripts/{seed_name}" in workflow
    for fixture_name in ACADEMIC_B_FIXTURES:
        assert f"test -s ../e2e/{fixture_name}" in workflow

    base_seed = workflow.index("python scripts/e2e_seed_academic_b_selection.py")
    w3_seed = workflow.index("python scripts/e2e_seed_academic_b_w3_schedule.py")
    w4_seed = workflow.index("python scripts/e2e_seed_academic_b_w4_selection.py")
    formation_seed = workflow.index("python scripts/e2e_seed_academic_b_w4_formation.py")
    account_bootstrap = workflow.index("python scripts/e2e_bootstrap_graduation_accounts_ci.py")
    w5_seed = workflow.index("python scripts/e2e_seed_academic_b_w5_selection.py")
    browser_run = workflow.index("run: npm test")

    assert base_seed < w3_seed < w4_seed < formation_seed
    # Formation creates the official org rows the canonical account bootstrap discovers.
    assert formation_seed < account_bootstrap
    # W5 consumes the official student identities created by that bootstrap.
    assert account_bootstrap < w5_seed < browser_run


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


def test_document_preview_e2e_sources_are_synthetic_and_never_embed_secrets():
    """W0 safety contract activates automatically when Viewer browser specs/fixtures appear."""
    roots = (ROOT / "e2e", ROOT / "frontend" / "tests")
    candidates = []
    for base in roots:
        if not base.exists():
            continue
        candidates.extend(
            path for path in base.rglob("*")
            if path.is_file()
            and "document-preview" in path.name.lower()
            and path.suffix.lower() in {".js", ".mjs", ".ts", ".json", ".html"}
        )

    forbidden = (
        "Authorization: Bearer ",
        '"authorization": "Bearer ',
        "X-Amz-Signature=",
        "X-Cos-Security-Token=",
        "preview?ticket=",
        '"ticket": "',
        "studentNameReal",
        "studentNoReal",
    )
    for path in candidates:
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "YUEKE E2E SYNTHETIC DOCUMENT" in text, path
        for marker in forbidden:
            assert marker not in text, f"{path} persists forbidden Viewer artifact data: {marker}"
