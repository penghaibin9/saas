import inspect

from app.services.sandbox_school_academic_flow_coverage import FLOWS
from app.services.sandbox_school_academic_flow_gap_seed import (
    _seed_applied_schedule_change_attendance,
    _seed_program_version_and_graduate,
    seed_academic_flow_gap_coverage,
)
from app.services.sandbox_school_affairs_seed import validate_affairs_facts
from app.services.sandbox_school_curriculum_closure import (
    EXPECTED_PROGRAMS,
    EXPECTED_PROGRAMS_AFTER_FLOW_COVERAGE,
    EXPECTED_PROGRAM_COURSES_AFTER_FLOW_COVERAGE,
    EXPECTED_PROGRAM_COURSES_FINAL,
    EXPECTED_SCHEDULE_ITEMS_AFTER_FLOW_COVERAGE,
    EXPECTED_TOTAL_SCHEDULE_ITEMS_FINAL,
    validate_school_academic_final_20k,
)


def test_all_24_academic_flows_have_strong_evidence_components():
    assert list(FLOWS) == [f"AA-{index:03d}" for index in range(1, 25)]
    assert all(len(components) >= 2 for components in FLOWS.values())
    assert all(component.sql.strip().upper().startswith("SELECT")
               for components in FLOWS.values() for component in components)


def test_cross_module_success_chains_are_not_table_nonempty_checks():
    by_code = {
        flow: {component.code: component.sql for component in components}
        for flow, components in FLOWS.items()
    }
    assert "t_workflow_instance" in by_code["AA-003"]["EFFECTIVE_CHANGE"]
    assert "t_aa_student_academic_fact" in by_code["AA-004"]["SPLIT_FACT"]
    assert "t_aa_teaching_class_member" in by_code["AA-011"]["SELECTION_ROSTER"]
    assert "t_aa_graduation_decision_fact" in by_code["AA-021"]["GRAD_PASSED"]
    assert "t_file_object" in by_code["AA-024"]["ACADEMIC_EXPORT"]


def test_clean_reset_seeds_an_applied_change_that_reaches_attendance():
    helper = inspect.getsource(_seed_applied_schedule_change_attendance)
    orchestrator = inspect.getsource(seed_academic_flow_gap_coverage)
    assert 'change.status = "APPLIED"' in helper
    assert 'change_id=change.id, status="EFFECTIVE"' in helper
    assert 'status="SUBMITTED"' in helper
    assert 'occurrence = f"{origin.batch_id}:{target.id}:' in helper
    assert "_seed_applied_schedule_change_attendance" in orchestrator


def test_final_scale_contract_counts_auditable_flow_versions():
    validator = inspect.getsource(validate_school_academic_final_20k)
    assert EXPECTED_PROGRAMS_AFTER_FLOW_COVERAGE == EXPECTED_PROGRAMS + 1
    assert (
        EXPECTED_PROGRAM_COURSES_AFTER_FLOW_COVERAGE
        == EXPECTED_PROGRAM_COURSES_FINAL + 18
    )
    assert (
        EXPECTED_SCHEDULE_ITEMS_AFTER_FLOW_COVERAGE
        == EXPECTED_TOTAL_SCHEDULE_ITEMS_FINAL + 1
    )
    assert '"programs": EXPECTED_PROGRAMS_AFTER_FLOW_COVERAGE' in validator
    assert (
        '"programCourses": EXPECTED_PROGRAM_COURSES_AFTER_FLOW_COVERAGE'
        in validator
    )
    assert (
        '"scheduleItems": EXPECTED_SCHEDULE_ITEMS_AFTER_FLOW_COVERAGE'
        in validator
    )


def test_core_flow_keeps_schedule_approval_and_thirteen_domain_manifest_chains():
    from app.services.sandbox_school_academic_core_flow_seed import (
        seed_academic_core_flows,
    )

    source = inspect.getsource(seed_academic_core_flows)
    assert "_repair_schedule_change_workflows" in source
    assert 'report["scheduleChangeWorkflow"]' in source
    assert 'json.loads(manifest_v1.domain_counts_json or "{}")' in source
    assert "len(domain_counts) != 13" in source
    assert "manifest_service._manifest_payload" in source
    assert 'domain_hashes["GRADE"]' in source


def test_graduation_sample_uses_append_only_discipline_revocation_chain():
    source = inspect.getsource(_seed_program_version_and_graduate)
    assert '_append_decision(' in source
    assert 'kind="REVOKED"' in source
    assert 'source_type="GRADUATION_CLEARANCE"' in source
    assert "_set_projection_decision" in source
    assert 'case.status = "REVOKED"' in source
    assert 'discipline.status = "REVOKED"' in source


def test_affairs_scale_validation_accepts_only_the_two_formal_discipline_stages():
    source = inspect.getsource(validate_affairs_facts)
    assert '"revokedDiscipline"' in source
    assert "allowed_discipline_lifecycles" in source
    assert "(EXPECTED_EFFECTIVE_DISCIPLINE, 0)" in source
    assert "(EXPECTED_EFFECTIVE_DISCIPLINE - 1, 1)" in source
    assert 'mismatch["disciplineLifecycle"]' in source
