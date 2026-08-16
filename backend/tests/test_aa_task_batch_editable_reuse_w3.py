"""A-W3 editable TeachingTask batch reuse on real MySQL state transitions."""
from __future__ import annotations

from tests.test_aa_teaching_task import (
    BASE,
    _enabled_course,
    _generate,
    _hdr,
    _published_bound_program,
    _seed,
    _tasks,
    _term,
)


def test_returned_batch_generation_reuses_same_editable_batch(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    course_id = _enabled_course(client, hdr, code="WTER101")
    _published_bound_program(client, hdr, course_id, ids["class"], ids["major"])
    term_id = _term(client, hdr)

    first = _generate(client, hdr, term_id)
    batch_id = first["batchId"]
    task_id = _tasks(client, hdr, batch_id)[0]["taskId"]

    assigned = client.post(
        f"{BASE}/teaching-tasks/{task_id}/assign",
        headers=hdr,
        json={"teacherName": "王老师", "teacherKey": "academic01", "expectedStudents": 40},
    )
    assert assigned.status_code == 200, assigned.text
    confirmed = client.post(
        f"{BASE}/teaching-tasks/{task_id}/teacher-act",
        headers=hdr,
        json={"action": "CONFIRM"},
    )
    assert confirmed.status_code == 200, confirmed.text
    college_confirmed = client.post(
        f"{BASE}/teaching-task-batches/{batch_id}/college-confirm",
        headers=hdr,
    )
    assert college_confirmed.status_code == 200, college_confirmed.text

    returned = client.post(
        f"{BASE}/teaching-task-batches/{batch_id}/review",
        headers=hdr,
        json={"action": "RETURN", "reason": "任课安排需要调整后重新提交"},
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["data"]["status"] == "RETURNED"

    replay = _generate(client, hdr, term_id)
    assert replay["batchId"] == batch_id
    assert replay["status"] == "RETURNED"
    assert replay["tasksGenerated"] == 0
    tasks = _tasks(client, hdr, batch_id)
    assert len(tasks) == 1
    assert tasks[0]["taskId"] == task_id

    reconfirmed = client.post(
        f"{BASE}/teaching-task-batches/{batch_id}/college-confirm",
        headers=hdr,
    )
    assert reconfirmed.status_code == 200, reconfirmed.text
    assert reconfirmed.json()["data"]["status"] == "COLLEGE_CONFIRMED"
