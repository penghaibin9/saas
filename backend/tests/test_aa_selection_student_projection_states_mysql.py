"""B-W5 student projection terminal/lottery states on fresh MySQL.

This file extends only the B-C3 read projection.  Lottery draw/capacity and Selection
LOCK state-machine behavior remain owned by their existing focused suites; here we assert
that those canonical facts are projected to stable student-facing status/allowedActions.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_FIXTURE_PATH = Path(__file__).with_name("test_aa_selection.py")
_SPEC = spec_from_file_location("academic_b_w5_state_fixtures", _FIXTURE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_FIXTURES = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FIXTURES)

BASE = _FIXTURES.BASE
_hdr = _FIXTURES._hdr
_make_open_batch = _FIXTURES._make_open_batch
_new_batch = _FIXTURES._new_batch
_ready_tasks = _FIXTURES._ready_tasks
_seed = _FIXTURES._seed
_stu_token = _FIXTURES._stu_token


def _course_projection(payload, selection_course_id):
    for group in payload["data"]["items"]:
        for course in group.get("courses") or []:
            if str(course.get("selectionCourseId")) == str(selection_course_id):
                return group, course
    raise AssertionError(f"projection missing selectionCourseId={selection_course_id}")


def _create_round(client, admin, batch_id, *, name, mode="LOTTERY"):
    response = client.post(
        f"{BASE}/selection/batches/{batch_id}/rounds",
        headers=admin,
        json={
            "roundName": name,
            "mode": mode,
            "allowEnroll": True,
            "allowDrop": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["roundId"]


def test_w5_pending_and_lottery_lost_projection_follow_canonical_round_fact(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    task1, _task2 = _ready_tasks(ids)
    batch_id, selection_course_id = _make_open_batch(
        client,
        admin,
        ids["course1"],
        capacity=1,
        name="W5抽签状态投影",
        teaching_task_id=task1,
    )
    round_id = _create_round(client, admin, batch_id, name="W5抽签投影轮次")
    opened = client.post(f"{BASE}/selection/rounds/{round_id}/open", headers=admin)
    assert opened.status_code == 200, opened.text

    students = (
        ("选甲", "SEL2401"),
        ("选乙", "SEL2402"),
    )
    for real_name, student_no in students:
        enrolled = client.post(
            f"{BASE}/selection/student/enroll",
            headers=_stu_token(real_name, student_no),
            json={"selectionCourseId": str(selection_course_id)},
        )
        assert enrolled.status_code == 200, enrolled.text
        assert enrolled.json()["data"]["status"] == "PENDING_LOTTERY"

    pending_token = _stu_token(*students[0])
    pending_response = client.get(f"{BASE}/selection/student/courses", headers=pending_token)
    assert pending_response.status_code == 200, pending_response.text
    _group, pending = _course_projection(pending_response.json(), selection_course_id)
    assert pending["status"] == "PENDING_LOTTERY"
    assert pending["statusLabel"] == "待抽签"
    assert pending["eligibility"] == "INELIGIBLE"
    assert pending["allowedActions"] == ["VIEW", "DROP"]
    assert pending["lottery"]["mode"] == "LOTTERY"

    closed = client.post(f"{BASE}/selection/rounds/{round_id}/close", headers=admin)
    assert closed.status_code == 200, closed.text
    drawn = client.post(f"{BASE}/selection/rounds/{round_id}/draw", headers=admin)
    assert drawn.status_code == 200, drawn.text
    assert drawn.json()["data"]["totalWinners"] == 1
    assert drawn.json()["data"]["totalLosers"] == 1

    from app.db.session import get_sessionmaker
    from app.models import AaSelectionRecord

    db = get_sessionmaker()()
    try:
        loser = db.query(AaSelectionRecord).filter(
            AaSelectionRecord.batch_id == int(batch_id),
            AaSelectionRecord.status == "LOTTERY_LOST",
            AaSelectionRecord.is_deleted.is_(False),
        ).one()
        loser_no = str(loser.student_no)
    finally:
        db.close()

    loser_token = _stu_token("lottery-loser", loser_no)
    loser_response = client.get(f"{BASE}/selection/student/courses", headers=loser_token)
    assert loser_response.status_code == 200, loser_response.text
    _group, lost = _course_projection(loser_response.json(), selection_course_id)
    assert lost["status"] == "LOTTERY_LOST"
    assert lost["statusLabel"] == "未中签"
    assert lost["eligibility"] == "INELIGIBLE"
    assert lost["allowedActions"] == ["VIEW"]

    preflight = client.post(
        f"{BASE}/selection/student/preflight",
        headers=loser_token,
        json={"selectionCourseId": str(selection_course_id)},
    )
    assert preflight.status_code == 200, preflight.text
    projected = preflight.json()["data"]
    assert projected["status"] == lost["status"]
    assert projected["allowedActions"] == lost["allowedActions"]


def test_w5_course_cancelled_projection_stays_visible_but_not_actionable(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    task1, task2 = _ready_tasks(ids)
    batch_id = _new_batch(client, admin, "W5取消课程投影")

    added1 = client.post(
        f"{BASE}/selection/batches/{batch_id}/courses",
        headers=admin,
        json={
            "courseId": str(ids["course1"]),
            "teachingTaskId": str(task1),
            "capacity": 30,
            "minCapacity": 1,
        },
    )
    added2 = client.post(
        f"{BASE}/selection/batches/{batch_id}/courses",
        headers=admin,
        json={
            "courseId": str(ids["course2"]),
            "teachingTaskId": str(task2),
            "capacity": 30,
            "minCapacity": 1,
        },
    )
    assert added1.status_code == 200, added1.text
    assert added2.status_code == 200, added2.text
    cancelled_id = added1.json()["data"]["selectionCourseId"]
    alternate_id = added2.json()["data"]["selectionCourseId"]

    assert client.post(f"{BASE}/selection/batches/{batch_id}/publish", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/batches/{batch_id}/open", headers=admin).status_code == 200
    student = _stu_token("选甲", "SEL2401")
    selected = client.post(
        f"{BASE}/selection/student/enroll",
        headers=student,
        json={"selectionCourseId": str(cancelled_id)},
    )
    assert selected.status_code == 200, selected.text
    assert client.post(f"{BASE}/selection/batches/{batch_id}/close", headers=admin).status_code == 200
    cancelled = client.post(f"{BASE}/selection/courses/{cancelled_id}/cancel", headers=admin)
    assert cancelled.status_code == 200, cancelled.text

    response = client.get(f"{BASE}/selection/student/courses", headers=student)
    assert response.status_code == 200, response.text
    _group, cancelled_course = _course_projection(response.json(), cancelled_id)
    assert cancelled_course["status"] == "COURSE_CANCELLED"
    assert cancelled_course["statusLabel"] == "课程已取消"
    assert cancelled_course["allowedActions"] == ["VIEW"]
    assert cancelled_course["eligibility"] == "INELIGIBLE"
    assert cancelled_course["reason"]

    _group, alternate = _course_projection(response.json(), alternate_id)
    assert alternate["phase"] == "RESELECT"
    assert alternate["reselect"] is True
    assert alternate["allowedActions"] == ["VIEW", "ENROLL"]


def test_w5_locked_record_preflight_projects_view_only_terminal_state(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    task1, _task2 = _ready_tasks(ids)
    batch_id, selection_course_id = _make_open_batch(
        client,
        admin,
        ids["course1"],
        capacity=5,
        name="W5锁定状态投影",
        teaching_task_id=task1,
    )
    student = _stu_token("选甲", "SEL2401")
    enrolled = client.post(
        f"{BASE}/selection/student/enroll",
        headers=student,
        json={"selectionCourseId": str(selection_course_id)},
    )
    assert enrolled.status_code == 200, enrolled.text
    assert client.post(f"{BASE}/selection/batches/{batch_id}/close", headers=admin).status_code == 200
    locked = client.post(f"{BASE}/selection/batches/{batch_id}/lock", headers=admin)
    assert locked.status_code == 200, locked.text
    assert locked.json()["data"]["status"] == "LOCKED"

    preflight = client.post(
        f"{BASE}/selection/student/preflight",
        headers=student,
        json={"selectionCourseId": str(selection_course_id)},
    )
    assert preflight.status_code == 200, preflight.text
    projected = preflight.json()["data"]
    assert projected["status"] == "LOCKED"
    assert projected["statusLabel"] == "名单已锁定"
    assert projected["phase"] == "LOCKED"
    assert projected["eligibility"] == "INELIGIBLE"
    assert projected["allowedActions"] == ["VIEW"]
    assert projected["reason"]
    assert projected["howToResolve"]
