from __future__ import annotations

import inspect
from datetime import datetime, timedelta

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _admin(client):
    data = client.post("/api/v1/auth/mock-login", json={"loginName": "school_admin01", "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaTeachingTask, AaTeachingTaskBatch, AaTerm
    db = get_sessionmaker()()
    try:
        term = AaTerm(tenant_id=TID, year_code="2028-2029", term_no=1, term_name="W1预检学期",
                      start_date=datetime.utcnow() - timedelta(days=5),
                      end_date=datetime.utcnow() + timedelta(days=120), status="PUBLISHED", is_current=False)
        course = AaCourse(tenant_id=TID, course_code="W1P101", course_name="W1预检课程", credit=2, status="ENABLED")
        db.add_all([term, course]); db.flush()
        task_batch = AaTeachingTaskBatch(
            tenant_id=TID, term_id=term.id, batch_name="W1预检教学任务批次", status="APPROVED",
        )
        db.add(task_batch); db.flush()
        task = AaTeachingTask(
            tenant_id=TID, batch_id=task_batch.id, course_id=course.id,
            course_code=course.course_code, course_name=course.course_name,
            teaching_class_name="W1预检教学班", status="READY",
            weekly_hours=2, total_hours=36, start_week=1, end_week=18,
        )
        db.add(task); db.flush()
        ids = (term.id, course.id, task.id)
        db.commit()
        return ids
    finally:
        db.close()


def test_batch_preflight_is_pure_source_contract():
    from app.modules.academic_affairs.services import academic_affairs_selection_preflight_service as svc
    source = inspect.getsource(svc.evaluate_batch)
    for token in ["db.commit(", "db.add(", ".update(", "_audit("]:
        assert token not in source, token
    assert "validate_selection_lock" in source


def test_publish_open_close_share_preflight_and_lock_uses_roster_validation():
    from app.modules.academic_affairs.services import academic_affairs_selection_final_service as final
    for fn, action in [(final.publish_batch, "PUBLISH"), (final.open_batch, "OPEN"), (final.close_batch, "CLOSE"), (final.lock_batch, "LOCK")]:
        source = inspect.getsource(fn)
        assert f'require_batch_action(db, batch, "{action}")' in source


def test_admin_preflight_blocks_empty_then_allows_configured_publish(client, db_mode):
    term_id, course_id, teaching_task_id = _seed(db_mode)
    admin = _admin(client)
    created = client.post(f"{BASE}/selection/batches", headers=admin, json={"batchName": "W1纯预检", "termId": str(term_id)})
    assert created.status_code == 200, created.text
    batch_id = created.json()["data"]["batchId"]

    blocked = client.get(f"{BASE}/selection/batches/{batch_id}/preflight?action=PUBLISH", headers=admin)
    assert blocked.status_code == 200, blocked.text
    payload = blocked.json()["data"]
    assert payload["allowed"] is False
    assert "SELECTION_COURSE_EMPTY" in {item["code"] for item in payload["blockers"]}

    added = client.post(f"{BASE}/selection/batches/{batch_id}/courses", headers=admin,
                        json={"courseId": str(course_id), "teachingTaskId": str(teaching_task_id), "capacity": 30, "minCapacity": 0})
    assert added.status_code == 200, added.text
    ready = client.get(f"{BASE}/selection/batches/{batch_id}/preflight?action=PUBLISH", headers=admin)
    assert ready.status_code == 200, ready.text
    assert ready.json()["data"]["allowed"] is True
    assert ready.json()["data"]["allowedActions"] == ["PUBLISH"]

    published = client.post(f"{BASE}/selection/batches/{batch_id}/publish", headers=admin)
    assert published.status_code == 200, published.text
    open_pre = client.get(f"{BASE}/selection/batches/{batch_id}/preflight?action=OPEN", headers=admin)
    assert open_pre.status_code == 200 and open_pre.json()["data"]["allowed"] is True
    opened = client.post(f"{BASE}/selection/batches/{batch_id}/open", headers=admin)
    assert opened.status_code == 200, opened.text
    close_pre = client.get(f"{BASE}/selection/batches/{batch_id}/preflight?action=CLOSE", headers=admin)
    assert close_pre.status_code == 200 and close_pre.json()["data"]["allowed"] is True
