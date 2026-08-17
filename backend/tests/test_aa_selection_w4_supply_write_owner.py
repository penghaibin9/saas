"""B-W4 production audit: formal supply mutations must not fall back to legacy writes."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "app/modules/academic_affairs/routers/course_selection_router.py"
COMMAND = ROOT / "app/modules/academic_affairs/services/academic_affairs_selection_course_command_service.py"


def test_w4_formal_supply_router_owns_all_three_mutations():
    router = ROUTER.read_text(encoding="utf-8")

    assert "selection_course_command_svc.add_course(user, batchId, body)" in router
    assert "selection_course_command_svc.update_course(user, courseId, body)" in router
    assert "selection_course_command_svc.cancel_course(user, courseId)" in router
    assert "selection_svc.add_course(user, batchId, body)" not in router
    assert "selection_svc.update_course(user, courseId, body)" not in router
    assert "selection_svc.cancel_course(user, courseId)" not in router


def test_w4_supply_update_and_cancel_freeze_rows_and_term_authority():
    source = COMMAND.read_text(encoding="utf-8")

    assert "def update_course(" in source
    assert "def cancel_course(" in source
    assert source.count("_selection._guard_batch_writable(db, batch)") >= 3

    update_start = source.index("def update_course(")
    update_course_lock = source.index("course = _lock_supply_course", update_start)
    update_batch_lock = source.index("batch = _lock_supply_batch", update_start)
    update_guard = source.index("_selection._guard_batch_writable", update_start)
    update_commit = source.index("db.commit()", update_start)
    assert update_start < update_course_lock < update_batch_lock < update_guard < update_commit

    cancel_start = source.index("def cancel_course(")
    cancel_course_lock = source.index("course = _lock_supply_course", cancel_start)
    cancel_batch_lock = source.index("batch = _lock_supply_batch", cancel_start)
    cancel_guard = source.index("_selection._guard_batch_writable", cancel_start)
    cancel_commit = source.index("db.commit()", cancel_start)
    assert cancel_start < cancel_course_lock < cancel_batch_lock < cancel_guard < cancel_commit


def test_w4_capacity_invariants_are_atomic_and_shared_formation_is_untouched():
    source = COMMAND.read_text(encoding="utf-8")

    assert "next_capacity < selected_count" in source
    assert "next_min_capacity < 0" in source
    assert "next_min_capacity > next_capacity" in source
    assert "formationMode" not in source
    assert "formation_mode" not in source
    assert "series_key" not in source
