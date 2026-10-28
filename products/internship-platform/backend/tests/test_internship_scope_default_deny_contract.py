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


def test_trends_mentor_scope_never_falls_back_to_advisor_name(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    from app.modules.internship.services import internship_stats_service as stats
    from app.modules.internship.services import internship_batch_context

    statements = []
    class Database:
        def execute(self, statement):
            statements.append(_sql(statement))
            return SimpleNamespace(all=lambda: [])

    @contextmanager
    def session():
        yield Database()

    monkeypatch.setattr(stats, 'session', session)
    monkeypatch.setattr(stats, '_tid', lambda: 1001)
    monkeypatch.setattr(stats, '_scope_ctx', lambda user: {
        'mode': 'SCOPED', 'roleCode': 'INTERN_MENTOR', 'advisorUserIds': {42},
        'advisorNames': {'同名教师'},
    })
    monkeypatch.setattr(internship_batch_context, 'resolve_batch',
                        lambda *args, **kwargs: SimpleNamespace(id=99))
    result = stats.trends({}, batch_id=99)
    assert len(statements) == 4
    assert all('advisor_user_id in (42)' in sql and 'advisor_name' not in sql for sql in statements)
    assert all(point['value'] == 0 for series in result['series'] for point in series['points'])
