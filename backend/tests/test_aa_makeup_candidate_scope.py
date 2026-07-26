"""补考候选不得跨学院/班级泄漏。"""
from types import SimpleNamespace


def _student(student_id, class_id):
    return SimpleNamespace(id=student_id, class_id=class_id)


class _Ctx:
    def __init__(self, allowed):
        self.allowed = allowed

    def allowed_class_ids(self, _db):
        return self.allowed


def test_tenant_all_scope_keeps_all_students():
    from app.modules.academic_affairs.services import academic_affairs_makeup_facade as service

    students = [_student(1, 10), _student(2, 20)]
    result = service._filter_students_by_scope(_Ctx(None), object(), students)

    assert [item.id for item in result] == [1, 2]


def test_college_scope_keeps_only_allowed_classes():
    from app.modules.academic_affairs.services import academic_affairs_makeup_facade as service

    students = [_student(1, 10), _student(2, 20), _student(3, "20")]
    result = service._filter_students_by_scope(_Ctx({20}), object(), students)

    assert [item.id for item in result] == [2, 3]


def test_empty_scope_returns_empty_instead_of_all_students():
    from app.modules.academic_affairs.services import academic_affairs_makeup_facade as service

    students = [_student(1, 10), _student(2, 20)]
    result = service._filter_students_by_scope(_Ctx(set()), object(), students)

    assert result == []


def test_invalid_class_id_is_not_accidentally_allowed():
    from app.modules.academic_affairs.services import academic_affairs_makeup_facade as service

    students = [_student(1, "unknown")]
    result = service._filter_students_by_scope(_Ctx({10}), object(), students)

    assert result == []
