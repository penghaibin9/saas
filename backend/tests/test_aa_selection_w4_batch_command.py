"""B production audit: canonical batch writes, strict term refs, scheduled lifecycle."""
from __future__ import annotations

import itertools
from datetime import datetime, timedelta
from pathlib import Path


BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001
_SEQ = itertools.count(1)
ROOT = Path(__file__).resolve().parents[1]


def _admin(client):
    data = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    ).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_tick_batches(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaCourse, AaSelectionBatch, AaSelectionCourse, AaTerm

    n = next(_SEQ)
    db = get_sessionmaker()()
    try:
        term = AaTerm(
            tenant_id=TID,
            year_code=f"31{n:02d}-31{n + 1:02d}",
            term_no=1,
            term_name=f"Tick学期{n}",
            teaching_weeks=20,
            status="PUBLISHED",
            is_current=False,
        )
        course = AaCourse(
            tenant_id=TID,
            course_code=f"TICK{n:05d}",
            course_name=f"Tick正式课程{n}",
            credit=2,
            status="ENABLED",
        )
        db.add_all([term, course])
        db.flush()

        now = datetime.utcnow()
        good = AaSelectionBatch(
            tenant_id=TID,
            batch_name=f"Tick正常批次{n}",
            term_id=term.id,
            select_start_at=now - timedelta(minutes=5),
            select_end_at=now + timedelta(hours=1),
            apply_scope_json="{}",
            rule_json="{}",
            status="PUBLISHED",
        )
        bad = AaSelectionBatch(
            tenant_id=TID,
            batch_name=f"Tick坏配置批次{n}",
            term_id=term.id,
            select_start_at=now - timedelta(minutes=5),
            select_end_at=now + timedelta(hours=1),
            apply_scope_json="{}",
            rule_json="{broken-json",
            status="PUBLISHED",
        )
        db.add_all([good, bad])
        db.flush()

        for batch in (good, bad):
            db.add(AaSelectionCourse(
                tenant_id=TID,
                batch_id=batch.id,
                course_id=course.id,
                course_name=course.course_name,
                teaching_task_id=None,
                credit=course.credit,
                capacity=20,
                min_capacity=1,
                selected_count=0,
                status="OPEN",
            ))
        db.commit()
        return int(good.id), int(bad.id)
    finally:
        db.close()


def _seed_soft_deleted_term_batch(db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaSelectionBatch, AaTerm

    n = next(_SEQ)
    db = get_sessionmaker()()
    try:
        term = AaTerm(
            tenant_id=TID,
            year_code=f"41{n:02d}-41{n + 1:02d}",
            term_no=1,
            term_name=f"Dangling学期{n}",
            teaching_weeks=20,
            status="PUBLISHED",
            is_current=False,
        )
        db.add(term)
        db.flush()
        batch = AaSelectionBatch(
            tenant_id=TID,
            batch_name=f"Dangling批次{n}",
            term_id=term.id,
            apply_scope_json="{}",
            rule_json=None,
            status="DRAFT",
        )
        db.add(batch)
        db.flush()
        ids = (int(term.id), int(batch.id))
        term.is_deleted = True
        db.commit()
        return ids
    finally:
        db.close()


def test_time_tick_uses_preflight_and_bad_batch_does_not_poison_good_batch(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaSelectionBatch

    good_id, bad_id = _seed_tick_batches(db_mode)
    response = client.post(f"{BASE}/selection/time-tick", headers=_admin(client))
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["opened"] == 1
    assert data["closed"] == 0
    assert data["blockedCount"] == 1
    assert data["blocked"][0]["batchId"] == str(bad_id)
    assert "规则" in data["blocked"][0]["message"]

    db = get_sessionmaker()()
    try:
        statuses = {
            int(row.id): str(row.status)
            for row in db.query(AaSelectionBatch).filter(
                AaSelectionBatch.tenant_id == TID,
                AaSelectionBatch.id.in_([good_id, bad_id]),
            ).all()
        }
        assert statuses[good_id] == "OPEN"
        assert statuses[bad_id] == "PUBLISHED"
    finally:
        db.close()


def test_batch_create_allows_termless_draft_but_rejects_explicit_unknown_term(client, db_mode):
    admin = _admin(client)
    draft = client.post(
        f"{BASE}/selection/batches",
        headers=admin,
        json={"batchName": f"待绑定学期批次{next(_SEQ)}"},
    )
    assert draft.status_code == 200, draft.text
    assert draft.json()["data"]["termId"] is None
    assert draft.json()["data"]["status"] == "DRAFT"

    rejected = client.post(
        f"{BASE}/selection/batches",
        headers=admin,
        json={"batchName": f"伪学期批次{next(_SEQ)}", "termId": "999999999999999999"},
    )
    assert rejected.status_code == 409, rejected.text
    assert "学期不存在或已删除" in rejected.text


def test_soft_deleted_term_blocks_preflight_and_locked_rule_write(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaSelectionBatch

    _, batch_id = _seed_soft_deleted_term_batch(db_mode)
    admin = _admin(client)

    preflight = client.get(
        f"{BASE}/selection/batches/{batch_id}/preflight?action=PUBLISH",
        headers=admin,
    )
    assert preflight.status_code == 200, preflight.text
    blocker_codes = {row["code"] for row in preflight.json()["data"]["blockers"]}
    assert "SELECTION_TERM_INVALID" in blocker_codes

    save = client.put(
        f"{BASE}/selection/batches/{batch_id}/rule",
        headers=admin,
        json={"rule": {"maxCredits": 12}},
    )
    assert save.status_code == 409, save.text
    assert "学期不存在或已删除" in save.text

    db = get_sessionmaker()()
    try:
        batch = db.query(AaSelectionBatch).filter(
            AaSelectionBatch.tenant_id == TID,
            AaSelectionBatch.id == batch_id,
        ).one()
        assert batch.rule_json is None
    finally:
        db.close()


def test_batch_command_source_locks_rule_write_and_reuses_w1_preflight():
    source = (
        ROOT / "app/modules/academic_affairs/services/academic_affairs_selection_batch_command_service.py"
    ).read_text(encoding="utf-8")
    selection_source = (
        ROOT / "app/modules/academic_affairs/services/academic_affairs_selection_service.py"
    ).read_text(encoding="utf-8")
    preflight_source = (
        ROOT / "app/modules/academic_affairs/services/academic_affairs_selection_preflight_service.py"
    ).read_text(encoding="utf-8")
    router = (
        ROOT / "app/modules/academic_affairs/routers/course_selection_router.py"
    ).read_text(encoding="utf-8")

    assert "def create_batch(" in source
    assert "def save_rule(" in source
    assert "def run_time_tick(" in source
    assert "select(AaSelectionBatch)" in source
    assert ".with_for_update()" in source
    assert "_guard_batch_writable(db, batch)" in source
    assert "_require_term_reference_writable(db, raw_term_id" in source
    assert 'require_batch_action(db, batch, "OPEN")' in source
    assert 'require_batch_action(db, batch, "CLOSE")' in source
    assert "except AppException as exc" in source

    assert "def _require_term_reference_writable(" in selection_source
    assert "AaTerm.is_deleted.is_(False)" in selection_source
    term_lock = selection_source.index("select(AaTerm).where(")
    archive_check = selection_source.index("archive_service.guard_term_writable")
    assert term_lock < archive_check
    assert ".with_for_update()" in selection_source[term_lock:archive_check]

    assert "_validate_term_reference(db, batch, blockers)" in preflight_source
    assert "SELECTION_TERM_INVALID" in preflight_source
    preflight_guard = preflight_source[
        preflight_source.index("def _validate_term_reference"):
        preflight_source.index("def evaluate_batch")
    ]
    assert ".with_for_update()" not in preflight_guard

    assert "selection_batch_command_svc.create_batch" in router
    assert "selection_batch_command_svc.save_rule" in router
    assert "selection_batch_command_svc.run_time_tick" in router
    assert "selection_svc.create_batch" not in router
    assert "selection_svc.save_rule" not in router
    assert "selection_svc.run_time_tick" not in router
