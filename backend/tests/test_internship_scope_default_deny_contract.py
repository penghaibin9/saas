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


def test_signed_college_claims_are_consumed_as_stable_scope_and_empty_stays_denied(monkeypatch):
    from app.modules.internship.services import internship_scope

    monkeypatch.setattr("app.services.mobile_teacher_service.resolve_teacher_scope", lambda _user: {
        "mode": "SCOPED", "by": "DEFAULT_DENY", "roleCode": "COLLEGE_ADMIN",
        "studentNos": set(), "classNames": set(), "collegeNames": set(),
        "advisorUserIds": set(), "advisorNames": set(),
    })
    scoped = internship_scope.resolve_internship_scope({
        "currentRoleCode": "COLLEGE_ADMIN", "collegeIds": ["21", "bad", 22],
    })
    assert scoped["mode"] == "SCOPED"
    assert scoped["by"] == "ROLE_ASSIGNMENT_SCOPE"
    assert scoped["collegeIds"] == {21, 22}

    denied = internship_scope.resolve_internship_scope({"currentRoleCode": "COLLEGE_ADMIN"})
    assert denied["mode"] == "SCOPED"
    assert denied["by"] == "DEFAULT_DENY"
    assert "collegeIds" not in denied


def test_signed_scope_replaces_stale_legacy_scope_instead_of_union(monkeypatch):
    monkeypatch.setattr("app.services.mobile_teacher_service.resolve_teacher_scope", lambda _user: {
        "mode": "SCOPED", "by": "LEGACY", "roleCode": "COLLEGE_ADMIN",
        "studentNos": {"STUDENT-IN-COLLEGE-B"}, "classNames": {"B班"},
        "collegeNames": {"学院B"}, "advisorUserIds": {99}, "advisorNames": {"旧导师"},
    })

    scope = internship_scope.resolve_internship_scope({
        "currentRoleCode": "COLLEGE_ADMIN", "collegeIds": [21],
    })

    assert scope["collegeIds"] == {21}
    assert scope["studentNos"] == set()
    assert scope["classNames"] == set()
    assert scope["collegeNames"] == set()
    assert scope["advisorUserIds"] == set()
    assert scope["advisorNames"] == set()


def test_college_claim_filters_by_stable_id_not_another_college(monkeypatch):
    from app.modules.internship.services import internship_student_service
    monkeypatch.setattr(internship_scope, "_tid", lambda: 1001)
    monkeypatch.setattr(internship_student_service, "_current_scope", lambda _user: {
        "mode": "SCOPED", "roleCode": "COLLEGE_ADMIN", "collegeIds": {21},
    })
    sql = _sql(internship_scope.apply_internship_record_scope(select(InternshipRecord), {}))

    assert "student_profile.college_id in (21)" in sql
    assert "student_profile.college_id in (22)" not in sql


def test_single_and_preloaded_scope_use_same_college_precedence(monkeypatch):
    from types import SimpleNamespace
    from app.models import Major, SchoolClass

    def tenant_get(_db, model, _id):
        if model is SchoolClass:
            return SimpleNamespace(major_id=10)
        if model is Major:
            return SimpleNamespace(college_id=21)
        return None

    monkeypatch.setattr("app.core.tenant_scoped.tenant_get", tenant_get)
    scope = {"collegeIds": {21}}
    class_major_ids = {30: 10}
    major_college_ids = {10: 21}
    cases = [
        (SimpleNamespace(id=1, class_id=30, major_id=None, college_id=None), True),
        (SimpleNamespace(id=2, class_id=30, major_id=10, college_id=22), False),
        (SimpleNamespace(id=3, class_id=None, major_id=None, college_id=21), True),
    ]

    for student, expected in cases:
        single = internship_scope._student_matches_stable_scope(object(), scope, student)
        preloaded = internship_scope._student_matches_stable_scope_preloaded(
            scope, student, class_major_ids=class_major_ids,
            major_college_ids=major_college_ids,
        )
        assert single is expected
        assert preloaded is expected


def test_advisor_identity_guard_uses_role_scope_ids_and_keeps_cross_college_denied(monkeypatch):
    from types import SimpleNamespace
    from app.modules.internship.services import internship_advisor_identity_guard as guard
    from app.modules.internship.services import internship_service

    monkeypatch.setattr(internship_service, "resolve_student_class_college_names",
                        lambda _db, _student: (None, None))
    scope = {
        "mode": "SCOPED", "roleCode": "COLLEGE_ADMIN", "collegeIds": {21},
        "studentNos": set(), "classNames": set(), "collegeNames": set(),
        "advisorNames": set(), "advisorUserIds": set(),
    }
    record = SimpleNamespace(advisor_user_id=None, advisor_name="不用于学院授权")
    in_college = SimpleNamespace(id=101, college_id=21, major_id=None,
                                  class_id=None, student_no="S-A")
    out_of_college = SimpleNamespace(id=202, college_id=22, major_id=None,
                                     class_id=None, student_no="S-B")

    assert guard._scope_rec_in_scope(scope, object(), record, in_college) is True
    assert guard._scope_rec_in_scope(scope, object(), record, out_of_college) is False
    assert guard._domain_rec_in_scope_pre(
        scope, record, in_college, {}, {}, {},
    ) is True
    assert guard._domain_rec_in_scope_pre(
        scope, record, out_of_college, {}, {}, {},
    ) is False


def test_trends_mentor_scope_never_falls_back_to_advisor_name():
    source = (internship_scope.__file__.replace("internship_scope.py", "internship_stats_service.py"))
    text = open(source, encoding="utf-8").read()
    trends = text[text.index("def trends("):text.index("def export_stats(")]

    assert "InternshipRecord.advisor_user_id.in_(advisor_user_ids)" in trends
    assert "InternshipRecord.advisor_name" not in trends
