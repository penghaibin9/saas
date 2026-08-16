from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"unexpected anchor count for {path}: {text.count(old)}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


public = Path("backend/app/modules/academic_affairs/services/academic_affairs_attendance_public_service.py")
replace_once(
    public,
    '''    existing = db.query(model).filter(
        model.tenant_id == _tid(),
        model.class_id == int(class_id or 0),
        model.teacher_key == str(teacher_key or ""),
        model.session_date == str(session_date),
        model.slot_no == int(slot_no),
        model.is_deleted.is_(False),
        _stats_session_type_condition(model),
    ).with_for_update().first()''',
    '''    # Soft deletion does not erase the historical classroom fact. Until INT finishes
    # legacy occurrence reconciliation and lands the final DB UNIQUE, the application guard
    # must lock both active and soft-deleted formal/history rows. Proven ADMIN_SPECIAL rows
    # remain excluded by the source Authority condition below.
    existing = db.query(model).filter(
        model.tenant_id == _tid(),
        model.class_id == int(class_id or 0),
        model.teacher_key == str(teacher_key or ""),
        model.session_date == str(session_date),
        model.slot_no == int(slot_no),
        _stats_session_type_condition(model),
    ).with_for_update().first()''',
)
replace_once(
    public,
    '''    ADMIN_SPECIAL remains a separate audit source and never blocks a formal classroom fact.
    """''',
    '''    ADMIN_SPECIAL remains a separate audit source and never blocks a formal classroom fact.
    Soft-deleted formal/history rows still block recreation: deletion is not a new occurrence.
    """''',
)

published = Path("backend/tests/test_aa_attendance_published_occurrence_contract.py")
text = published.read_text(encoding="utf-8")
append = r'''


def test_soft_deleted_formal_session_still_blocks_recreate_until_db_unique(monkeypatch, db_mode):
    from app.core.exceptions import AppException
    from app.models import AaAttendanceSession
    from app.modules.academic_affairs.services import academic_affairs_attendance_public_service as service

    _ctx()
    db = _session()
    _term, _task_batch, task, _batch, schedule_item = _seed(db, activate=True)
    task_id = int(task.id)
    schedule_item_id = int(schedule_item.id)
    db.commit()
    db.close()

    calls = {"roster": 0}
    _patch_roster(monkeypatch, service, calls)
    body = {
        "teachingTaskId": task_id,
        "classId": 101,
        "sessionDate": "2026-03-02",
        "slotNo": 2,
        "scheduleItemId": schedule_item_id,
        "sessionType": "常规",
    }
    created = service.create_session(_user(), body)
    created_id = int(created["sessionId"])
    assert created["sourceType"] == "FORMAL_TEACHING"

    db = _session()
    try:
        row = db.get(AaAttendanceSession, created_id)
        assert row is not None
        assert row.occurrence_identity == f"V1:TASK:{task_id}:DATE:2026-03-02:SLOT:2"
        row.is_deleted = True
        db.commit()
    finally:
        db.close()

    with pytest.raises(AppException) as exc:
        service.create_session(_user(), body)
    assert exc.value.http_status == 409
    assert exc.value.code == "DATA_CONFLICT"
    assert "请勿重复点名" in exc.value.message

    db = _session()
    try:
        rows = db.query(AaAttendanceSession).filter(
            AaAttendanceSession.tenant_id == TID,
            AaAttendanceSession.class_id == 101,
            AaAttendanceSession.session_date == "2026-03-02",
            AaAttendanceSession.slot_no == 2,
        ).all()
        assert len(rows) == 1
        assert int(rows[0].id) == created_id
        assert rows[0].is_deleted is True
    finally:
        db.close()
'''
assert "test_soft_deleted_formal_session_still_blocks_recreate_until_db_unique" not in text
published.write_text(text + append, encoding="utf-8")
