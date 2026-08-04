"""教务 P0 收口的最小、稳定回归合同。"""
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "app/modules/academic_affairs/services"


def _grade(row_id, attempt, score, strategy=None, source="PUBLISH"):
    return SimpleNamespace(
        id=row_id,
        acad_student_id=1,
        course_id=101,
        course_code="JAVA_BASIC",
        course_version=1,
        course_name="Java程序设计",
        nature="REQUIRED",
        credit_value=4,
        attempt_no=attempt,
        score=score,
        pass_status="PASSED" if score >= 60 else "FAILED",
        record_status="ACTIVE",
        source=source,
        exam_type="FINAL",
        effective_attempt_strategy=strategy,
        effective_policy_code=f"{strategy}_V1" if strategy else None,
        effective_policy_version=1 if strategy else None,
    )


def test_prerequisite_loader_normalizes_and_rejects_corruption():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services.academic_affairs_selection_service import _load_prerequisite_codes

    course = SimpleNamespace(
        course_code="WEB",
        prerequisite_codes_json='[" java_basic ", "JAVA_BASIC", "DB"]',
    )
    assert _load_prerequisite_codes(course) == {"JAVA_BASIC", "DB"}

    try:
        _load_prerequisite_codes(
            SimpleNamespace(course_code="WEB", prerequisite_codes_json="{broken")
        )
    except AppException as exc:
        assert exc.code == "DATA_CONFLICT"
    else:
        raise AssertionError("损坏先修 JSON 必须失败关闭")


def test_tenant_effective_grade_policy_matrix():
    from app.modules.academic_affairs.services import academic_affairs_effective_grade_policy_compat  # noqa: F401
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import resolve_effective_grade

    rows = [_grade(1, 1, 75, "HIGHEST_PASSED"), _grade(2, 2, 55, "HIGHEST_PASSED")]
    assert resolve_effective_grade(rows)[0].id == 1

    rows = [_grade(1, 1, 55, "LATEST_PASSED"), _grade(2, 2, 65, "LATEST_PASSED")]
    assert resolve_effective_grade(rows)[0].id == 2

    rows = [_grade(1, 1, 90, "HIGHEST_SCORE"), _grade(2, 2, 70, "HIGHEST_SCORE")]
    assert resolve_effective_grade(rows)[0].id == 1

    rows = [
        _grade(1, 1, 75, "RETAKE_OVERRIDE_ONLY_IF_PASSED"),
        _grade(2, 2, 55, "RETAKE_OVERRIDE_ONLY_IF_PASSED"),
    ]
    assert resolve_effective_grade(rows)[0].id == 1


def test_migration_history_uses_explicit_legacy_v1_without_blocking_reads():
    from app.modules.academic_affairs.services import academic_affairs_effective_grade_policy_compat  # noqa: F401
    from app.modules.academic_affairs.services.academic_affairs_effective_grade_policy_service import resolve_effective_grade

    rows = [_grade(1, 1, 75), _grade(2, 2, 55)]
    selected = resolve_effective_grade(rows)
    assert len(selected) == 1
    assert selected[0].id == 2


def test_credit_progress_has_no_fake_default_and_exposes_unresolved_contract():
    mobile = (SERVICES / "mobile_academic_affairs_service.py").read_text(encoding="utf-8")
    resolver = (SERVICES / "student_program_resolution_service.py").read_text(encoding="utf-8")
    model = (ROOT / "app/models/academic.py").read_text(encoding="utf-8")

    assert "120.0" not in mobile
    assert "default=120" not in model
    assert "credit_requirement_payload" in mobile
    assert '"resolutionStatus": "RESOLVED" if resolved else "UNRESOLVED"' in resolver
    assert '"requiredCredits": required if resolved else None' in resolver
    assert '"canJudgeGraduation": bool(resolved)' in resolver


def test_grade_recheck_is_append_only_archive_guarded_and_uses_snapshot_pass_line():
    source = (SERVICES / "academic_affairs_grade_recheck_service.py").read_text(encoding="utf-8")
    assert "guard_term_writable" in source
    assert 'grade.record_status = "SUPERSEDED"' in source
    assert "corrected = AcademicGrade(" in source
    assert "AaGradeCorrection(" in source
    assert 'pass_status = "PASSED" if score >= pass_line else "FAILED"' in source
    assert "pass_line_snapshot" in source
    assert "grade.score = score" not in source


def test_stats_snapshot_permissions_and_sql_scope_are_separate():
    router = (ROOT / "app/modules/academic_affairs/routers/stats_snapshot_router.py").read_text(encoding="utf-8")
    service = (SERVICES / "academic_affairs_stats_snapshot_service.py").read_text(encoding="utf-8")

    assert "academicAffairs.stats.snapshot.view" in router
    assert "academicAffairs.stats.snapshot.create" in router
    assert "academicAffairs.stats.snapshot.manage" in router
    assert '"ACADEMIC_TEACHER"' not in service
    assert ".offset((page - 1) * page_size).limit(page_size)" in service
    assert "query.count()" in service


def test_teaching_task_projection_uses_one_transaction():
    service = (SERVICES / "academic_affairs_task_service.py").read_text(encoding="utf-8")
    generation = (SERVICES / "academic_affairs_task_generation_service.py").read_text(encoding="utf-8")

    assert "generation.generate_batch_tx(db, body, user)" in service
    assert "sync_batch_teaching_classes(db, batch_id)" in service
    assert "def generate_batch_tx(db, body, user)" in generation
    generate_block = service.split("def generate_batch(body, user)", 1)[1].split("def assign_teacher", 1)[0]
    assert generate_block.index("sync_batch_teaching_classes") < generate_block.index("db.commit()")


def test_teacher_grade_entry_never_persists_class_scores_locally():
    page = (ROOT.parent / "miniapp/src/pages/teacher/academic-affairs/grade-entry.vue").read_text(encoding="utf-8")
    assert "uni.setStorageSync" not in page
    assert "uni.getStorageSync" not in page
    assert "scores: draftScores" not in page
    assert "离开后将丢失" in page
