"""B-W5 student selection projection static contract.

The projection is a read model only.  It must be owned by the final Selection service,
share one internal decision evaluator with student preflight, and never fan out into
per-course public preflight calls.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "backend/app/modules/academic_affairs/services/academic_affairs_selection_final_service.py"


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
