"""B-W5 Student Selection Projection focused MySQL contracts.

Only exercises the new B-C3 read projection against existing production-grade selection
fixtures. It deliberately does not rerun the full Selection state-machine suite.
"""
from tests.test_aa_selection import (
    BASE,
    _hdr,
    _make_open_batch,
    _new_batch,
    _ready_tasks,
    _seed,
    _stu_token,
)


def _course_projection(payload, selection_course_id):
    groups = payload["data"]["items"]
    for group in groups:
        for course in group.get("courses") or []:
            if str(course.get("selectionCourseId")) == str(selection_course_id):
                return group, course
    raise AssertionError(f"projection missing selectionCourseId={selection_course_id}")


def test_w5_open_projection_matches_preflight_and_selected_drop(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    task1, _task2 = _ready_tasks(ids)
    _bid, scid = _make_open_batch(
        client, admin, ids["course1"], capacity=5,
        name="W5开放投影", teaching_task_id=task1,
    )
    stu = _stu_token("选甲", "SEL2401")

    courses_resp = client.get(f"{BASE}/selection/student/courses", headers=stu)
    assert courses_resp.status_code == 200, courses_resp.text
    _group, course = _course_projection(courses_resp.json(), scid)
    assert course["status"] == "OPEN"
    assert course["statusLabel"] == "可选"
    assert course["phase"] == "SELECTION"
    assert course["eligibility"] == "ELIGIBLE"
    assert course["allowedActions"] == ["VIEW", "ENROLL"]
    assert course["reselect"] is False
    assert course["lottery"]["mode"] == "FCFS"

    preflight = client.post(
        f"{BASE}/selection/student/preflight", headers=stu,
        json={"selectionCourseId": str(scid)},
    )
    assert preflight.status_code == 200, preflight.text
    pf = preflight.json()["data"]
    assert pf["allowed"] is True
    assert pf["allowedActions"] == course["allowedActions"]
    assert pf["status"] == course["status"]

    enrolled = client.post(
        f"{BASE}/selection/student/enroll", headers=stu,
        json={"selectionCourseId": str(scid)},
    )
    assert enrolled.status_code == 200, enrolled.text
    assert enrolled.json()["data"]["status"] == "SELECTED"

    reread = client.get(f"{BASE}/selection/student/courses", headers=stu)
    assert reread.status_code == 200, reread.text
    _group, selected = _course_projection(reread.json(), scid)
    assert selected["status"] == "SELECTED"
    assert selected["statusLabel"] == "已选"
    assert selected["allowedActions"] == ["VIEW", "DROP"]
    assert "ENROLL" not in selected["allowedActions"]

    selected_pf = client.post(
        f"{BASE}/selection/student/preflight", headers=stu,
        json={"selectionCourseId": str(scid)},
    )
    assert selected_pf.status_code == 200, selected_pf.text
    selected_pf_data = selected_pf.json()["data"]
    assert selected_pf_data["allowed"] is False
    assert selected_pf_data["status"] == "SELECTED"
    assert selected_pf_data["allowedActions"] == selected["allowedActions"]


def test_w5_full_course_projection_blocks_without_client_capacity_guess(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    task1, _task2 = _ready_tasks(ids)
    _bid, scid = _make_open_batch(
        client, admin, ids["course1"], capacity=1,
        name="W5满额投影", teaching_task_id=task1,
    )
    stu1 = _stu_token("选甲", "SEL2401")
    stu2 = _stu_token("选乙", "SEL2402")

    filled = client.post(
        f"{BASE}/selection/student/enroll", headers=stu1,
        json={"selectionCourseId": str(scid)},
    )
    assert filled.status_code == 200, filled.text

    courses_resp = client.get(f"{BASE}/selection/student/courses", headers=stu2)
    assert courses_resp.status_code == 200, courses_resp.text
    _group, blocked = _course_projection(courses_resp.json(), scid)
    assert blocked["status"] == "BLOCKED"
    assert blocked["eligibility"] == "INELIGIBLE"
    assert blocked["allowedActions"] == ["VIEW"]
    assert "课程容量已满" in blocked["reason"]
    assert blocked["howToResolve"]

    preflight = client.post(
        f"{BASE}/selection/student/preflight", headers=stu2,
        json={"selectionCourseId": str(scid)},
    )
    assert preflight.status_code == 200, preflight.text
    pf = preflight.json()["data"]
    assert pf["allowed"] is False
    assert pf["status"] == "BLOCKED"
    assert pf["allowedActions"] == ["VIEW"]
    assert "课程容量已满" in pf["reason"]


def test_w5_closed_cancelled_course_exposes_server_reselect_action(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    task1, task2 = _ready_tasks(ids)
    bid = _new_batch(client, admin, "W5补选投影")

    add1 = client.post(
        f"{BASE}/selection/batches/{bid}/courses", headers=admin,
        json={"courseId": str(ids["course1"]), "teachingTaskId": str(task1), "capacity": 30, "minCapacity": 1},
    )
    add2 = client.post(
        f"{BASE}/selection/batches/{bid}/courses", headers=admin,
        json={"courseId": str(ids["course2"]), "teachingTaskId": str(task2), "capacity": 30, "minCapacity": 1},
    )
    assert add1.status_code == 200, add1.text
    assert add2.status_code == 200, add2.text
    sc1 = add1.json()["data"]["selectionCourseId"]
    sc2 = add2.json()["data"]["selectionCourseId"]

    assert client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin).status_code == 200

    stu = _stu_token("选甲", "SEL2401")
    enrolled = client.post(
        f"{BASE}/selection/student/enroll", headers=stu,
        json={"selectionCourseId": str(sc1)},
    )
    assert enrolled.status_code == 200, enrolled.text
    assert client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin).status_code == 200
    cancelled = client.post(f"{BASE}/selection/courses/{sc1}/cancel", headers=admin)
    assert cancelled.status_code == 200, cancelled.text

    courses_resp = client.get(f"{BASE}/selection/student/courses", headers=stu)
    assert courses_resp.status_code == 200, courses_resp.text
    group, alternate = _course_projection(courses_resp.json(), sc2)
    assert group["batch"]["batchId"] == str(bid)
    assert group["batch"]["status"] == "CLOSED"
    assert alternate["phase"] == "RESELECT"
    assert alternate["reselect"] is True
    assert alternate["eligibility"] == "ELIGIBLE"
    assert alternate["allowedActions"] == ["VIEW", "ENROLL"]

    preflight = client.post(
        f"{BASE}/selection/student/preflight", headers=stu,
        json={"selectionCourseId": str(sc2)},
    )
    assert preflight.status_code == 200, preflight.text
    pf = preflight.json()["data"]
    assert pf["allowed"] is True
    assert pf["phase"] == "RESELECT"
    assert pf["reselect"] is True
    assert pf["allowedActions"] == alternate["allowedActions"]


def test_w5_explicit_batch_id_does_not_expose_draft_or_unqualified_closed_batch(client, db_mode):
    ids = _seed(db_mode)
    admin = _hdr(client, "school_admin01")
    task1, _task2 = _ready_tasks(ids)
    bid = _new_batch(client, admin, "W5学生不可见草稿")

    add = client.post(
        f"{BASE}/selection/batches/{bid}/courses", headers=admin,
        json={"courseId": str(ids["course1"]), "teachingTaskId": str(task1), "capacity": 10, "minCapacity": 1},
    )
    assert add.status_code == 200, add.text

    stu = _stu_token("选甲", "SEL2401")
    draft_read = client.get(
        f"{BASE}/selection/student/courses", headers=stu,
        params={"batchId": str(bid)},
    )
    assert draft_read.status_code == 200, draft_read.text
    assert draft_read.json()["data"]["items"] == []

    assert client.post(f"{BASE}/selection/batches/{bid}/publish", headers=admin).status_code == 200
    published_read = client.get(
        f"{BASE}/selection/student/courses", headers=stu,
        params={"batchId": str(bid)},
    )
    assert published_read.status_code == 200, published_read.text
    assert published_read.json()["data"]["items"] == []

    assert client.post(f"{BASE}/selection/batches/{bid}/open", headers=admin).status_code == 200
    assert client.post(f"{BASE}/selection/batches/{bid}/close", headers=admin).status_code == 200
    closed_read = client.get(
        f"{BASE}/selection/student/courses", headers=stu,
        params={"batchId": str(bid)},
    )
    assert closed_read.status_code == 200, closed_read.text
    assert closed_read.json()["data"]["items"] == []
