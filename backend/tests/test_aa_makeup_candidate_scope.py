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
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as service

    students = [_student(1, 10), _student(2, 20)]
    result = service._scope_students(_Ctx(None), object(), students)
    assert [item.id for item in result] == [1, 2]


def test_college_scope_keeps_only_allowed_classes():
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as service

    students = [_student(1, 10), _student(2, 20), _student(3, "20")]
    result = service._scope_students(_Ctx({20}), object(), students)
    assert [item.id for item in result] == [2, 3]


def test_empty_scope_returns_empty_instead_of_all_students():
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as service

    students = [_student(1, 10), _student(2, 20)]
    assert service._scope_students(_Ctx(set()), object(), students) == []


def test_invalid_class_id_is_not_accidentally_allowed():
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as service

    students = [_student(1, "unknown")]
    assert service._scope_students(_Ctx({10}), object(), students) == []


def test_legacy_guard_does_not_keep_a_second_scope_implementation():
    from app.modules.academic_affairs.services import academic_affairs_makeup_course_identity_guard as compatibility
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as canonical

    assert compatibility._legacy is canonical
    assert compatibility.makeup_pending is canonical.makeup_pending
    assert compatibility.clearance_scan is canonical.clearance_scan
