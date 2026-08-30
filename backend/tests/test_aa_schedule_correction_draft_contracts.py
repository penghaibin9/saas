from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_correction_draft_keeps_current_truth_and_clones_existing_items():
    service = _read(
        "app/modules/academic_affairs/services/academic_affairs_schedule_final_service.py"
    )

    assert "def start_correction_draft" in service
    assert 'source.status != "PUBLISHED"' in service
    assert "head.active_batch_id" in service
    assert "supersedes_batch_id=source.id" in service
    assert "batch_id=draft.id" in service
    assert 'status="DRAFT"' in service
    assert 'source="MANUAL"' in service
    assert "source.status = \"ARCHIVED\"" not in service
    assert "db.commit()" in service


def test_correction_draft_is_idempotent_and_publish_excludes_only_replaced_truth():
    service = _read(
        "app/modules/academic_affairs/services/academic_affairs_schedule_final_service.py"
    )
    truth = _read(
        "app/modules/academic_affairs/services/academic_affairs_schedule_truth_service.py"
    )

    assert 'AaScheduleBatch.status.in_(("DRAFT", "PRE_PUBLISHED"))' in service
    assert "idempotent=True" in service
    assert "replacing_batch_id=int(head.active_batch_id)" in service
    assert "def require_no_school_wide_conflict(db, batch, *, replacing_batch_id=None)" in truth
    assert "AaScheduleBatch.id.notin_(excluded)" in truth


def test_correction_draft_route_is_owned_by_schedule_core_router():
    router = _read(
        "app/modules/academic_affairs/routers/schedule_core_router.py"
    )

    assert '@router.post("/schedule-batches/{batchId}/correction-draft"' in router
    assert "sched_svc.start_correction_draft(batchId, user, body.reason)" in router
    assert 'require_permission("academicAffairs.schedule.edit")' in router


def test_correction_draft_participates_in_schedule_write_scope_binding():
    guard = _read(
        "app/modules/academic_affairs/services/academic_affairs_schedule_write_scope_r3.py"
    )

    assert '"start_correction_draft"' in guard
    assert "assert_schedule_write_scope(db, actor, batch)" in guard
