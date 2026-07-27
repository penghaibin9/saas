"""P0-06：毕业审核培养方案历史生效解析。"""
from datetime import datetime
from types import SimpleNamespace


class _Rows:
    def __init__(self, rows):
        self.rows = list(rows)

    def all(self):
        return list(self.rows)


class _Db:
    def __init__(self, bindings, programs):
        self.bindings = list(bindings)
        self.programs = dict(programs)

    def scalars(self, _stmt):
        return _Rows(self.bindings)

    def get(self, _model, key):
        return self.programs.get(int(key))


def _binding(binding_id, program_id, *, status="ACTIVE", grade="2025", class_id=None, bound_at=None):
    return SimpleNamespace(
        id=binding_id,
        tenant_id=1,
        program_id=program_id,
        major_id=10,
        grade_year=grade,
        class_id=class_id,
        bound_at=bound_at,
        status=status,
        is_deleted=False,
    )


def _program(program_id, *, status="ENABLED", tenant_id=1):
    return SimpleNamespace(
        id=program_id,
        tenant_id=tenant_id,
        version=1,
        status=status,
        is_deleted=False,
    )


def _student(*, grade="2025", class_id=100):
    return SimpleNamespace(id=1, major_id=10, grade=grade, class_id=class_id)


def test_class_historical_binding_is_used_when_effective_at_audit_time():
    from app.modules.academic_affairs.services.student_program_resolution_service import resolve_student_program

    old = _binding(
        1, 11, status="SUPERSEDED", class_id=100,
        bound_at=datetime(2024, 9, 1),
    )
    result = resolve_student_program(
        _Db([old], {11: _program(11, status="FROZEN")}),
        _student(),
        tenant_id=1,
        as_of=datetime(2026, 7, 1),
    )

    assert result.status == "RESOLVED"
    assert result.rule == "CLASS_HISTORICAL_EFFECTIVE"
    assert result.program.id == 11


def test_future_historical_binding_is_not_used_early():
    from app.modules.academic_affairs.services.student_program_resolution_service import resolve_student_program

    future = _binding(
        1, 11, status="SUPERSEDED", class_id=100,
        bound_at=datetime(2027, 9, 1),
    )
    result = resolve_student_program(
        _Db([future], {11: _program(11)}),
        _student(),
        tenant_id=1,
        as_of=datetime(2026, 7, 1),
    )

    assert result.status == "MISSING"
    assert result.rule == "CLASS_BINDING_INVALID"


def test_latest_effective_grade_history_wins():
    from app.modules.academic_affairs.services.student_program_resolution_service import resolve_student_program

    older = _binding(1, 11, status="SUPERSEDED", bound_at=datetime(2023, 9, 1))
    latest = _binding(2, 12, status="SUPERSEDED", bound_at=datetime(2024, 9, 1))
    result = resolve_student_program(
        _Db([older, latest], {11: _program(11), 12: _program(12, status="PUBLISHED")}),
        _student(class_id=None),
        tenant_id=1,
        as_of=datetime(2026, 7, 1),
    )

    assert result.status == "RESOLVED"
    assert result.rule == "MAJOR_GRADE_HISTORICAL_EFFECTIVE"
    assert result.program.id == 12


def test_same_effective_time_history_is_ambiguous():
    from app.modules.academic_affairs.services.student_program_resolution_service import resolve_student_program

    when = datetime(2024, 9, 1)
    rows = [
        _binding(1, 11, status="SUPERSEDED", bound_at=when),
        _binding(2, 12, status="SUPERSEDED", bound_at=when),
    ]
    result = resolve_student_program(
        _Db(rows, {11: _program(11), 12: _program(12)}),
        _student(class_id=None),
        tenant_id=1,
        as_of=datetime(2026, 7, 1),
    )

    assert result.status == "AMBIGUOUS"
    assert result.rule == "MAJOR_GRADE_CONFLICT"


def test_other_grade_unique_binding_is_not_guessed():
    from app.modules.academic_affairs.services.student_program_resolution_service import resolve_student_program

    other_grade = _binding(1, 11, grade="2024")
    result = resolve_student_program(
        _Db([other_grade], {11: _program(11)}),
        _student(grade="2025", class_id=None),
        tenant_id=1,
    )

    assert result.status == "MISSING"
    assert result.rule == "NO_EFFECTIVE_BINDING"


def test_cross_tenant_program_cannot_be_selected():
    from app.modules.academic_affairs.services.student_program_resolution_service import resolve_student_program

    row = _binding(1, 11, class_id=100)
    result = resolve_student_program(
        _Db([row], {11: _program(11, tenant_id=2)}),
        _student(),
        tenant_id=1,
    )

    assert result.status == "MISSING"
    assert result.rule == "CLASS_BINDING_INVALID"
