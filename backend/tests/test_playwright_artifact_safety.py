"""Static safety contract for the complete Playwright runtime graph.

The production and Graduation workflows intentionally delegate infrastructure to
one local composite action and one bootstrap script. These tests validate that
full graph instead of coupling safety to duplicated inline YAML commands.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_WORKFLOW = ROOT / ".github" / "workflows" / "playwright-production-e2e.yml"
GRADUATION_WORKFLOW = ROOT / ".github" / "workflows" / "graduation-browser-gate.yml"
GOLD_WORKFLOW = ROOT / ".github" / "workflows" / "graduation-v6-gold-candidate.yml"
RUNTIME_ACTION = ROOT / ".github" / "actions" / "browser-runtime" / "action.yml"
RUNTIME_BOOTSTRAP = ROOT / "scripts" / "e2e" / "bootstrap-browser-runtime.sh"
SUITE_RUNNER = ROOT / "scripts" / "e2e" / "run-browser-suite.sh"
RESET_SCRIPT = ROOT / "backend" / "scripts" / "e2e_reset_graduation_passwords.py"
VERIFY_SCRIPT = ROOT / "backend" / "scripts" / "e2e_verify_graduation_accounts.py"
BOOTSTRAP_SCRIPT = ROOT / "backend" / "scripts" / "e2e_bootstrap_graduation_accounts_ci.py"
COUNSELOR_BOOTSTRAP = ROOT / "backend" / "scripts" / "e2e_bootstrap_affairs_counselor_ci.py"
INTERNSHIP_SEED = ROOT / "backend" / "scripts" / "e2e_seed_internship_sandbox.py"
SCHOOL_IAM_SEED = ROOT / "backend" / "scripts" / "e2e_seed_control_plane_school_iam.py"
WORKFLOWS = (PRODUCTION_WORKFLOW, GRADUATION_WORKFLOW, GOLD_WORKFLOW)
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


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_playwright_artifacts_never_collect_backend_tmp_wildcards():
    combined = "\n".join(read(path) for path in (*WORKFLOWS, RUNTIME_ACTION, RUNTIME_BOOTSTRAP, SUITE_RUNNER))
    assert "backend/tmp/*.json" not in combined
    assert "backend/tmp/**/*.json" not in combined
    assert "e2e_graduation_credentials" not in combined


def test_ci_account_chain_never_persists_plaintext_password_maps():
    combined = "\n".join(
        read(path)
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


def test_all_browser_gates_keep_mock_login_disabled_and_isolated_database_guarded():
    for workflow in WORKFLOWS:
        text = read(workflow)
        assert "MOCK_LOGIN_ENABLED: 'false'" in text, workflow
        assert "E2E_ALLOW_DESTRUCTIVE_TESTS: 'true'" in text, workflow
        assert "student_lifecycle_e2e" in text, workflow
        assert "APP_ENV: test" in text, workflow


def test_workflows_follow_exact_head_through_the_shared_runtime_graph():
    production = read(PRODUCTION_WORKFLOW)
    graduation = read(GRADUATION_WORKFLOW)
    gold = read(GOLD_WORKFLOW)
    action = read(RUNTIME_ACTION)
    bootstrap = read(RUNTIME_BOOTSTRAP)

    for workflow in (production, graduation):
        assert "E2E_EXPECTED_SHA: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow
    assert "E2E_EXPECTED_SHA: ${{ inputs.head_sha || github.sha }}" in gold

    for workflow in (production, graduation, gold):
        assert "ref: ${{ env.E2E_EXPECTED_SHA }}" in workflow
        assert "uses: ./.github/actions/browser-runtime" in workflow
        assert "head_sha: ${{ env.E2E_EXPECTED_SHA }}" in workflow

    assert "E2E_EXPECTED_SHA: ${{ inputs.head_sha }}" in action
    assert 'bash "$GITHUB_WORKSPACE/scripts/e2e/bootstrap-browser-runtime.sh"' in action
    assert 'ACTUAL_SHA="$(git rev-parse HEAD)"' in bootstrap
    assert 'test "$ACTUAL_SHA" = "$EXPECTED_SHA"' in bootstrap


def test_real_school_iam_seed_is_centralized_and_ordered_after_tenant_seed():
    bootstrap = read(RUNTIME_BOOTSTRAP)
    seed = read(SCHOOL_IAM_SEED)

    tenant_seed = bootstrap.index("python scripts/e2e_seed_playwright_tenants.py")
    school_seed = bootstrap.index("python scripts/e2e_seed_control_plane_school_iam.py")
    assert tenant_seed < school_seed
    assert '"control-plane-school-iam.json"' in seed
    assert "reconcile_permission_catalog(" in seed
    assert "converge_published_system_templates(" in seed


def test_full_runtime_materializes_academic_dependencies_in_canonical_order():
    bootstrap = read(RUNTIME_BOOTSTRAP)
    runner = read(SUITE_RUNNER)

    for seed_name in ACADEMIC_B_SEEDS:
        assert (ROOT / "backend" / "scripts" / seed_name).is_file()
        assert f"python scripts/{seed_name}" in bootstrap
    for fixture_name in ACADEMIC_B_FIXTURES:
        assert f"e2e/{fixture_name}" in bootstrap

    base_seed = bootstrap.index("python scripts/e2e_seed_academic_b_selection.py")
    w3_seed = bootstrap.index("python scripts/e2e_seed_academic_b_w3_schedule.py")
    w4_seed = bootstrap.index("python scripts/e2e_seed_academic_b_w4_selection.py")
    formation_seed = bootstrap.index("python scripts/e2e_seed_academic_b_w4_formation.py")
    account_bootstrap = bootstrap.index("python scripts/e2e_bootstrap_graduation_accounts_ci.py")
    w5_seed = bootstrap.index("python scripts/e2e_seed_academic_b_w5_selection.py")

    assert base_seed < w3_seed < w4_seed < formation_seed
    # Formation creates the official org rows the canonical identity import discovers.
    assert formation_seed < account_bootstrap
    # W5 consumes the official student identities created by that account import.
    assert account_bootstrap < w5_seed
    assert "npx playwright test" in runner


def test_internship_seed_stays_in_full_runtime_and_only_creates_local_prerequisites():
    bootstrap = read(RUNTIME_BOOTSTRAP)
    seed = read(INTERNSHIP_SEED)

    assert 'if [[ "$PROFILE" == "full" ]]' in bootstrap
    assert "python scripts/e2e_seed_internship_sandbox.py" in bootstrap
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


def test_browser_runtime_is_centralized_and_gold_is_manual_only():
    production = read(PRODUCTION_WORKFLOW)
    graduation = read(GRADUATION_WORKFLOW)
    gold = read(GOLD_WORKFLOW)

    for workflow in (production, graduation, gold):
        assert "python -m alembic upgrade head" not in workflow
        assert "nohup uvicorn" not in workflow
        assert "e2e_bootstrap_graduation_accounts_ci.py" not in workflow

    assert "profile: full" in production
    assert "production-non-graduation" in production
    assert "profile: graduation" in graduation
    assert "graduation-functional" in graduation
    assert "workflow_dispatch:" in gold
    assert "\n  pull_request:" not in gold
    assert "cancel-in-progress: false" in gold
    assert "graduation-gold" in gold


def test_counselor_bootstrap_uses_canonical_teacher_identity_pipeline():
    counselor = read(COUNSELOR_BOOTSTRAP)
    canonical = read(BOOTSTRAP_SCRIPT)

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
    """Viewer browser fixtures must be synthetic; source-contract tests are not browser artifacts."""
    e2e_root = ROOT / "e2e"
    suffixes = {".js", ".mjs", ".ts", ".json", ".html"}
    markers = ("YUEKE E2E SYNTHETIC DOCUMENT", "YUEKE E2E GRADUATION SCENARIO")
    candidates = []

    if e2e_root.exists():
        for path in e2e_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "document-preview" in path.name.lower() or any(marker in text for marker in markers):
                candidates.append((path, text))

    for relative in (Path("frontend/tests/e2e"), Path("frontend/tests/playwright")):
        base = ROOT / relative
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "document-preview" in path.name.lower() or any(marker in text for marker in markers):
                candidates.append((path, text))

    assert candidates, "Viewer E2E must contain at least one synthetic document source"

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
    for path, text in candidates:
        assert any(marker in text for marker in markers), path
        for forbidden_marker in forbidden:
            assert forbidden_marker not in text, f"{path} persists forbidden Viewer artifact data: {forbidden_marker}"
