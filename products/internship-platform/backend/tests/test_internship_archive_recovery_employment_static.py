from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_archive_manifest_and_revoke_share_one_transaction_owner():
    compat = read("backend/app/modules/internship/services/internship_material_center_compat.py")
    router = read("backend/app/modules/internship/routers/internship_material_center.py")
    assert "def archive_with_manifest" in compat
    archive_command = compat[compat.index("def archive_with_manifest"):compat.index("def revoke_with_manifests")]
    for step in (
        "prepare_archive_manifest_in_session",
        "archive_svc.archive_student_in_session",
        "finalize_manifest_in_session",
        "db.commit()",
    ):
        assert step in archive_command
    assert archive_command.index("prepare_archive_manifest_in_session") < archive_command.index(
        "archive_svc.archive_student_in_session"
    ) < archive_command.index("finalize_manifest_in_session") < archive_command.index("db.commit()")
    assert "archive_with_manifest" in router
    assert "revoke_with_manifests" in router
    assert "abort_manifest" not in router
    archive_route = router[router.index("def archive_student_guard"):router.index("def archive_preflight_guard")]
    assert 'require_permission("internship.archive.execute")' in archive_route


def test_total_archive_freezes_only_published_score_inside_shared_session():
    guard = read("backend/app/modules/internship/services/internship_score_archive_guard.py")
    assert "def _archive_student_in_session" in guard
    assert 'score.status != "PUBLISHED"' in guard
    assert 'snapshot["finalScoreFreeze"]' in guard
    assert 'snapshot["finalScoreFreezeHash"]' in guard
    assert "_archive.archive_student_in_session = _archive_student_in_session" in guard


def test_manifest_drift_and_restore_count_hash_mismatch_fail_closed():
    core = read("backend/app/modules/internship/services/internship_material_center_service.py")
    compat = read("backend/app/modules/internship/services/internship_material_center_compat.py")
    streaming = read("backend/app/modules/internship/services/internship_streaming_package_service.py")
    assert "def manifest_digest" in core
    assert "core.manifest_digest(manifest, items) != manifest.manifest_sha256" in streaming
    assert "core.manifest_digest(manifest, items) != manifest.manifest_sha256" in compat
    assert "def verify_package_for_restore" in streaming
    for evidence in (
        "package_hash != str(package.package_sha256",
        "len(infos) != len(manifest_items) + 1",
        "len(embedded_items) != len(manifest_items)",
        "digest.hexdigest() != str(frozen.sha256_snapshot",
        "int(package.row_count or 0) != 1",
        '"restoreReady": True',
    ):
        assert evidence in streaming


def test_employment_transition_requires_archived_published_frozen_result():
    archive = read("backend/app/modules/internship/services/internship_archive_service.py")
    router = read("backend/app/modules/internship/routers/internship_material_center.py")
    assert "def employment_transition_context" in archive
    command = archive[archive.index("def employment_transition_context"):archive.index("def build_package")]
    assert 'archive.status != "ARCHIVED"' in command
    assert 'InternshipFinalScore.status == "PUBLISHED"' in command
    assert 'frozen_hash = (archive.material_snapshot or {}).get("finalScoreFreezeHash")' in command
    assert '"resultAuthority": "PUBLISHED_FINAL_SCORE_FROZEN_IN_ARCHIVE"' in command
    assert "/employment-transition" in router


def test_archive_preflight_returns_fix_targets_file_safety_and_receipt():
    archive = read("backend/app/modules/internship/services/internship_archive_service.py")
    router = read("backend/app/modules/internship/routers/internship_material_center.py")
    for evidence in (
        "def preflight_archive",
        '"missingActions": missing_actions',
        '"fileVersionSafety"',
        '"preflightReceipt"',
        '"ARCHIVE_PREFLIGHT"',
    ):
        assert evidence in archive
    assert "/archive/{internship_id}/preflight" in router
    assert "/archive-packages/{package_id}/restore-check" in router


def test_advanced_journey_normalizes_employment_login_role_and_scope():
    seed = read("backend/scripts/e2e_seed_internship_v8_advanced_sandbox.py")
    helper = seed[seed.index("def ensure_employment_scope"):seed.index("def require_enterprise_collaborator")]
    for evidence in (
        'Role.role_code == "EMPLOYMENT_TEACHER"',
        'login_name="e2e_ix_employment"',
        'password_hash=hash_password("E2eTest@2026")',
        "db.add(UserRole(",
        'TeacherStudentScope.scope_type == "STUDENT"',
    ):
        assert evidence in helper
    assert "if user is None:\n        return" not in helper


def test_batch_archive_package_is_bounded_streamed_and_manifest_authoritative():
    streaming = read("backend/app/modules/internship/services/internship_streaming_package_service.py")
    archive = read("backend/app/modules/internship/services/internship_archive_service.py")
    router = read("backend/app/modules/internship/routers/internship_material_center.py")
    resolvers = read("backend/app/services/file_access_resolvers.py")
    for evidence in (
        "MAX_BATCH_ROWS = 20",
        "MAX_BATCH_FILES = 199",
        "MAX_BATCH_BYTES = 90 * 1024 * 1024",
        "def build_batch_versioned_package",
        'package_type="ARCHIVE_BATCH"',
        '"INTERNSHIP_ARCHIVE_BATCH_FILE_VERSION_V1"',
        "core.manifest_digest(manifest, items) != manifest.manifest_sha256",
        "add_path(",
        '"hasMore": has_more',
        "def _verify_batch_package_for_restore",
        "verified_files != int(package.file_count or 0)",
        "def resolve_batch_package_download",
    ):
        assert evidence in streaming
    assert 'InternshipEvidencePackage.package_type == "ARCHIVE_BATCH"' in archive
    assert "/archive-batches/{batch_id}/packages" in router
    assert "/archive-batch-packages/{package_id}/download" in router
    assert '@register_file_resolver("ARCHIVE_PACKAGE", "ARCHIVE_BATCH_PACKAGE")' in resolvers
    assert "len(records) != int(package.row_count or 0)" in resolvers
