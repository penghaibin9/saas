"""选课轮次归档写保护与正式公开入口回归。"""
from types import SimpleNamespace


def test_writable_batch_calls_term_archive_guard(monkeypatch):
    from app.modules.academic_affairs import services
    from app.modules.academic_affairs.services import academic_affairs_selection_round_facade as service

    batch = SimpleNamespace(id=7, term_id=9)
    calls = []
    monkeypatch.setattr(service._legacy, "_get_batch", lambda _db, batch_id: batch)
    monkeypatch.setattr(
        services.academic_affairs_archive_service,
        "guard_term_writable",
        lambda db, term_id: calls.append((db, term_id)),
    )
    db = object()

    result = service._writable_batch(db, 7)

    assert result is batch
    assert calls == [(db, 9)]


def test_public_round_service_keeps_real_function_names_and_facade():
    from app.modules.academic_affairs import services

    service = services.academic_affairs_selection_round_service
    assert service.__name__.endswith("academic_affairs_selection_round_facade")
    assert service.create_round.__module__.endswith("academic_affairs_selection_round_facade")
    assert service.open_round.__module__.endswith("academic_affairs_selection_round_facade")
    assert service.close_round.__module__.endswith("academic_affairs_selection_round_facade")
    assert service.draw_round.__module__.endswith("academic_affairs_selection_round_facade")
    assert not hasattr(service, "draw_lottery")


def test_round_facade_preserves_constants_without_mutating_legacy_functions():
    from app.modules.academic_affairs.services import academic_affairs_selection_round_facade as service

    assert service._legacy._REC_PENDING
    assert service._legacy._REC_SELECTED
    assert service._legacy._REC_LOST
    assert service._legacy.draw_round is not service.draw_round
