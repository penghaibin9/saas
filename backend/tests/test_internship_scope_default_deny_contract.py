"""SQL 范围收敛必须保留 DEFAULT_DENY，不能因本人恰好是指导老师而扩权。"""

from sqlalchemy import select
from sqlalchemy.dialects import mysql

from app.models import InternshipRecord
from app.modules.internship.services import internship_scope
from app.modules.internship.services import internship_student_service


def _sql(statement):
    return str(statement.compile(
        dialect=mysql.dialect(), compile_kwargs={"literal_binds": True},
    )).lower()


def test_non_advisor_with_only_own_advisor_id_stays_default_deny(monkeypatch):
    monkeypatch.setattr(internship_scope, "_tid", lambda: 1001)
    monkeypatch.setattr(internship_student_service, "_current_scope", lambda _user: {
        "mode": "SCOPED", "roleCode": "ACADEMIC_TEACHER",
        "studentNos": set(), "classNames": set(), "collegeNames": set(),
        "advisorUserIds": {42}, "advisorNames": {"历史导师"},
    })

    statement = internship_scope.apply_internship_record_scope(select(InternshipRecord), {})
    where_sql = _sql(statement.whereclause)

    assert "advisor_user_id" not in where_sql
    assert "false" in where_sql or "0 = 1" in where_sql


def test_legacy_gd_mentor_role_keeps_stable_advisor_id_scope(monkeypatch):
    monkeypatch.setattr(internship_scope, "_tid", lambda: 1001)
    monkeypatch.setattr(internship_student_service, "_current_scope", lambda _user: {
        "mode": "SCOPED", "roleCode": "GD_MENTOR", "advisorUserIds": {42},
    })

    sql = _sql(internship_scope.apply_internship_record_scope(select(InternshipRecord), {}))

    assert "advisor_user_id" in sql
    assert "42" in sql


def test_trends_mentor_scope_never_falls_back_to_advisor_name():
    source = (internship_scope.__file__.replace("internship_scope.py", "internship_stats_service.py"))
    text = open(source, encoding="utf-8").read()
    trends = text[text.index("def trends("):text.index("def export_stats(")]

    assert "InternshipRecord.advisor_user_id.in_(advisor_user_ids)" in trends
    assert "InternshipRecord.advisor_name" not in trends
