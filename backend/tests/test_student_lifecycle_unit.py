from app.core.student_lifecycle import (
    normalize_student_stage,
    student_lifecycle_phase,
    student_stage_label,
)
from app.models.student import StudentProfile


def test_runtime_aliases_are_read_as_frozen_lifecycle_codes():
    assert normalize_student_stage("ORIENTATION") == "ADMITTED"
    assert normalize_student_stage("ON_CAMPUS") == "ENROLLED"
    assert normalize_student_stage("studying") == "ENROLLED"
    assert normalize_student_stage("INTERNSHIP") == "INTERN"
    assert normalize_student_stage("GRADUATION_DESIGN") == "GRADUATING"
    assert normalize_student_stage("EMPLOYMENT") == "GRADUATING"
    assert student_stage_label("ON_CAMPUS") == "在读阶段"


def test_frozen_storage_values_form_four_primary_phases_and_two_terminal_states():
    assert student_lifecycle_phase("ADMITTED") == "ORIENTATION"
    assert student_lifecycle_phase("PRE_STUDENT_VERIFIED") == "ORIENTATION"
    assert student_lifecycle_phase("REGISTERED_PENDING_ENROLLMENT") == "ORIENTATION"
    assert student_lifecycle_phase("ENROLLED") == "ON_CAMPUS"
    assert student_lifecycle_phase("INTERN") == "INTERNSHIP"
    assert student_lifecycle_phase("GRADUATING") == "GRADUATION"
    assert student_lifecycle_phase("GRADUATED") == "GRADUATED"
    assert student_lifecycle_phase("ALUMNI") == "ALUMNI"
    assert student_stage_label("GRADUATION_DESIGN") == "毕业阶段"
    assert student_stage_label("EMPLOYMENT") == "毕业阶段"


def test_new_student_model_default_uses_frozen_enrolled_code():
    default = StudentProfile.__table__.c.current_stage.default
    assert default is not None
    assert default.arg == "ENROLLED"


def test_unknown_stage_is_visible_instead_of_silently_misclassified():
    assert normalize_student_stage("CUSTOM_STAGE") == "CUSTOM_STAGE"
    assert student_stage_label("CUSTOM_STAGE") == "CUSTOM_STAGE"
