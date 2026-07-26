"""补考/重修/免修本人解析优先稳定studentId与账号绑定。"""
from types import SimpleNamespace

import pytest


class _ScalarResult:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class _Db:
    def __init__(self, row):
        self.row = row
        self.queries = []

    def scalars(self, query):
        self.queries.append(str(query))
        return _ScalarResult(self.row)


def _student(student_id=11, student_no="20260001"):
    return SimpleNamespace(
        id=student_id,
        tenant_id=1,
        student_no=student_no,
        is_deleted=False,
    )


def test_stable_student_id_is_used_before_student_number(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_makeup_facade as service

    row = _student(11, "NEW-NO")
    db = _Db(row)
    monkeypatch.setattr(service, "get_current_user_ctx", lambda: {
        "studentId": "11",
        "studentNo": "OLD-NO",
        "loginName": "OLD-NO",
        "userId": "db-99",
    })
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(
        service,
        "get_student_id_by_user",
        lambda *_args, **_kwargs: pytest.fail("已有studentId时不应再查账号绑定"),
    )

    resolved = service._student(db)

    assert resolved.id == 11
    assert resolved.student_no == "NEW-NO"


def test_account_link_resolves_student_when_token_lacks_student_id(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_makeup_facade as service

    row = _student(22, "20260022")
    db = _Db(row)
    calls = []
    monkeypatch.setattr(service, "get_current_user_ctx", lambda: {
        "studentId": None,
        "studentNo": "OLD-NO",
        "loginName": "OLD-NO",
        "userId": "db-88",
    })
    monkeypatch.setattr(service, "_tid", lambda: 1)

    def resolve(_db, **kwargs):
        calls.append(kwargs)
        return 22

    monkeypatch.setattr(service, "get_student_id_by_user", resolve)

    resolved = service._student(db)

    assert resolved.id == 22
    assert calls[0]["user_id"] == 88
    assert calls[0]["allow_legacy_fallback"] is True


def test_missing_binding_and_profile_is_rejected(monkeypatch):
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_makeup_facade as service

    db = _Db(None)
    monkeypatch.setattr(service, "get_current_user_ctx", lambda: {
        "studentId": None,
        "studentNo": "UNKNOWN",
        "loginName": "UNKNOWN",
        "userId": "db-77",
    })
    monkeypatch.setattr(service, "_tid", lambda: 1)
    monkeypatch.setattr(service, "get_student_id_by_user", lambda *_args, **_kwargs: None)

    with pytest.raises(AppException) as exc:
        service._student(db)

    assert "账号尚未绑定" in exc.value.message


def test_original_makeup_state_machine_uses_stable_resolver():
    from app.modules.academic_affairs.services import academic_affairs_makeup_facade as service

    assert service._legacy._student is service._student
