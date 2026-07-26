"""补考/清考/重修/免修termCode写保护和归档域回归。"""
from types import SimpleNamespace


class _Query:
    def __init__(self, rows):
        self._rows = list(rows or [])

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._rows)


class _Db:
    def __init__(self, rows):
        self.rows = rows

    def query(self, _model):
        return _Query(self.rows)


def _term(term_id, year="2025-2026", no=2):
    return SimpleNamespace(
        id=term_id,
        tenant_id=1,
        is_deleted=False,
        year_code=year,
        term_no=no,
    )


def test_term_code_resolver_requires_exact_formal_term(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_archive_term_guard_facade as service

    monkeypatch.setattr(service, "_tid", lambda: 1)
    db = _Db([_term(9)])

    assert service.resolve_term_by_code(db, "2025-2026-2").id == 9


def test_unknown_term_code_is_not_silently_treated_as_writable(monkeypatch):
    import pytest
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_archive_term_guard_facade as service

    monkeypatch.setattr(service, "_tid", lambda: 1)
    with pytest.raises(AppException) as exc:
        service.resolve_term_by_code(_Db([_term(9)]), "2024-2025-2")

    assert exc.value.http_status == 409
    assert "未匹配到本校正式学期" in exc.value.message


def test_batch_write_context_guards_batch_term_code(monkeypatch):
    from app.modules.academic_affairs import services
    from app.modules.academic_affairs.services import academic_affairs_makeup_term_facade as service

    batch = SimpleNamespace(id=7, term_code="2025-2026-2")
    calls = []
    monkeypatch.setattr(service, "_original_get_mb", lambda _db, _bid: batch)
    monkeypatch.setattr(
        services.academic_affairs_archive_service,
        "guard_term_code_writable",
        lambda db, code, required=True: calls.append((db, code, required)),
    )
    db = object()
    token = service._BATCH_WRITE.set(True)
    try:
        assert service._get_mb(db, 7) is batch
    finally:
        service._BATCH_WRITE.reset(token)

    assert calls == [(db, "2025-2026-2", True)]


def test_makeup_archive_gate_blocks_unfinished_business():
    from app.modules.academic_affairs.services.academic_affairs_archive_makeup_facade import (
        _makeup_gate_result,
    )

    result = _makeup_gate_result(
        [SimpleNamespace(status="SCORING"), SimpleNamespace(status="FINISHED")],
        active_retakes=2,
        active_exemptions=3,
    )

    assert result["present"] is False
    assert "未结束补考/清考批次 1 个" in result["remark"]
    assert "在途重修申请 2 条" in result["remark"]
    assert "在途免修申请 3 条" in result["remark"]


def test_makeup_archive_gate_accepts_finished_or_no_business():
    from app.modules.academic_affairs.services.academic_affairs_archive_makeup_facade import (
        _makeup_gate_result,
    )

    assert _makeup_gate_result([])["present"] is True
    assert _makeup_gate_result([SimpleNamespace(status="FINISHED")])["present"] is True


def test_public_makeup_and_archive_services_point_to_final_layers():
    from app.modules.academic_affairs import services

    assert services.academic_affairs_archive_service.__name__.endswith(
        "academic_affairs_archive_makeup_facade"
    )
    assert any(code == "MAKEUP" for code, _label in services.academic_affairs_archive_service._legacy._DOMAINS)
    assert services.academic_affairs_makeup_service.__name__.endswith(
        "academic_affairs_makeup_term_facade"
    )
    assert services.academic_affairs_makeup_service.create_makeup_batch.__module__.endswith(
        "academic_affairs_makeup_term_facade"
    )
    assert services.academic_affairs_makeup_service.retake_apply.__module__.endswith(
        "academic_affairs_makeup_term_facade"
    )
