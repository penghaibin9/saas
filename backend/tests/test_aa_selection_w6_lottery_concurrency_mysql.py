"""B-W6-3 real-MySQL contracts for Lottery close/draw concurrency.

Only gaps not already covered by the sequential round suite live here:
- two administrators drawing the same CLOSED Lottery concurrently may produce one result only;
- a CLOSED Lottery awaiting draw must never fall back to legacy FCFS enrollment.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from queue import Queue
from threading import Barrier, Thread

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services import (
    academic_affairs_selection_round_service as round_service,
)


_suite_path = Path(__file__).with_name("test_aa_selection.py")
_spec = importlib.util.spec_from_file_location("_w6_lottery_selection_suite", _suite_path)
_suite = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_suite)

BASE = _suite.BASE
TID = _suite.TID


def _admin_user() -> dict:
    return {
        "userId": "w6-lottery-admin",
        "loginName": "w6-lottery-admin",
        "realName": "W6抽签管理员",
        "userType": "ADMIN",
        "currentRoleCode": "ACADEMIC_ADMIN",
    }


def _activate_admin() -> dict:
    user = _admin_user()
    set_tenant({"tenantId": str(TID), "tenantCode": "academic-b-w6-lottery"})
    set_current_user(user)
    return user


def _clear_context() -> None:
    set_current_user(None)
    set_tenant(None)


def _create_open_lottery(client, admin, batch_id: int, *, name: str) -> int:
    created = client.post(
        f"{BASE}/selection/batches/{batch_id}/rounds",
        headers=admin,
        json={"roundName": name, "mode": "LOTTERY", "allowEnroll": True, "allowDrop": True},
    )
    assert created.status_code == 200, created.text
    round_id = int(created.json()["data"]["roundId"])
    opened = client.post(f"{BASE}/selection/rounds/{round_id}/open", headers=admin)
    assert opened.status_code == 200, opened.text
    return round_id


def _enroll(client, student_no: str, real_name: str, selection_course_id: int):
    return client.post(
        f"{BASE}/selection/student/enroll",
        headers=_suite._stu_token(real_name, student_no),
        json={"selectionCourseId": str(selection_course_id)},
    )


def _run_draw(barrier: Barrier, round_id: int, outcomes: Queue) -> None:
    user = _activate_admin()
    try:
        barrier.wait(timeout=10)
        outcomes.put(("ok", round_service.draw_round(user, int(round_id))))
    except BaseException as exc:
        outcomes.put(("error", exc))
    finally:
        _clear_context()


def _lottery_state(round_id: int, selection_course_id: int) -> dict:
    from app.models import AaSelectionCourse, AaSelectionRecord, AaSelectionRound

    db = get_sessionmaker()()
    try:
        round_row = db.query(AaSelectionRound).filter(
            AaSelectionRound.id == int(round_id),
            AaSelectionRound.tenant_id == TID,
            AaSelectionRound.is_deleted.is_(False),
        ).one()
        course = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == int(selection_course_id),
            AaSelectionCourse.tenant_id == TID,
            AaSelectionCourse.is_deleted.is_(False),
        ).one()
        records = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == TID,
            AaSelectionRecord.selection_course_id == int(selection_course_id),
            AaSelectionRecord.is_deleted.is_(False),
        ).all()
        return {
            "roundStatus": str(round_row.status),
            "selectedCount": int(course.selected_count or 0),
            "statuses": sorted(str(row.status) for row in records),
        }
    finally:
        db.close()


def test_w6_concurrent_double_lottery_draw_is_single_claim(client, db_mode):
    ids = _suite._seed(db_mode)
    admin = _suite._hdr(client, "school_admin01")
    task_id, _ = _suite._ready_tasks(ids)
    batch_id, selection_course_id = _suite._make_open_batch(
        client,
        admin,
        ids["course1"],
        capacity=1,
        teaching_task_id=task_id,
        name="W6 双并发摇号",
    )
    round_id = _create_open_lottery(client, admin, int(batch_id), name="W6 双并发抽签轮")

    first = _enroll(client, "SEL2401", "选甲", int(selection_course_id))
    second = _enroll(client, "SEL2402", "选乙", int(selection_course_id))
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["data"]["status"] == "PENDING_LOTTERY"
    assert second.json()["data"]["status"] == "PENDING_LOTTERY"

    closed = client.post(f"{BASE}/selection/rounds/{round_id}/close", headers=admin)
    assert closed.status_code == 200, closed.text

    outcomes: Queue = Queue()
    barrier = Barrier(2)
    threads = [
        Thread(target=_run_draw, args=(barrier, round_id, outcomes), name=f"w6-draw-{index}")
        for index in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
        assert not thread.is_alive(), f"{thread.name} did not terminate"

    assert outcomes.qsize() == 2
    rows = [outcomes.get_nowait() for _ in range(2)]
    successes = [payload for state, payload in rows if state == "ok"]
    failures = [payload for state, payload in rows if state == "error"]
    assert len(successes) == 1, rows
    assert len(failures) == 1, rows
    assert isinstance(failures[0], AppException), repr(failures[0])
    assert int(getattr(failures[0], "http_status", 0) or 0) == 409
    assert "已摇号不可重摇" in str(getattr(failures[0], "message", "") or failures[0])
    assert successes[0]["totalWinners"] == 1
    assert successes[0]["totalLosers"] == 1

    state = _lottery_state(round_id, int(selection_course_id))
    assert state == {
        "roundStatus": "DRAWN",
        "selectedCount": 1,
        "statuses": ["LOTTERY_LOST", "SELECTED"],
    }, state


def test_w6_closed_lottery_waiting_draw_never_falls_back_to_fcfs(client, db_mode):
    ids = _suite._seed(db_mode)
    admin = _suite._hdr(client, "school_admin01")
    task_id, _ = _suite._ready_tasks(ids)
    batch_id, selection_course_id = _suite._make_open_batch(
        client,
        admin,
        ids["course1"],
        capacity=2,
        teaching_task_id=task_id,
        name="W6 关闭待摇号保护",
    )
    round_id = _create_open_lottery(client, admin, int(batch_id), name="W6 关闭待摇号抽签轮")

    pending = _enroll(client, "SEL2401", "选甲", int(selection_course_id))
    assert pending.status_code == 200, pending.text
    assert pending.json()["data"]["status"] == "PENDING_LOTTERY"

    closed = client.post(f"{BASE}/selection/rounds/{round_id}/close", headers=admin)
    assert closed.status_code == 200, closed.text
    before = _lottery_state(round_id, int(selection_course_id))
    assert before == {
        "roundStatus": "CLOSED",
        "selectedCount": 0,
        "statuses": ["PENDING_LOTTERY"],
    }, before

    late = _enroll(client, "SEL2402", "选乙", int(selection_course_id))
    assert late.status_code == 409, late.text

    after = _lottery_state(round_id, int(selection_course_id))
    assert after == before, {"before": before, "after": after, "response": late.text}
