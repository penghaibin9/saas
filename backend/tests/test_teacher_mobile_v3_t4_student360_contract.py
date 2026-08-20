from __future__ import annotations

import inspect

from app.api.v1 import teacher_mobile_students as student_api
from app.services import teacher_mobile_student360_projection_service as projection


def test_t4_student360_projection_is_sql_scoped_and_read_only_composition():
    source = inspect.getsource(projection)
    assert "compile_teacher_student_visibility" in source
    assert "StudentProfile.phone" not in source
    assert "phone_encrypted" not in source
    assert "id_card" not in source.lower()
    assert ".limit(10)" in source
    assert "cache_set" not in source
    assert "redis" not in source.lower() or "second Redis version authority" in source
    assert "PsyReferral" not in source
    assert "mental_flag" in source
    assert "CsDiscipline" in source


def test_t4_student360_actions_are_object_context_not_new_command_authority():
    source = inspect.getsource(projection.get_projection)
    for key in ("RECORD_CONTACT", "NEW_TALK", "FAMILY_CONTACT", "EMPLOYMENT_FOLLOWUP"):
        assert f'"key": "{key}"' in source
    assert '"internshipId"' in source
    assert '"employmentStudentId"' in source
    assert "create_talk" not in source
    assert "create_contact" not in source
    assert "create_referral" not in source
    assert "create_follow" not in source


def test_t4_sensitive_zone_never_projects_psychological_or_discipline_detail():
    source = inspect.getsource(projection.get_projection)
    assert '"detailRestricted": True' in source
    assert '"mental"' in source
    assert '"discipline"' in source
    for forbidden in ("reason_summary", "counselor_note", "doc_no", "discipline.reason"):
        assert forbidden not in source


def test_t4_projection_version_consumes_shared_freshness_when_handoff_exists():
    source = inspect.getsource(projection._projection_version)
    assert "mobile_freshness_service" in source
    assert "projection_version" in source
    assert 'scoped["studentId"]' in source
    assert "increment_with_ttl" not in source
    assert "cache_set" not in source


def test_t4_student360_route_is_additive_under_teacher_mobile_students_router():
    paths = {route.path for route in student_api.router.routes}
    assert "/students" in paths
    assert "/students/{student_id}/projection" in paths


def test_t4_risk_rollup_prefers_high_then_medium_then_low():
    assert projection._risk_level(warning_count=0, internship_risk="LOW", affairs_risk="LOW") == "LOW"
    assert projection._risk_level(warning_count=1, internship_risk="LOW", affairs_risk="LOW") == "MEDIUM"
    assert projection._risk_level(warning_count=0, internship_risk="HIGH", affairs_risk="LOW") == "HIGH"
