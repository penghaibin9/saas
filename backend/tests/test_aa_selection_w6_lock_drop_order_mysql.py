"""B-W6-2: LOCK/drop must not deadlock under real MySQL row locks.

The fixture reuses the canonical Selection suite.  The race coordinator only waits
after real ``SELECT ... FOR UPDATE`` statements have acquired their rows; it does
not monkeypatch business functions or fake database locks.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from queue import Queue
from threading import Event, Thread, current_thread
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_engine, get_sessionmaker
from app.modules.academic_affairs.services import (
    academic_affairs_selection_final_service as selection_final,
)


_suite_path = Path(__file__).with_name("test_aa_selection.py")
_spec = importlib.util.spec_from_file_location("_w6_lock_drop_selection_suite", _suite_path)
_suite = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_suite)


def _activate(user: dict) -> None:
    set_tenant({"tenantId": str(_suite.TID), "tenantCode": "academic-b-w6-lock-drop"})
    set_current_user(user)


def _clear_context() -> None:
    set_current_user(None)
    set_tenant(None)


def _admin_user() -> dict:
    return {
        "userId": "w6-academic-admin",
        "loginName": "w6-academic-admin",
        "realName": "W6教务管理员",
        "userType": "ADMIN",
        "currentRoleCode": "ACADEMIC_ADMIN",
    }


def _student_user(student_id: int) -> dict:
    return {
        "studentId": str(student_id),
        "studentNo": "SEL2401",
        "loginName": "SEL2401",
        "realName": "选甲",
        "userType": "STUDENT",
        "currentRoleCode": "STUDENT",
    }


def _captures_mysql_deadlock(exc: BaseException | None) -> bool:
    seen: set[int] = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        text = f"{type(current).__name__}: {current}"
        lowered = text.lower()
        if "1213" in text or "deadlock found when trying to get lock" in lowered:
            return True
        current = getattr(current, "orig", None) or getattr(current, "__cause__", None)
    return False


def _run(outcomes: Queue, key: str, user: dict, command) -> None:
    _activate(user)
    try:
        outcomes.put((key, "ok", command()))
    except BaseException as exc:  # capture the real DB/business failure for the assertion thread
        outcomes.put((key, "error", exc))
    finally:
        _clear_context()


def _final_state(batch_id: int, selection_course_id: int, student_id: int) -> dict:
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord

    db = get_sessionmaker()()
    try:
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.id == int(batch_id),
            AaSelectionBatch.tenant_id == _suite.TID,
            AaSelectionBatch.is_deleted.is_(False),
        ).one()
        course = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.id == int(selection_course_id),
            AaSelectionCourse.tenant_id == _suite.TID,
            AaSelectionCourse.is_deleted.is_(False),
        ).one()
        record = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == _suite.TID,
            AaSelectionRecord.student_id == int(student_id),
            AaSelectionRecord.selection_course_id == int(selection_course_id),
            AaSelectionRecord.is_deleted.is_(False),
        ).one()
        return {
            "batchStatus": str(batch.status),
            "recordStatus": str(record.status),
            "selectedCount": int(course.selected_count or 0),
        }
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_w6_lock_and_student_drop_share_one_lock_order(client, db_mode):
    ids = _suite._seed(db_mode)
    admin_headers = _suite._hdr(client, "school_admin01")
    task_id, _ = _suite._ready_tasks(ids)
    batch_id, selection_course_id = _suite._make_open_batch(
        client,
        admin_headers,
        ids["course1"],
        capacity=5,
        teaching_task_id=task_id,
        name="W6 LOCK/drop 锁序竞态",
    )
    student_headers = _suite._stu_token("选甲", "SEL2401")
    enrolled = client.post(
        f"{_suite.BASE}/selection/student/enroll",
        headers=student_headers,
        json={"selectionCourseId": str(selection_course_id)},
    )
    assert enrolled.status_code == 200, enrolled.text
    record_id = enrolled.json()["data"]["recordId"]

    closed = client.post(
        f"{_suite.BASE}/selection/batches/{batch_id}/close",
        headers=admin_headers,
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["status"] == "CLOSED"

    batch_locked = Event()
    drop_lock_observed = Event()
    first_drop_lock: Queue = Queue()
    coordination_errors: Queue = Queue()

    def _after_cursor_execute(_conn, _cursor, statement, _parameters, _context, _executemany):
        normalized = " ".join(str(statement).lower().split())
        name = current_thread().name
        if (
            name == "w6-locker"
            and "aa_selection_batch" in normalized
            and "for update" in normalized
            and not batch_locked.is_set()
        ):
            batch_locked.set()
            if not drop_lock_observed.wait(timeout=10):
                coordination_errors.put("drop thread never acquired its first Selection FOR UPDATE")
        elif (
            name == "w6-dropper"
            and "for update" in normalized
            and not drop_lock_observed.is_set()
        ):
            if "aa_selection_course" in normalized:
                first_drop_lock.put("course")
                drop_lock_observed.set()
            elif "aa_selection_record" in normalized:
                first_drop_lock.put("record")
                drop_lock_observed.set()
    engine = get_engine()
    event.listen(engine, "after_cursor_execute", _after_cursor_execute)
    outcomes: Queue = Queue()
    locker = Thread(
        name="w6-locker",
        target=_run,
        args=(
            outcomes,
            "lock",
            _admin_user(),
            lambda: selection_final.lock_batch(_admin_user(), int(batch_id)),
        ),
    )
    dropper = Thread(
        name="w6-dropper",
        target=_run,
        args=(
            outcomes,
            "drop",
            _student_user(int(ids["s1"])),
            lambda: selection_final.student_drop(
                _student_user(int(ids["s1"])),
                SimpleNamespace(selectionCourseId=str(selection_course_id)),
            ),
        ),
    )

    try:
        locker.start()
        assert batch_locked.wait(timeout=10), "LOCK command did not acquire batch FOR UPDATE"
        dropper.start()
        locker.join(timeout=15)
        dropper.join(timeout=15)
    finally:
        event.remove(engine, "after_cursor_execute", _after_cursor_execute)

    assert not locker.is_alive(), "LOCK command did not terminate"
    assert not dropper.is_alive(), "DROP command did not terminate"
    assert coordination_errors.empty(), list(coordination_errors.queue)
    assert outcomes.qsize() == 2

    result = {}
    while not outcomes.empty():
        key, state, payload = outcomes.get_nowait()
        result[key] = (state, payload)

    assert set(result) == {"lock", "drop"}
    deadlocks = {
        key: payload
        for key, (state, payload) in result.items()
        if state == "error" and _captures_mysql_deadlock(payload)
    }
    assert not deadlocks, {
        key: f"{type(exc).__name__}: {exc}" for key, exc in deadlocks.items()
    }

    assert first_drop_lock.qsize() == 1
    assert first_drop_lock.get_nowait() == "course"

    lock_state, lock_payload = result["lock"]
    assert lock_state == "ok", f"LOCK failed: {lock_payload!r}"
    assert str(lock_payload.get("status") or "") == "LOCKED"

    drop_state, drop_payload = result["drop"]
    assert drop_state == "error", f"DROP unexpectedly succeeded: {drop_payload!r}"
    assert isinstance(drop_payload, AppException), repr(drop_payload)
    assert "当前不在退课窗口" in str(getattr(drop_payload, "message", "") or drop_payload)

    state = _final_state(int(batch_id), int(selection_course_id), int(ids["s1"]))
    assert state == {
        "batchStatus": "LOCKED",
        "recordStatus": "LOCKED",
        "selectedCount": 1,
    }, {"recordId": record_id, **state}
