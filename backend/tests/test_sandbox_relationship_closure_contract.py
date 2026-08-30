from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_schedule_seed_expands_each_task_to_weekly_sessions():
    source = _read("app/services/sandbox_school_academic_affairs_seed.py")
    closure = _read("app/services/sandbox_school_curriculum_closure.py")

    assert "EXPECTED_SCHEDULE_ITEMS = EXPECTED_TASKS * 2" in source
    assert source.count("for offset in range(int(task.weekly_hours or 0))") >= 2
    assert "EXPECTED_TOTAL_SCHEDULE_ITEMS_FINAL = EXPECTED_TOTAL_TASKS_FINAL * 2" in closure
    assert "EXPECTED_HISTORICAL_SCHEDULE_ITEMS_FINAL" in closure
    assert "for offset in range(int(task.weekly_hours or 0))" in closure
    assert "AaSchedulePublish(" in source


def test_pc_schedule_views_resolve_the_current_term_scopehead():
    source = _read(
        "app/modules/academic_affairs/services/academic_affairs_schedule_service.py"
    )

    assert "def _current_published_batch" in source
    assert "AaTerm.is_current.is_(True)" in source
    assert 'AaScheduleScopeHead.scope_type == "SCHOOL"' in source
    assert "AaScheduleScopeHead.active_batch_id.is_not(None)" in source
    assert "AaScheduleBatch.id == int(head.active_batch_id)" in source
    assert "AaScheduleBatch.term_id == resolved_term_id" in source


def test_archive_seed_uses_formal_thirteen_domain_manifest():
    source = _read("app/services/sandbox_school_academic_archive_seed.py")

    assert "manifest_service._live_manifest_parts" in source
    assert "manifest_service._manifest_payload" in source
    assert "ArchiveManifest(" in source


def test_attendance_seed_keeps_direct_teaching_task_identity():
    source = _read("app/services/sandbox_school_academic_r11_runtime_seed.py")

    assert '"teaching_task_id": int(task.id)' in source
    assert '"occurrence_identity": f"TASK:' in source
    assert '"source_type": "FORMAL_TEACHING"' in source


def test_relationship_audit_covers_every_core_domain_and_semantic_break():
    from app.services.sandbox_school_relationship_closure import CHECKS

    codes = {check.code for check in CHECKS}
    domains = {check.domain for check in CHECKS}
    assert len(codes) == len(CHECKS)
    assert len(CHECKS) >= 100
    assert {
        "master", "orientation", "academic", "campus", "internship",
        "graduation", "employment", "student_affairs", "academic_affairs",
        "academic_support", "communication",
    }.issubset(domains)
    assert {
        "AA_PUBLISHED_SCHEDULE_COMPLETE",
        "AA_EXAM_INCIDENT_PARENTS",
        "AA_EXAM_INCIDENT_DISCIPLINE",
        "AA_EXAM_GRADE_CANDIDATE",
        "AA_MAKEUP_BATCH_TERMINAL",
        "AA_SCHEDULE_CHANGE_WORKFLOW",
        "AA_SCHEDULE_CHANGE_ACTIVE_SCOPE",
        "AA_SCHEDULE_CHANGE_TASK",
        "AA_SCHEDULE_CHANGE_TODO",
        "AA_SCHEDULE_CHANGE_TARGET_LINK",
        "AA_ATTENDANCE_TASK",
        "AA_ATTENDANCE_SOURCE_TYPE",
        "ACAD_WARNING_GRADE_EVIDENCE",
        "ACAD_STUDENT_GRADE_WARNING_AGGREGATES",
        "AA_GRAD_AUDIT_RESULT",
        "AA_GRAD_ACADEMIC_STUDENT",
        "AA_GRAD_EVALUATION_RUN",
        "AA_GRAD_DECISION_RUN",
        "AA_GRAD_DECISION_WRITEBACK",
        "ACAD_GRADE_COURSE",
        "ACAD_GRADE_TERM",
        "ACAD_GRADE_PROVENANCE",
        "AA_ARCHIVE_MANIFEST",
        "AFFAIRS_FUNDING_DISBURSEMENT",
        "INTERN_COMPLIANCE_SCOPE",
        "GRAD_PROCESS_STUDENT",
        "MASTER_ROLE_SCOPE_ASSIGNMENT",
        "MASTER_ROLE_SCOPE_RESOURCE",
        "MASTER_MANUAL_ROLE_SCOPE_COVERAGE",
        "MASTER_PSY_SCOPE_COMPATIBILITY",
    }.issubset(codes)

    source = _read("app/services/sandbox_school_relationship_closure.py")
    assert '"brokenPublishedSchedules"' in source
    assert '"gradeCourseResolution"' in source
    assert '"gradeProvenanceByTerm"' in source
    assert '"latestArchiveManifests"' in source


def test_standard_20k_reset_requires_relationship_closure():
    source = _read("scripts/reset_sandbox_school.py")

    assert "require_sandbox_relationship_closure" in source
    assert '"relationshipClosure": require_sandbox_relationship_closure' in source


def test_safe_reconciler_only_backfills_unambiguous_sources():
    source = _read("app/services/sandbox_school_relationship_reconcile.py")

    assert "consumer_type='ATTENDANCE_SESSION'" in source
    assert "a.teaching_task_id IS NULL" in source
    assert "safeToRepair" in source
    assert "missingSchedulePublishLedgers" in source
    assert "只允许修复 sandbox-school" in source
    assert "t_acad_grade" not in source
    assert "_repair_schedule_change_workflows" in source
    assert "_rebase_schedule_change_origins" in source
    assert "RECONCILE_WORKFLOW" in source
    assert "REBASE_ACTIVE_SCOPE" in source


def test_sandbox_roles_create_unique_academic_approval_responsibilities():
    roles = _read("app/services/sandbox_school_role_reconcile.py")
    assignee = _read(
        "app/modules/academic_affairs/services/academic_affairs_grade_task_assignee_guard.py"
    )

    assert "ensure_school_approval_responsibilities" in roles
    assert 'assignment_type="SECRETARY"' in roles
    assert 'assignment_type="ACADEMIC_REVIEWER"' in roles
    assert "college.secretary_id = secretary_id" in roles
    assert 'StaffAssignment.assignment_type == "ACADEMIC_REVIEWER"' in assignee


def test_sandbox_role_scopes_project_legacy_business_facts_to_stable_ids():
    policy = _read("app/services/role_assignment_scope_service.py")
    projection = _read("app/services/sandbox_school_role_scope_reconcile.py")
    reconciler = _read("app/services/sandbox_school_relationship_reconcile.py")
    role_seed = _read("app/services/sandbox_school_role_reconcile.py")

    assert "ROLE_TEMPLATE_BY_CODE" in policy
    assert 'template["defaultScope"]' in policy
    assert "reconcile_sandbox_role_assignment_scopes" in projection
    assert 'source_type="PROJECTED"' in projection
    assert 'scope_type="PSY_STUDENT"' in projection
    assert "AaTeachingTask.teacher_key == user.login_name" in projection
    assert "reconcile_sandbox_role_assignment_scopes" in reconciler
    assert "reconcile_sandbox_role_assignment_scopes" in role_seed


def test_role_assignment_scope_collation_matches_legacy_role_codes():
    migration = _read(
        "alembic/versions/20260830_role_assignment_scope_collation.py"
    )

    assert 'down_revision = "20260829_pr236_main_merge"' in migration
    assert 'TARGET_COLLATION = "utf8mb4_unicode_ci"' in migration
    assert "CONVERT TO CHARACTER SET" in migration
    assert "t_role_assignment_scope" in migration


def test_discipline_readonly_check_accepts_one_formally_revoked_chain():
    source = _read("app/services/sandbox_school_discipline_decision_reconcile.py")

    assert "revoked_cases in (0, 1)" in source
    assert "linked_revoked == revoked_cases" in source
    assert "GRADUATION_CLEARANCE" in source
    assert "previous.decision_kind = 'ORIGINAL'" in source


def test_academic_main_chain_verifier_uses_cross_module_business_identities():
    source = _read("scripts/verify_sandbox_academic_main_chain.py")
    change = _read(
        "app/modules/academic_affairs/services/academic_affairs_schedule_change_service.py"
    )

    assert "scheduleChangeToFourEnds" in source
    assert "changeToAttendance" in source
    assert "examToGradeToWarning" in source
    assert "graduationAudit" in source
    assert "gt.teaching_task_id=ec.teaching_task_id" in source
    assert "gr.student_id=ers.student_id" in source
    assert "d.evaluation_run_id=run.id" in source
    assert "Residual source segments are ordinary" in change
    assert "source=origin.source, change_id=None" in change


def test_grade_relationship_reconciler_uses_real_course_and_snapshot_evidence():
    source = _read("app/services/sandbox_school_grade_relationship_reconcile.py")
    archive = _read("app/services/sandbox_school_academic_archive_seed.py")
    curriculum = _read("app/services/sandbox_school_curriculum_closure.py")

    assert 'PROVENANCE_TYPE = "EFFECTIVE_GRADE_POLICY_SNAPSHOT"' in source
    assert "snap.academic_grade_id=g.id" in source
    assert "AcademicGrade.course_id.is_(None)" in source
    assert "courseRowsUpdated" in source
    assert "高等数学" in curriculum and '"PUB013"' in curriculum
    assert "reconcile_sandbox_grade_relationships" in archive
