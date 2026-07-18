from __future__ import annotations

from types import SimpleNamespace

from app.core.affairs_security import StudentAffairsSecurityContext


class CapturingSession:
    def __init__(self, result):
        self.result = result
        self.statement = None

    def scalar(self, statement):
        self.statement = statement
        return self.result

    def get(self, *_args, **_kwargs):
        raise AssertionError("require_student must not load a cross-tenant row by primary key")


def test_require_student_scopes_primary_lookup_in_sql():
    context = StudentAffairsSecurityContext(
        user_id="teacher-1",
        login_name="teacher-1",
        tenant_id=101,
        role_codes={"SCHOOL_ADMIN"},
        permission_codes=set(),
        sensitive_permissions=set(),
        scope_type="TENANT_ALL",
    )
    student = SimpleNamespace(id=9, tenant_id=101, class_id=3, is_deleted=False)
    db = CapturingSession(student)

    assert context.require_student(db, 9) is student

    sql = str(db.statement)
    assert "t_student_profile.id" in sql
    assert "t_student_profile.tenant_id" in sql
    assert "t_student_profile.is_deleted IS false" in sql
