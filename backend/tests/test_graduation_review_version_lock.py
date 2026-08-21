"""W7.1 source-level safety contracts for formal review version locking.

Database/browser acceptance remains in the exact-head gates; these tests prevent accidental
removal of the P0 invariants while later W7 waves are added.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_submit_contract_carries_optimistic_and_file_version_identity():
    schema = _read("backend/app/modules/graduation/schemas/graduation_review.py")
    router = _read("backend/app/modules/graduation/routers/graduation_review.py")
    assert "expectedVersion" in schema
    assert "fileVersionId" in schema
    assert "expected_version=body.expectedVersion" in router
    assert "file_version_id=body.fileVersionId" in router


def test_assignment_ignores_caller_final_as_authority_and_freezes_approved_thesis_final():
    guard = _read("backend/app/modules/graduation/services/graduation_review_version_guard.py")
    assert 'GraduationFinal.final_type == "定稿"' in guard
    assert 'GraduationFinal.status == "APPROVED"' in guard
    assert 'GraduationStudentMaterial.material_code == "THESIS_FINAL"' in guard
    assert 'GraduationStudentMaterial.source_record_type == "FINAL"' in guard
    assert "material_id=int(material.id)" in guard
    assert "file_version_id=int(version.id)" in guard
    assert "source_sha256=digest" in guard


def test_submit_is_fail_closed_on_legacy_snapshot_version_hash_and_security_changes():
    guard = _read("backend/app/modules/graduation/services/graduation_review_version_guard.py")
    assert "该历史评阅任务缺少版本快照" in guard
    assert "APPROVAL_VERSION_CONFLICT" in guard
    assert "current_version_id" in guard
    assert "source_sha256" in guard
    assert "FILE_NOT_READY" in guard
    assert "FILE_HASH_MISSING" in guard
    assert "expected_version" in guard
    assert "file_version_id" in guard


def test_stable_reviewer_identity_and_sod_remain_required():
    guard = _read("backend/app/modules/graduation/services/graduation_review_version_guard.py")
    assert "sod_conflict_with_advisor" in guard
    assert "reviewer_mentor_id" in guard
    assert "current_user_mentor" in guard
    assert "当前账号不是该评阅任务指定评阅人" in guard


def test_migration_extends_existing_review_table_and_keeps_single_parent():
    migration = _read("backend/alembic/versions/20260821_gd_review_file_lock.py")
    assert 'down_revision = "20260820_teacher_emp_reco"' in migration
    assert 'op.add_column("t_gd_review"' in migration
    for field in ("material_id", "file_version_id", "source_sha256", "started_at"):
        assert field in migration
    assert "create_table" not in migration
