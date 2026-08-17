from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001
BASE = "/api/v1/academic-affairs"


def _set_tenant():
    from app.core.context import set_tenant

    set_tenant({"tenantId": str(TID)})


def _admin_headers(client):
    response = client.post(
        "/api/v1/auth/mock-login",
        json={"loginName": "school_admin01", "password": "any"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def _ensure_teacher_users(db, count=2):
    """Seed only the teacher identities this contract owns; never depend on ambient DB users."""
    from app.models import User

    users = []
    for index in range(1, count + 1):
        login_name = f"cw3_delivery_teacher_{index:02d}"
        user = db.query(User).filter(
            User.tenant_id == TID,
            User.login_name == login_name,
            User.is_deleted.is_(False),
        ).one_or_none()
        if user is None:
            user = User(
                tenant_id=TID,
                login_name=login_name,
                real_name=f"C-W3监考教师{index}",
                password_hash="cw3-contract-password-not-used",
                user_type="TEACHER",
                status="ACTIVE",
                is_deleted=False,
            )
            db.add(user)
        else:
            user.real_name = f"C-W3监考教师{index}"
            user.user_type = "TEACHER"
            user.status = "ACTIVE"
        users.append(user)
    db.flush()
    return users


def _ensure_teacher_user(db):
    return _ensure_teacher_users(db, 1)[0]


def _seed_assignment(db, teacher_key: str, *, batch_status="PUBLISHED"):
    from app.models import AaExamBatch, AaExamCourse, AaExamInvigilator, AaExamRoom

    batch = AaExamBatch(
        tenant_id=TID,
        batch_name="C-W3监考发布通知",
        status=batch_status,
        published_at=datetime.utcnow() if batch_status in {"PUBLISHED", "FINISHED"} else None,
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
        confirm_status="CONFIRMED",
    )
    db.add(invigilator)
    db.flush()
    return batch, course, room, invigilator


def test_publish_delivery_emits_teacher_outbox_from_current_canonical_assignment(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import MessageEventOutbox
    from app.modules.academic_affairs.services import academic_affairs_exam_publish_delivery_guard as delivery

    _admin_headers(client)
    _set_tenant()

    db = get_sessionmaker()()
    user = _ensure_teacher_user(db)
    assert user.login_name
    batch, course, _room, invigilator = _seed_assignment(db, str(user.login_name))

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

    _admin_headers(client)
    _set_tenant()

    db = get_sessionmaker()()
    batch, course, _room, invigilator = _seed_assignment(db, "cw3_unmapped_teacher_key")
    assert delivery.emit_published_invigilation_notices(db, batch, [course]) == 0
    assert db.query(MessageEventOutbox).filter(
        MessageEventOutbox.tenant_id == TID,
        MessageEventOutbox.source_biz_type == "exam_invigilator",
        MessageEventOutbox.source_biz_id == invigilator.id,
        MessageEventOutbox.is_deleted.is_(False),
    ).count() == 0
    db.rollback()
    db.close()


def test_published_reassignment_keeps_one_assignment_and_notifies_old_and_new_teacher(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaExamInvigilator, MessageEventOutbox

    admin = _admin_headers(client)
    _set_tenant()
    db = get_sessionmaker()()
    users = _ensure_teacher_users(db, 2)
    assert len(users) == 2
    old_user, new_user = users
    assert old_user.login_name and new_user.login_name and old_user.id != new_user.id
    _batch, _course, room, invigilator = _seed_assignment(db, str(old_user.login_name))
    invigilator_id = int(invigilator.id)
    room_id = int(room.id)
    db.commit()
    db.close()

    changed = client.post(
        f"{BASE}/exam/rooms/{room_id}/invigilators/change",
        headers=admin,
        json={
            "oldTeacherKey": str(old_user.login_name),
            "newTeacherKey": str(new_user.login_name),
            "newTeacherName": "C-W3接替教师",
            "newRole": "ASSISTANT",
            "reason": "C-W3发布后临时改派验证",
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["invigilatorId"] == str(invigilator_id)

    db = get_sessionmaker()()
    rows = db.query(AaExamInvigilator).filter(
        AaExamInvigilator.tenant_id == TID,
        AaExamInvigilator.exam_room_id == room_id,
        AaExamInvigilator.is_deleted.is_(False),
    ).all()
    assert len(rows) == 1
    assert int(rows[0].id) == invigilator_id
    assert rows[0].teacher_key == str(new_user.login_name)
    assert rows[0].confirm_status == "ASSIGNED"
    assert rows[0].role == "ASSISTANT"

    notices = db.query(MessageEventOutbox).filter(
        MessageEventOutbox.tenant_id == TID,
        MessageEventOutbox.source_biz_type == "exam_invigilator_change",
        MessageEventOutbox.source_biz_id == invigilator_id,
        MessageEventOutbox.is_deleted.is_(False),
    ).order_by(MessageEventOutbox.id).all()
    assert len(notices) == 2
    recipients = {
        int(ref["userId"])
        for notice in notices
        for ref in (notice.recipient_refs_json or [])
        if ref.get("userId") is not None
    }
    assert recipients == {int(old_user.id), int(new_user.id)}
    titles = [str((notice.payload_json or {}).get("title") or "") for notice in notices]
    contents = [str((notice.payload_json or {}).get("content") or "") for notice in notices]
    assert any("监考调整" in title for title in titles)
    assert any("请接替" in title for title in titles)
    assert any("原来的监考安排已调整" in content for content in contents)
    assert any("请按最新安排到场监考" in content for content in contents)
    db.close()


def test_reassignment_before_publish_fails_closed_and_rolls_back_assignment(client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import AaExamInvigilator, MessageEventOutbox

    admin = _admin_headers(client)
    _set_tenant()
    db = get_sessionmaker()()
    users = _ensure_teacher_users(db, 2)
    assert len(users) == 2
    old_user, new_user = users
    _batch, _course, room, invigilator = _seed_assignment(
        db,
        str(old_user.login_name),
        batch_status="ARRANGED",
    )
    room_id = int(room.id)
    invigilator_id = int(invigilator.id)
    db.commit()
    db.close()

    changed = client.post(
        f"{BASE}/exam/rooms/{room_id}/invigilators/change",
        headers=admin,
        json={
            "oldTeacherKey": str(old_user.login_name),
            "newTeacherKey": str(new_user.login_name),
            "newTeacherName": "C-W3不应生效教师",
            "reason": "发布前必须走正常编排入口",
        },
    )
    assert changed.status_code == 409, changed.text
    payload = changed.json()
    assert payload.get("bizCode") == "DATA_CONFLICT"
    assert "发布前请使用正常监考编排入口" in str(payload.get("message") or "")

    db = get_sessionmaker()()
    row = db.query(AaExamInvigilator).filter(
        AaExamInvigilator.tenant_id == TID,
        AaExamInvigilator.id == invigilator_id,
        AaExamInvigilator.is_deleted.is_(False),
    ).one()
    assert row.teacher_key == str(old_user.login_name)
    assert db.query(MessageEventOutbox).filter(
        MessageEventOutbox.tenant_id == TID,
        MessageEventOutbox.source_biz_type == "exam_invigilator_change",
        MessageEventOutbox.source_biz_id == invigilator_id,
        MessageEventOutbox.is_deleted.is_(False),
    ).count() == 0
    db.close()


def test_delivery_guard_only_extends_transaction_hooks_not_exam_authority():
    import inspect
    from app.modules.academic_affairs.services import academic_affairs_exam_publish_delivery_guard as delivery

    source = inspect.getsource(delivery)
    install_source = inspect.getsource(delivery.install)
    change_source = inspect.getsource(delivery.emit_invigilation_change_notices)

    assert "legacy._notify_publish = _notify_publish_with_invigilators" in install_source
    assert "legacy._audit = _audit_with_invigilation_delivery" in install_source
    assert "student_sent = int(original_notify(db, batch, courses) or 0)" in install_source
    assert 'action == "EXAM_INVIGILATOR_CHANGE"' in install_source
    assert "original_audit(db, biz_type, biz_id, action, detail, before, after)" in install_source
    assert "emit_invigilation_change_notices(" in install_source
    assert "session(" not in change_source
    assert "db.commit(" not in change_source

    for forbidden in (
        "legacy.publish_batch =",
        "legacy.change_invigilator =",
        "legacy.assign_invigilator =",
        "AaExamInvigilator(",
        "db.commit(",
    ):
        assert forbidden not in source
