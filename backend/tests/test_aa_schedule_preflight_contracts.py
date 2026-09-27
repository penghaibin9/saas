"""R1-06 manual scheduling preflight public-contract checks."""
from __future__ import annotations

from fastapi.routing import APIRoute
import pytest

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


@pytest.mark.parametrize("pre_publish", [False, True], ids=["draft", "pre-published"])
@pytest.mark.parametrize("resource", ["classroom", "teacher"])
@pytest.mark.parametrize("weekday", [1, 6], ids=["weekday", "weekend"])
@pytest.mark.parametrize("action", ["add", "move"])
def test_college_preflight_sees_other_college_candidate_without_edit_access(client, db_mode, pre_publish, resource, weekday, action):
    from tests.test_aa_v5_school_schedule_gate import BASE, _facts, _candidate, _snapshot
    from tests.test_aa_schedule import _item
    from app.db.session import get_sessionmaker
    from app.models import AaScheduleItem

    facts = _facts(client, shared_teacher=resource == "teacher")
    own = _candidate(client, facts, 0, weekday=3, add_item=action == "move", pre_publish=False)
    other = _candidate(client, facts, 1, weekday=weekday, room="发布测试教室0", pre_publish=pre_publish)
    with get_sessionmaker()() as db:
        item = db.query(AaScheduleItem).filter(AaScheduleItem.batch_id == int(other)).one()
        item.classroom_text = "旧教室名称"
        own_item = db.query(AaScheduleItem).filter(AaScheduleItem.batch_id == int(own)).first()
        endpoint = (f"{BASE}/schedule-items/{own_item.id}/move-preflight" if own_item
                    else f"{BASE}/schedule-batches/{own}/items/preflight")
        db.commit()
    body = {"taskId": facts["tasks"][0]["taskId"], "weekday": weekday, "slotNo": 1,
            "startWeek": 1, "endWeek": 18, "weekParity": "ALL", "classroom": "发布测试教室0"}
    if action == "move":
        body = {"weekday": weekday, "slotNo": 1}
    before = _snapshot(facts)
    results = []
    for headers in (facts["college"], facts["school"]):
        response = client.post(endpoint, headers=headers, json=body)
        assert response.status_code == 200, response.text
        results.append(response.json()["data"])
    assert results[0]["allowed"] is False
    assert results[0]["conflict"]["type"] == resource.upper()
    assert facts["tasks"][1]["courseName"] not in str(results[0]["conflict"])
    assert facts["tasks"][1]["teacherName"] not in str(results[0]["conflict"])
    assert results[0]["conflict"] == results[1]["conflict"]
    assert results[0]["candidate"] == results[1]["candidate"]
    assert results[0]["alternatives"]
    assert all(row["weekday"] != weekday for row in results[0]["alternatives"])
    assert _snapshot(facts) == before
    assert client.get(f"{BASE}/schedule-batches/{other}", headers=facts["college"]).status_code == 403

    # 同范围新候选取代旧候选；旧草稿/预发布的资源不应永久占用。
    response = client.post(f"{BASE}/schedule-batches", headers=facts["school"], json={
        "termId": str(facts["termId"]), "collegeId": facts["tasks"][1]["collegeId"], "batchName": "替换候选",
    })
    assert response.status_code == 200, response.text
    replacement_id = response.json()["data"]["batchId"]
    response = _item(client, facts["school"], replacement_id,
        **{key: value for key, value in facts["tasks"][1].items() if key != "collegeId"},
        weekday=2, classroom="发布测试教室0")
    assert response.status_code == 200, response.text
    response = client.post(endpoint, headers=facts["college"], json=body)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["allowed"] is True
