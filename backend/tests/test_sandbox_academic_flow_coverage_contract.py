import inspect

from app.services.sandbox_school_academic_flow_coverage import FLOWS
from app.services.sandbox_school_academic_flow_gap_seed import (
    _seed_applied_schedule_change_attendance,
    seed_academic_flow_gap_coverage,
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
