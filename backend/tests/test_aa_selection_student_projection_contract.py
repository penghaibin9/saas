"""B-W5 student selection projection static contract.

The projection is a read model only. It must be owned by the final Selection service,
share one internal decision evaluator with student preflight, and survive the D6 read
optimization binding without falling back to legacy ``_course_dto``.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICES = ROOT / "backend/app/modules/academic_affairs/services"
FINAL = SERVICES / "academic_affairs_selection_final_service.py"
READ = SERVICES / "academic_affairs_selection_read_service.py"
READ_CORE = SERVICES / "academic_affairs_selection_read_core_service.py"


REQUIRED_PROJECTION_FIELDS = (
    '"status"',
    '"statusLabel"',
    '"phase"',
    '"eligibility"',
    '"allowedActions"',
    '"reason"',
    '"howToResolve"',
    '"window"',
    '"lottery"',
    '"reselect"',
)


def _block(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


def test_final_service_owns_single_student_course_decision_evaluator():
    source = FINAL.read_text(encoding="utf-8")
    assert "def _evaluate_student_course(" in source

    preflight = _block(source, "def student_preflight(", "def student_enroll(")
    courses = _block(source, "def student_courses(", "def batch_preflight(")

    assert "_evaluate_student_course(" in preflight
    assert "_evaluate_student_course(" in courses
    assert "student_preflight(" not in courses


def test_student_course_projection_freezes_b_c3_fields_and_server_actions():
    source = FINAL.read_text(encoding="utf-8")
    courses = _block(source, "def student_courses(", "def batch_preflight(")

    for field in REQUIRED_PROJECTION_FIELDS:
        assert field in courses, f"B-C3 projection missing {field}"

    assert '"VIEW"' in courses
    assert '"ENROLL"' in source
    assert '"DROP"' in source
    assert "allowedActions" in courses


def test_d6_read_binding_cannot_downgrade_w5_projection():
    read_source = READ.read_text(encoding="utf-8")
    assert "academic_affairs_selection_final_service" in read_source
    assert "_final_student_courses_projection" in read_source
    assert "_final.student_courses" in read_source
    assert 'status == "OPEN"' in read_source
    assert 'status == "CLOSED"' in read_source
    assert 'course.get("reselect")' in read_source
    assert "_read_core.student_courses" not in read_source

    core_source = READ_CORE.read_text(encoding="utf-8")
    assert "AaSelectionCourse.batch_id.in_(batch_ids)" in core_source
    assert "by_batch" in core_source
