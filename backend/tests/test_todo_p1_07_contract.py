from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.services.todo_route_registry import resolve_todo_route, route_contract_snapshot
from app.services.workbench_todo_service import _todo_dict


ROOT = Path(__file__).resolve().parents[2]


def test_pc_exact_todo_routes_exist_in_generated_route_index():
    index = json.loads((ROOT / "shared/generated/route-index.json").read_text(encoding="utf-8"))
    patterns = set(index.get("patterns") or [])
    exact = route_contract_snapshot()["pcExact"]
    assert exact
    for spec in exact.values():
        pattern = spec["pathTemplate"].replace("{recordId}", ":recordId")
        # generated index uses domain-specific parameter names; compare normalized static shape.
        normalized = pattern.rsplit("/:", 1)[0]
        assert any(p.startswith(normalized + "/:") for p in patterns), spec


def test_typed_todo_dto_contains_record_route_actions_and_version():
    row = SimpleNamespace(
        id=101,
        todo_type="RISK_HANDLE",
        title="处置风险",
        source_biz_type="RISK",
        source_biz_id=88,
        source_module="student-affairs",
        due_at=None,
        created_at=datetime(2026, 8, 8, 8, 0, 0),
        status="PENDING",
        version=7,
    )
    dto = _todo_dict(row, client="pc")
    assert dto["recordId"] == "88"
    assert dto["routeName"] == "studentAffairs.risk.detail"
    assert dto["routePath"] == "/admin/student-affairs/risk/88"
    assert dto["routeParams"] == {"recordId": "88"}
    assert dto["query"] == {}
    assert dto["routeExact"] is True
    assert dto["allowedActions"] == ["OPEN", "COMPLETE"]
    assert dto["version"] == 7


def test_unimplemented_detail_route_is_explicitly_non_exact_but_keeps_record_id():
    route = resolve_todo_route("LEAVE_APPROVAL", 55, client="pc")
    assert route == {
        "routeName": "studentAffairs.leave.queue",
        "routeParams": {"recordId": "55"},
        "query": {"status": "PENDING", "recordId": "55"},
        "path": "/admin/student-affairs/leave",
        "exact": False,
    }


def test_unknown_todo_type_does_not_invent_a_route():
    assert resolve_todo_route("UNKNOWN_NEW_TODO", 1, client="pc") is None
    assert resolve_todo_route("UNKNOWN_NEW_TODO", 1, client="studentMini") is None
