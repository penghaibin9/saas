"""INT lock-order contract for Program DEFINITION confirmation."""
from __future__ import annotations

import inspect


def _service():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_confirm_service as service
    return service


def test_definition_confirm_prelocks_program_series_before_security_major_and_course_loads():
    service = _service()
    confirm_source = inspect.getsource(service.confirm_program_definition_import)
    prelock_at = confirm_source.index("_prelock_existing_program_series(db, rows)")
    security_at = confirm_source.index("build_affairs_context(user, db)")
    preflight_at = confirm_source.index("run_program_import_preflight(")

    assert prelock_at < security_at < preflight_at
    assert "_program_snapshots(db, keys)" in inspect.getsource(
        service._prelock_existing_program_series
    )
    assert ".with_for_update()" in inspect.getsource(service._program_snapshots)


def test_program_prelock_keys_are_main_only_uppercase_and_deterministic():
    service = _service()
    assert service._source_series_keys([
        {
            "logicalGroup": "COURSE",
            "payload": {"programSeriesKey": "ignored"},
        },
        {
            "logicalGroup": "MAIN",
            "payload": {"programSeriesKey": " series-b "},
        },
        {
            "logicalGroup": "MAIN",
            "payload": {"programSeriesKey": "SERIES-A"},
        },
        {
            "logicalGroup": "MAIN",
            "payload": {"programSeriesKey": "series-b"},
        },
    ]) == ("SERIES-A", "SERIES-B")
