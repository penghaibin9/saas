"""评教学期写保护与归档闭环回归。"""
from types import SimpleNamespace


def test_evaluation_archive_gate_blocks_open_window_missing_results_and_appeals():
    from app.modules.academic_affairs.services.academic_affairs_archive_evaluation_facade import (
        _evaluation_gate_result,
    )

    result = _evaluation_gate_result(
        [SimpleNamespace(status="OPEN"), SimpleNamespace(status="CLOSED")],
        missing_results=2,
        active_appeals=3,
    )

    assert result["present"] is False
    assert "未关闭评教批次 1 个" in result["remark"]
    assert "未生成结果的评教任务 2 个" in result["remark"]
    assert "在途评教申诉 3 条" in result["remark"]


def test_evaluation_archive_gate_accepts_closed_or_unused_domain():
    from app.modules.academic_affairs.services.academic_affairs_archive_evaluation_facade import (
        _evaluation_gate_result,
    )

    assert _evaluation_gate_result([])["present"] is True
    assert _evaluation_gate_result([SimpleNamespace(status="CLOSED")])["present"] is True


def test_evaluation_write_helpers_call_term_guard(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_evaluation_term_facade as service

    calls = []
    monkeypatch.setattr(service, "_guard_term", lambda db, term_id: calls.append((db, term_id)))
    batch = SimpleNamespace(id=7, term_id=9)
    monkeypatch.setattr(service, "_original_get_batch", lambda _db, _id: batch)
    db = object()
    token = service._BATCH_WRITE.set(True)
    try:
        assert service._get_batch(db, 7) is batch
    finally:
        service._BATCH_WRITE.reset(token)

    assert calls == [(db, 9)]


def test_public_evaluation_and_archive_services_point_to_final_layers():
    from app.modules.academic_affairs import services

    assert services.academic_affairs_archive_service.__name__.endswith(
        "academic_affairs_archive_evaluation_facade"
    )
    assert any(code == "EVALUATION" for code, _label in services.academic_affairs_archive_service._legacy._DOMAINS)
    assert services.academic_affairs_evaluation_service.__name__.endswith(
        "academic_affairs_evaluation_term_facade"
    )
    assert services.academic_affairs_evaluation_service.submit.__module__.endswith(
        "academic_affairs_evaluation_term_facade"
    )
    assert services.academic_affairs_evaluation_service.review_appeal.__module__.endswith(
        "academic_affairs_evaluation_term_facade"
    )
