from __future__ import annotations

import inspect

from app.api.v1.standalone_browser_auth import _channel_from_client_type
from app.modules.internship.services import internship_scope
from app.modules.internship.services import internship_student_dashboard_service as dashboard
from app.services.mobile_teacher_service import _db_user_id


def test_student_mini_uses_student_auth_channel():
    assert _channel_from_client_type("STUDENT_MINI") == "student"
    assert _channel_from_client_type("student_mini") == "student"
    assert _channel_from_client_type("STUDENT_PC") == "student"


def test_teacher_mini_remains_staff_auth_channel():
    assert _channel_from_client_type("TEACHER_MINI") == "staff"
    assert _channel_from_client_type("PC") == "staff"


def test_teacher_scope_normalizes_canonical_db_subject_user_id():
    assert _db_user_id("db-88113") == 88113
    assert _db_user_id("DB-88113") == 88113
    assert _db_user_id(88113) == 88113


def test_teacher_scope_rejects_non_database_subject_for_advisor_id():
    assert _db_user_id("mobile-INTERN_MENTOR") is None
    assert _db_user_id("") is None


def test_teacher_sql_scope_remains_stable_id_based_and_fail_closed():
    source = inspect.getsource(internship_scope.apply_internship_record_scope)
    advisor_start = source.index("if role in advisor_roles:")
    advisor_end = source.index("direct_major =", advisor_start)
    advisor_scope = source[advisor_start:advisor_end]
    assert "InternshipRecord.advisor_user_id.in_(advisor_ids)" in advisor_scope
    assert "InternshipRecord.advisor_name" not in advisor_scope
    assert "false()" in advisor_scope


def test_student_dashboard_uses_canonical_checkin_timestamp_field():
    source = inspect.getsource(dashboard.get_my_dashboard)
    assert 'getattr(checkin, "checkin_at", None)' in source
    assert 'getattr(checkin, "checkin_time", None)' not in source
