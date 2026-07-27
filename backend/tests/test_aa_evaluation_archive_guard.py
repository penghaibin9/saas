"""评教学期写保护与归档闭环回归。"""
from pathlib import Path
from types import SimpleNamespace


def test_evaluation_archive_gate_blocks_non_final_batches_missing_results_and_appeals():
    from app.modules.academic_affairs.services.academic_affairs_archive_evaluation_facade import (
        _evaluation_gate_result,
    )

    result = _evaluation_gate_result(
        [SimpleNamespace(status="OPEN"), SimpleNamespace(status="CLOSED")],
        missing_results=2,
        active_appeals=3,
    )

    assert result["present"] is False
    assert "未形成最终结果的评教批次 2 个" in result["remark"]
    assert "未生成结果的评教任务 2 个" in result["remark"]
    assert "在途评教申诉 3 条" in result["remark"]


def test_evaluation_archive_gate_accepts_result_ready_archived_or_unused_domain():
    from app.modules.academic_affairs.services.academic_affairs_archive_evaluation_facade import (
        _evaluation_gate_result,
    )

    assert _evaluation_gate_result([])["present"] is True
    assert _evaluation_gate_result([
        SimpleNamespace(status="RESULT_READY"),
        SimpleNamespace(status="ARCHIVED"),
    ])["present"] is True


def test_evaluation_write_helpers_call_term_guard(monkeypatch):
    from app.modules.academic_affairs.services import academic_affairs_evaluation_term_facade as service

    calls = []
    batch = SimpleNamespace(id=7, term_id=9)
    monkeypatch.setattr(service._legacy, "_get_batch", lambda _db, _id: batch)
    monkeypatch.setattr(service, "_guard_term", lambda db, term_id: calls.append((db, term_id)))
    db = object()

    assert service._writable_batch(db, 7) is batch
    assert calls == [(db, 9)]


def test_public_evaluation_and_archive_services_point_to_final_layers():
    from app.modules.academic_affairs import services

    assert services.academic_affairs_archive_service.__name__.endswith(
        "academic_affairs_archive_service"
    )
    assert any(
        code == "EVALUATION"
        for code, _label in services.academic_affairs_archive_service._DOMAINS
    )
    assert services.academic_affairs_evaluation_service.__name__.endswith(
        "academic_affairs_evaluation_term_facade"
    )
    assert services.academic_affairs_evaluation_service.submit_evaluation.__module__.endswith(
        "academic_affairs_evaluation_term_facade"
    )
    assert services.academic_affairs_evaluation_service.review_appeal.__module__.endswith(
        "academic_affairs_evaluation_term_facade"
    )


def test_evaluation_public_service_has_no_legacy_function_replacement():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "app/modules/academic_affairs/services/academic_affairs_evaluation_term_facade.py"
    ).read_text(encoding="utf-8")

    for token in (
        "_legacy._get_batch =",
        "setattr(_legacy",
        "_legacy.create_batch =",
        "_legacy.submit_appeal =",
        "_legacy.review_appeal =",
    ):
        assert token not in source
    assert "def _writable_batch" in source
    assert "_guard_term(db, batch.term_id)" in source
