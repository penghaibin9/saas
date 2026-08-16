from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001


def _set_tenant():
    from app.core.context import set_tenant

    set_tenant({"tenantId": str(TID)})


def _active_user(db):
    from app.models import User

    return db.query(User).filter(
        User.tenant_id == TID,
        User.status == "ACTIVE",
        User.is_deleted.is_(False),
        User.login_name.isnot(None),
    ).order_by(User.id).first()


def _seed_assignment(db, teacher_key: str):
    from app.models import AaExamBatch, AaExamCourse, AaExamInvigilator, AaExamRoom

    batch = AaExamBatch(
        tenant_id=TID,
        batch_name="C-W3监考发布通知",
        status="PUBLISHED",
        published_at=datetime.utcnow(),
    )
    db.add(batch)
    db.flush()
    course = AaExamCourse(
        tenant_id=TID,
        batch_id=batch.id,
        course_name="C-W3监考通知课程",
        exam_date="2029-01-18",
        start_time="09:00",
        end_time="11:00",
        status="CONFIRMED",
    )
    db.add(course)
    db.flush()
    room = AaExamRoom(
        tenant_id=TID,
        exam_course_id=course.id,
        room_seq=1,
        classroom_text="C-W3-501",
        capacity=30,
        planned_count=1,
        seat_mode="SEQUENTIAL",
        source="MANUAL",
        status="ACTIVE",
    )
    db.add(room)
    db.flush()
    invigilator = AaExamInvigilator(
        tenant_id=TID,
        exam_room_id=room.id,
        teacher_key=teacher_key,
        teacher_name="C-W3监考教师",
        role="CHIEF",
        confirm_status="ASSIGNED",
    )
    db.add(invigilator)
    db.flush()
    return batch, course, invigilator


def test_publish_delivery_emits_teacher_outbox_from_current_canonical_assignment(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import MessageEventOutbox
    from app.modules.academic_affairs.services import academic_affairs_exam_publish_delivery_guard as delivery

    # Boot the normal test seed and prove the recipient is a real active account, not a display-name guess.
    response = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    )
    assert response.status_code == 200, response.text
    _set_tenant()

    db = get_sessionmaker()()
    user = _active_user(db)
    assert user is not None and user.login_name
    batch, course, invigilator = _seed_assignment(db, str(user.login_name))

    sent = delivery.emit_published_invigilation_notices(db, batch, [course])
    assert sent == 1
    row = db.query(MessageEventOutbox).filter(
        MessageEventOutbox.tenant_id == TID,
        MessageEventOutbox.source_biz_type == "exam_invigilator",
        MessageEventOutbox.source_biz_id == invigilator.id,
        MessageEventOutbox.is_deleted.is_(False),
    ).one()
    assert row.event_code == "EXAM.ARRANGED"
    assert row.recipient_refs_json == [{"userId": int(user.id)}]
    assert row.dedup_key == f"EXAM.ARRANGED:invigilator:{invigilator.id}:batch:{batch.id}"
    assert "C-W3监考通知课程" in (row.payload_json or {}).get("title", "")
    assert "C-W3-501" in (row.payload_json or {}).get("content", "")
    assert "主监考" in (row.payload_json or {}).get("content", "")

    # Replaying the hook is idempotent through the existing Outbox dedup authority.
    assert delivery.emit_published_invigilation_notices(db, batch, [course]) == 1
    assert db.query(MessageEventOutbox).filter(
        MessageEventOutbox.tenant_id == TID,
        MessageEventOutbox.dedup_key == row.dedup_key,
        MessageEventOutbox.is_deleted.is_(False),
    ).count() == 1
    db.rollback()
    db.close()


def test_publish_delivery_does_not_guess_unmapped_teacher_account(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import MessageEventOutbox
    from app.modules.academic_affairs.services import academic_affairs_exam_publish_delivery_guard as delivery

    response = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    )
    assert response.status_code == 200, response.text
    _set_tenant()

    db = get_sessionmaker()()
    batch, course, invigilator = _seed_assignment(db, "cw3_unmapped_teacher_key")
    assert delivery.emit_published_invigilation_notices(db, batch, [course]) == 0
    assert db.query(MessageEventOutbox).filter(
        MessageEventOutbox.tenant_id == TID,
        MessageEventOutbox.source_biz_type == "exam_invigilator",
        MessageEventOutbox.source_biz_id == invigilator.id,
        MessageEventOutbox.is_deleted.is_(False),
    ).count() == 0
    db.rollback()
    db.close()


def test_delivery_guard_only_extends_notify_hook_not_publish_or_assignment_authority():
    import inspect
    from app.modules.academic_affairs.services import academic_affairs_exam_publish_delivery_guard as delivery

    source = inspect.getsource(delivery)
    assert "legacy._notify_publish = _notify_publish_with_invigilators" in source
    assert "student_sent = int(original(db, batch, courses) or 0)" in source
    for forbidden in (
        "legacy.publish_batch =",
        "change_invigilator =",
        "assign_invigilator =",
        "AaExamInvigilator(",
        "db.commit(",
    ):
        assert forbidden not in source
