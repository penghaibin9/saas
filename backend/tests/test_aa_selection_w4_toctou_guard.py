"""B-W4 production-audit contract: supply writes freeze mutable authorities."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "app/modules/academic_affairs/services/academic_affairs_selection_course_command_service.py"


def test_w4_add_course_locks_batch_lifecycle_and_ready_task_before_insert():
    source = COMMAND.read_text(encoding="utf-8")

    # SelectionBatch must be a locking read so OPEN/PUBLISH/CLOSE cannot race a
    # stale DRAFT/PUBLISHED decision and admit supply after the lifecycle moved.
    assert "select(AaSelectionBatch)" in source
    # READY is mutable authority; the same transaction must freeze it through insert.
    assert "select(AaTeachingTask)" in source
    assert source.count(".with_for_update()") >= 2

    batch_lock = source.index("select(AaSelectionBatch)")
    lifecycle_check = source.index("if batch.status not in")
    task_lock = source.index("select(AaTeachingTask)")
    ready_check = source.index('if str(task.status or "").upper() != "READY"')
    insert = source.index("row = AaSelectionCourse(")

    assert batch_lock < lifecycle_check < task_lock < ready_check < insert


def test_w4_toctou_guard_does_not_claim_shared_formation_authority():
    source = COMMAND.read_text(encoding="utf-8")

    assert "formationMode" not in source
    assert "formation_mode" not in source
    assert "series_key" not in source
