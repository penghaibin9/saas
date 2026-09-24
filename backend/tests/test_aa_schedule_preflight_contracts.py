"""R1-06 manual scheduling preflight public-contract checks."""
from __future__ import annotations

from fastapi.routing import APIRoute

from app.modules.academic_affairs.routers import schedule_core_router
from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as service


def _route(path: str, method: str) -> APIRoute:
    for row in schedule_core_router.router.routes:
        if isinstance(row, APIRoute) and row.path == path and method in (row.methods or set()):
            return row
    raise AssertionError(f"missing {method} {path}")


def test_add_and_move_preflight_are_explicit_pure_read_routes():
    add = _route("/academic-affairs/schedule-batches/{batchId}/items/preflight", "POST")
    move = _route("/academic-affairs/schedule-items/{itemId}/move-preflight", "POST")
    assert add.endpoint.__module__.endswith("schedule_core_router")
    assert move.endpoint.__module__.endswith("schedule_core_router")
    assert "纯读" in (add.summary or "")
    assert "纯读" in (move.summary or "")


def test_preflight_service_exposes_canonical_conflict_and_alternative_contract():
    assert callable(service.preflight_item)
    assert callable(service.preflight_move)
    names = set(service._preflight_result.__code__.co_names)
    assert "_detect_conflict" not in names  # uses the preloaded wrapper of the one canonical detector
    constants = " ".join(str(value) for value in service._preflight_result.__code__.co_consts)
    assert "CANONICAL_SCHEDULE_CONFLICT_V1" in constants
    assert "alternatives" in constants
    assert "HARD" in constants
