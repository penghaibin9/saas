from pathlib import Path

path = Path("backend/tests/test_aa_attendance_published_occurrence_contract.py")
text = path.read_text(encoding="utf-8")
marker = "test_school_and_college_same_active_batch_dedupes_for_attendance"
if marker in text:
    raise SystemExit("C-C1 ScopeHead boundary tests already present")

text += r'''


def test_school_and_college_same_active_batch_dedupes_for_attendance(db_mode):
    from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as truth
    from app.modules.academic_affairs.services import academic_affairs_attendance_occurrence_consumer as consumer

    _ctx()
    db = _session()
    term, task_batch, task, batch, item = _seed(db, activate=True)
    school_head = truth.lock_scope_head(db, term.id, "SCHOOL", 0)
    school_head.active_batch_id = batch.id
    school_head.version = 6
    school_head.published_at = datetime(2026, 2, 20, 8, 1, 0)
    db.commit()

    result = consumer.resolve_formal_occurrence(
        db,
        task,
        task_batch,
        term,
        session_date="2026-03-02",
        slot_no=2,
    )
    assert result["activeBatchId"] == str(batch.id)
    assert result["scheduleItemId"] == str(item.id)
    db.close()


def test_same_task_in_different_active_batches_fails_closed_for_attendance(db_mode):
    from app.core.exceptions import AppException
    from app.models import AaScheduleBatch, AaScheduleItem
    from app.modules.academic_affairs.services import academic_affairs_schedule_truth_service as truth
    from app.modules.academic_affairs.services import academic_affairs_attendance_occurrence_consumer as consumer

    _ctx()
    db = _session()
    term, task_batch, task, college_batch, _college_item = _seed(db, activate=True)
    school_batch = AaScheduleBatch(
        tenant_id=TID,
        term_id=term.id,
        college_id=None,
        batch_name="C-W1冲突全校正式课表",
        status="PUBLISHED",
    )
    db.add(school_batch)
    db.flush()
    school_item = AaScheduleItem(
        tenant_id=TID,
        batch_id=school_batch.id,
        task_id=task.id,
        course_id=task.course_id,
        course_name=task.course_name,
        teacher_key=task.teacher_key,
        teacher_name=task.teacher_name,
        class_id=task.class_id,
        weekday=1,
        slot_no=2,
        start_week=1,
        end_week=18,
        week_parity="ALL",
        status="EFFECTIVE",
    )
    db.add(school_item)
    db.flush()
    school_head = truth.lock_scope_head(db, term.id, "SCHOOL", 0)
    school_head.active_batch_id = school_batch.id
    school_head.version = 9
    school_head.published_at = datetime(2026, 2, 20, 8, 2, 0)
    db.commit()

    assert int(college_batch.id) != int(school_batch.id)
    with pytest.raises(AppException) as exc:
        consumer.resolve_formal_occurrence(
            db,
            task,
            task_batch,
            term,
            session_date="2026-03-02",
            slot_no=2,
        )
    assert exc.value.http_status == 409
    assert "多个当前正式课表范围" in exc.value.message
    db.close()
'''

path.write_text(text, encoding="utf-8")
