from app.services.sandbox_school_academic_flow_coverage import FLOWS


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
