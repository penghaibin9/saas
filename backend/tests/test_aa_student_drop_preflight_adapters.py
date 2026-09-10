"""Student PC/mobile must reach DROP's read-only owner, never ENROLL or a writer.

These are adapter tests; canonical MySQL rules and browser acceptance are separate.
"""
import pytest

from app.core.exceptions import AppException
from app.modules.academic_affairs.services import academic_affairs_selection_final_service as canonical
from app.modules.academic_affairs.services import mobile_academic_affairs_service as mobile
from app.student_portal.services import academic_service as portal


STUDENT = {"userType": "STUDENT", "userId": "db-101"}


@pytest.mark.parametrize("adapter", [mobile.selection_drop_preflight_my, portal.selection_drop_preflight])
@pytest.mark.parametrize("allowed", [True, False])
def test_only_drop_owner_receives_original_actor_and_exact_long_id(monkeypatch, adapter, allowed):
    calls = []
    course_id = "9007199254740993"
    decision = {"action": "DROP", "allowed": allowed, "selectionCourseId": course_id}

    def preflight(user, body):
        calls.append((user, vars(body)))
        return decision

    def forbidden(*args, **kwargs):
        pytest.fail("A DROP preflight must not invoke ENROLL eligibility or a business writer")

    monkeypatch.setattr(canonical, "student_drop_preflight", preflight)
    for name in ("student_preflight", "student_enroll", "student_drop"):
        monkeypatch.setattr(canonical, name, forbidden)
    result = adapter(STUDENT, {"selectionCourseId": course_id, "studentId": "999", "action": "ENROLL"})
    assert result is decision
    assert calls == [(STUDENT, {"selectionCourseId": course_id})]


@pytest.mark.parametrize("course_id", [None, True, False, 0, -1, "", "1.5", "x", 1.5, [], "１２"])
def test_invalid_identity_never_reaches_canonical(monkeypatch, course_id):
    def forbidden(*args):
        pytest.fail("Invalid identity must be rejected before querying the canonical owner")
    monkeypatch.setattr(canonical, "student_drop_preflight", forbidden)
    with pytest.raises(AppException) as error:
        mobile.selection_drop_preflight_my(STUDENT, {"selectionCourseId": course_id})
    assert error.value.code == "VALIDATION_ERROR"


@pytest.mark.parametrize("adapter", [mobile.selection_drop_preflight_my, portal.selection_drop_preflight])
def test_non_student_is_rejected_before_query(monkeypatch, adapter):
    def forbidden(*args):
        pytest.fail("Non-student must not query a student's selection records")
    monkeypatch.setattr(canonical, "student_drop_preflight", forbidden)
    with pytest.raises(AppException) as error:
        adapter({"userType": "TEACHER", "userId": "db-101"}, {"selectionCourseId": "10"})
    assert error.value.code == "NO_PERMISSION"


def test_both_public_routers_register_authenticated_drop_preflight():
    from app.api.v1 import mobile as mobile_router
    from app.student_portal import router as portal_router

    for public, suffix, endpoint in (
        (mobile_router.router, "/academic/selection/drop-preflight", mobile_router.academic_selection_drop_preflight),
        (portal_router.router, "/academic/course-selection/drop-preflight", portal_router.academic_course_drop_preflight),
    ):
        matches = [r for r in public.routes if getattr(r, "path", "").endswith(suffix) and "POST" in getattr(r, "methods", set())]
        assert len(matches) == 1
        assert matches[0].endpoint is endpoint
        assert any(d.name == "user" for d in matches[0].dependant.dependencies)
