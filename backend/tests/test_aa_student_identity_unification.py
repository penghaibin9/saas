"""P0-05：教务四端统一学生身份解析。"""
from types import SimpleNamespace


class _Result:
    def __init__(self, rows):
        self.rows = list(rows)

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)


class _Db:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = 0

    def scalars(self, _stmt):
        self.calls += 1
        return _Result(self.rows)


def _student(student_id=11, no="20260011", name="测试学生"):
    return SimpleNamespace(
        id=student_id,
        student_no=no,
        real_name=name,
        tenant_id=1,
        is_deleted=False,
    )


def test_stable_student_id_has_highest_priority(monkeypatch):
    from app.services import mobile_student_identity_facade as service
    from app.services import mobile_student_service as impl
    from app.services import student_account_link_service as link_service

    row = _student()
    db = _Db([row])
    monkeypatch.setattr(impl, "_tid", lambda: 1)
    monkeypatch.setattr(
        link_service,
        "get_student_id_by_user",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("不应查询账号绑定")),
    )

    assert service.resolve_student(db, {"studentId": "11", "userId": "db-99"}) is row


def test_real_account_uses_link_service_with_monitored_legacy_fallback(monkeypatch):
    from app.services import mobile_student_identity_facade as service
    from app.services import mobile_student_service as impl
    from app.services import student_account_link_service as link_service

    row = _student(22)
    db = _Db([row])
    seen = {}
    monkeypatch.setattr(impl, "_tid", lambda: 1)

    def resolve(_db, **kwargs):
        seen.update(kwargs)
        return 22

    monkeypatch.setattr(link_service, "get_student_id_by_user", resolve)

    assert service.resolve_student(db, {
        "userId": "db-88",
        "loginName": "20260022",
        "studentNo": "OLD-NO",
        "realName": "同名学生",
    }) is row
    assert seen == {
        "tenant_id": 1,
        "user_id": 88,
        "allow_legacy_fallback": True,
        "login_name": "20260022",
    }


def test_u_prefix_is_also_treated_as_real_database_account(monkeypatch):
    from app.services import mobile_student_identity_facade as service
    from app.services import mobile_student_service as impl
    from app.services import student_account_link_service as link_service

    row = _student(44)
    db = _Db([row])
    seen = {}
    monkeypatch.setattr(impl, "_tid", lambda: 1)

    def resolve(_db, **kwargs):
        seen.update(kwargs)
        return 44

    monkeypatch.setattr(link_service, "get_student_id_by_user", resolve)

    assert service.resolve_student(db, {
        "userId": "u_144",
        "loginName": "20260044",
        "realName": "不能按姓名猜",
    }) is row
    assert seen["user_id"] == 144


def test_real_account_without_binding_fails_closed_before_name_guess(monkeypatch):
    from app.services import mobile_student_identity_facade as service
    from app.services import mobile_student_service as impl
    from app.services import student_account_link_service as link_service

    db = _Db([_student(name="唯一姓名")])
    monkeypatch.setattr(impl, "_tid", lambda: 1)
    monkeypatch.setattr(link_service, "get_student_id_by_user", lambda *_args, **_kwargs: None)

    resolved = service.resolve_student(db, {
        "userId": "db-77",
        "loginName": "UNKNOWN",
        "realName": "唯一姓名",
    })

    assert resolved is None
    assert db.calls == 0


def test_legacy_token_without_database_user_id_can_use_unique_student_number(monkeypatch, caplog):
    from app.services import mobile_student_identity_facade as service
    from app.services import mobile_student_service as impl
    from app.services import student_account_link_service as link_service

    row = _student(33, no="20260033")
    db = _Db([row])
    monkeypatch.setattr(impl, "_tid", lambda: 1)

    resolved = service.resolve_student(db, {"studentNo": "20260033"})

    assert resolved is row
    assert "student_identity_legacy_student_no" in caplog.text


def test_academic_service_package_installs_unified_resolver():
    """教务各域必须共用同一个身份解析实现，不得各自维护第二套。

    验的是能力而不是包结构：facade 只是薄再导出层，各服务在调用点直接
    `from app.services.mobile_student_identity_facade import resolve_student`，
    因此断言"解析函数是同一个对象"，而不是"包上挂了某个属性名"。
    """
    from app.services import mobile_student_identity_facade as identity
    from app.services import mobile_student_service as impl

    assert identity.resolve_student is impl.resolve_student

    # 教务侧真实调用点必须解析到同一个函数，不允许某个域偷偷换实现。
    from app.modules.academic_affairs.services import (
        academic_affairs_evaluation_public_service as evaluation,
        academic_affairs_grade_recheck_service as recheck,
        academic_affairs_makeup_service as makeup,
    )
    import inspect
    for module in (evaluation, recheck, makeup):
        source = inspect.getsource(module)
        assert "from app.services.mobile_student_identity_facade import resolve_student" in source, (
            f"{module.__name__} 未使用统一身份解析入口")
