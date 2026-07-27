"""补考、重修、免修本人解析只使用统一学生账号绑定服务。"""
from types import SimpleNamespace

import pytest


def _student(student_id=11, student_no="20260001"):
    return SimpleNamespace(
        id=student_id,
        tenant_id=1,
        student_no=student_no,
        real_name="测试学生",
        is_deleted=False,
    )


def test_makeup_student_resolver_delegates_to_unified_identity(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as service
    from app.services import mobile_student_identity_facade as identity

    row = _student(11, "NEW-NO")
    calls = []

    def resolve(db, user):
        calls.append((db, user))
        return row

    monkeypatch.setattr(identity, "resolve_student", resolve)
    user = {"studentId": "11", "userId": "db-99", "studentNo": "OLD-NO"}
    db = object()

    resolved = service._student(db, user)

    assert resolved is row
    assert calls == [(db, user)]


def test_missing_binding_is_rejected_as_business_404(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as service
    from app.services import mobile_student_identity_facade as identity

    monkeypatch.setattr(identity, "resolve_student", lambda _db, _user: None)

    with pytest.raises(AppException) as exc:
        service._student(object(), {"userId": "db-77"})

    assert "尚未绑定唯一学生档案" in exc.value.message
    assert exc.value.http_status == 404


def test_retake_and_exemption_student_lists_use_profile_id_not_student_number():
    source = __import__("pathlib").Path(__file__).resolve().parents[1] / (
        "app/modules/academic_affairs/services/academic_affairs_makeup_service.py"
    )
    text = source.read_text(encoding="utf-8")

    assert "AaRetakeApply.student_id == int(student.id)" in text
    assert "AaExemption.student_id == int(student.id)" in text
    assert "AaRetakeApply.student_no ==" not in text
    assert "AaExemption.student_no ==" not in text


def test_legacy_identity_facade_only_reexports_canonical_resolver():
    from app.modules.academic_affairs.services import academic_affairs_makeup_identity_facade as compatibility
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as canonical

    assert compatibility._legacy is canonical
    assert compatibility._required_student is canonical._student
