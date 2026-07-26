"""毕业审核必须精确解析学生培养方案，关键 UNKNOWN 不得被当成系统通过。"""
from types import SimpleNamespace


class _ScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeDb:
    def __init__(self, bindings, programs):
        self.bindings = list(bindings)
        self.programs = dict(programs)

    def scalars(self, _stmt):
        return _ScalarRows(self.bindings)

    def get(self, _model, key):
        return self.programs.get(int(key))


def _binding(bid, program_id, *, major_id=10, grade="2025", class_id=None):
    return SimpleNamespace(
        id=bid, program_id=program_id, major_id=major_id,
        grade_year=grade, class_id=class_id, status="ACTIVE", is_deleted=False,
    )


def _program(pid, version="V1", status="ENABLED"):
    return SimpleNamespace(id=pid, tenant_id=1, version=version, status=status, is_deleted=False)


def _student(*, grade="2025", class_id=100, major_id=10):
    return SimpleNamespace(id=1, grade=grade, class_id=class_id, major_id=major_id)


def test_class_binding_has_highest_priority():
    from app.modules.academic_affairs.services.student_program_resolution_service import resolve_student_program

    p1, p2 = _program(1, "年级版"), _program(2, "班级特例版")
    db = _FakeDb([
        _binding(11, 1, grade="2025"),
        _binding(12, 2, grade="2025", class_id=100),
    ], {1: p1, 2: p2})

    result = resolve_student_program(db, _student(), tenant_id=1)

    assert result.status == "RESOLVED"
    assert result.rule == "CLASS_BINDING"
    assert result.program.id == 2


def test_major_grade_binding_is_used_when_no_class_override():
    from app.modules.academic_affairs.services.student_program_resolution_service import resolve_student_program

    p1, p2 = _program(1, "2024版"), _program(2, "2025版")
    db = _FakeDb([
        _binding(11, 1, grade="2024"),
        _binding(12, 2, grade="2025"),
    ], {1: p1, 2: p2})

    result = resolve_student_program(db, _student(class_id=999), tenant_id=1)

    assert result.status == "RESOLVED"
    assert result.rule == "MAJOR_GRADE_BINDING"
    assert result.program.id == 2


def test_ambiguous_same_grade_bindings_are_not_guessed():
    from app.modules.academic_affairs.services.student_program_resolution_service import resolve_student_program

    db = _FakeDb([
        _binding(11, 1, grade="2025"),
        _binding(12, 2, grade="2025"),
    ], {1: _program(1), 2: _program(2)})

    result = resolve_student_program(db, _student(class_id=None), tenant_id=1)

    assert result.status == "AMBIGUOUS"
    assert result.program is None


def test_disabled_program_is_not_selected():
    from app.modules.academic_affairs.services.student_program_resolution_service import resolve_student_program

    db = _FakeDb([_binding(11, 1)], {1: _program(1, status="DISABLED")})

    result = resolve_student_program(db, _student(class_id=None), tenant_id=1)

    assert result.status == "MISSING"
    assert result.program is None


def test_critical_unknown_blocks_system_pass():
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as service

    items = [
        {"item": "STATUS", "result": "PASS"},
        {"item": "CREDIT", "result": "UNKNOWN"},
        {"item": "EMPLOYMENT", "result": "UNKNOWN"},
    ]

    assert service._overall(items) == "SYSTEM_ABNORMAL"


def test_non_blocking_reminders_can_remain_unknown():
    from app.modules.academic_affairs.services import academic_affairs_graduation_service as service

    items = [
        {"item": "STATUS", "result": "PASS"},
        {"item": "CREDIT", "result": "PASS"},
        {"item": "EMPLOYMENT", "result": "UNKNOWN"},
        {"item": "FEE", "result": "UNKNOWN"},
    ]

    assert service._overall(items) == "SYSTEM_PASSED"
