"""C-W4 GradeTask deadline scheduler targeted contracts.

Only this policy is exercised here: 7/3/1 milestone selection, formal teacher
recipient resolution, overdue college scope, school academic visibility and durable
outbox deduplication. The shared delivery worker is tested elsewhere.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import text

TID = 1000000000000000001


def _role(db, code: str):
    from app.models import Role

    row = db.query(Role).filter(
        Role.tenant_id == TID,
        Role.role_code == code,
        Role.is_deleted.is_(False),
    ).first()
    if row is None:
        row = Role(
            tenant_id=TID,
            role_code=code,
            role_name=code,
            role_type="SYSTEM",
            status="ACTIVE",
        )
        db.add(row)
        db.flush()
    else:
        row.status = "ACTIVE"
    return row


def _user(db, login: str, *, user_type="TEACHER"):
    from app.models import User

    row = db.query(User).filter(User.tenant_id == TID, User.login_name == login).first()
    if row is None:
        row = User(
            tenant_id=TID,
            login_name=login,
            real_name=login,
            password_hash="x",
            user_type=user_type,
            status="ACTIVE",
        )
        db.add(row)
        db.flush()
    else:
        row.status = "ACTIVE"
    return row


def _assign(db, user, role):
    from app.models import UserRole

    row = db.query(UserRole).filter(
        UserRole.tenant_id == TID,
        UserRole.user_id == int(user.id),
        UserRole.role_id == int(role.id),
        UserRole.is_deleted.is_(False),
    ).first()
    if row is None:
        db.add(UserRole(
            tenant_id=TID,
            user_id=int(user.id),
            role_id=int(role.id),
            status="ACTIVE",
        ))
    else:
        row.status = "ACTIVE"
    db.flush()


def _college(db, name: str):
    from app.models import College, Major, SchoolClass

    college = College(tenant_id=TID, college_name=name, status="ACTIVE")
    db.add(college); db.flush()
    major = Major(tenant_id=TID, college_id=college.id, major_name=f"{name}专业", status="ACTIVE")
    db.add(major); db.flush()
    school_class = SchoolClass(
        tenant_id=TID,
        major_id=major.id,
        class_name=f"{name}2601",
        grade="2026",
        status="ACTIVE",
    )
    db.add(school_class); db.flush()
    return college, school_class


def _college_scope(db, user, college):
    from app.models import TeacherStudentScope

    db.add(TeacherStudentScope(
        tenant_id=TID,
        teacher_key=user.login_name,
        role_code="COLLEGE_ADMIN",
        scope_type="COLLEGE",
        ref_value=college.college_name,
        status="ACTIVE",
    ))
    db.flush()


def _grade_task(db, *, course_name: str, class_id: int, teacher_key: str, deadline: datetime):
    from app.models import AaGradeTask

    task = AaGradeTask(
        tenant_id=TID,
        course_name=course_name,
        class_id=int(class_id),
        teacher_key=teacher_key,
        usual_ratio=30,
        midterm_ratio=0,
        final_ratio=70,
        pass_line=60,
        status="INPUTTING",
    )
    db.add(task); db.flush()
    db.execute(text(
        "UPDATE t_aa_grade_task SET deadline_at=:deadline, deadline_updated_at=:now "
        "WHERE id=:task_id AND tenant_id=:tenant_id"
    ), {
        "deadline": deadline.replace(microsecond=0),
        "now": datetime.utcnow().replace(microsecond=0),
        "task_id": int(task.id),
        "tenant_id": TID,
    })
    db.flush()
    return task


def _recipient_ids(row) -> set[int]:
    values = row.recipient_refs_json or []
    return {int(item.get("userId")) for item in values if item.get("userId") is not None}


def _payload_items(row) -> list[dict]:
    payload = row.payload_json or {}
    return list((payload.get("variables") or {}).get("items") or [])


def test_grade_deadline_milestone_days():
    from app.modules.academic_affairs.services import academic_affairs_grade_deadline_scheduler_service as service

    now = datetime(2026, 8, 18, 0, 0, 0)
    assert service._milestone_days(now + timedelta(days=6), now) == 7
    assert service._milestone_days(now + timedelta(days=2), now) == 3
    assert service._milestone_days(now + timedelta(hours=12), now) == 1
    assert service._milestone_days(now + timedelta(days=8), now) is None
    assert service._milestone_days(now - timedelta(seconds=1), now) is None


def test_grade_deadline_scheduler_teacher_and_scoped_overdue_digest(db_mode):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import MessageEventOutbox
    from app.modules.academic_affairs.services import academic_affairs_grade_deadline_scheduler_service as service

    db = get_sessionmaker()()
    suffix = str(int(datetime.utcnow().timestamp() * 1_000_000))
    college_a, class_a = _college(db, f"截止提醒学院A-{suffix}")
    college_b, class_b = _college(db, f"截止提醒学院B-{suffix}")

    teacher_a = _user(db, f"deadline_teacher_a_{suffix}")
    teacher_b = _user(db, f"deadline_teacher_b_{suffix}")
    college_admin_a = _user(db, f"deadline_college_a_{suffix}", user_type="SCHOOL_ADMIN")
    college_admin_b = _user(db, f"deadline_college_b_{suffix}", user_type="SCHOOL_ADMIN")
    academic_admin = _user(db, f"deadline_academic_{suffix}", user_type="SCHOOL_ADMIN")

    college_role = _role(db, "COLLEGE_ADMIN")
    academic_role = _role(db, "ACADEMIC_ADMIN")
    _assign(db, college_admin_a, college_role)
    _assign(db, college_admin_b, college_role)
    _assign(db, academic_admin, academic_role)
    _college_scope(db, college_admin_a, college_a)
    _college_scope(db, college_admin_b, college_b)

    now = datetime.utcnow().replace(microsecond=0)
    upcoming = _grade_task(
        db,
        course_name=f"截止提醒课程-{suffix}",
        class_id=class_a.id,
        teacher_key=teacher_a.login_name,
        deadline=now + timedelta(days=6),
    )
    overdue_a = _grade_task(
        db,
        course_name=f"学院A逾期-{suffix}",
        class_id=class_a.id,
        teacher_key=teacher_a.login_name,
        deadline=now - timedelta(hours=2),
    )
    overdue_b = _grade_task(
        db,
        course_name=f"学院B逾期-{suffix}",
        class_id=class_b.id,
        teacher_key=teacher_b.login_name,
        deadline=now - timedelta(hours=3),
    )

    upcoming_id = int(upcoming.id)
    overdue_a_id = int(overdue_a.id)
    overdue_b_id = int(overdue_b.id)
    teacher_a_id = int(teacher_a.id)
    college_admin_a_id = int(college_admin_a.id)
    college_admin_b_id = int(college_admin_b.id)
    academic_admin_id = int(academic_admin.id)
    db.commit()
    db.close()

    set_tenant({"tenantId": str(TID)})
    try:
        first = service.scan_grade_deadlines(limit=500)
        second = service.scan_grade_deadlines(limit=500)
    finally:
        set_tenant(None)

    assert first["teacherReminders"] >= 1
    assert first["overdueTasks"] >= 2
    assert second["teacherReminders"] == 0
    assert second["overdueDigests"] == 0

    db = get_sessionmaker()()
    reminder = db.query(MessageEventOutbox).filter(
        MessageEventOutbox.tenant_id == TID,
        MessageEventOutbox.event_code == "GRADE.ENTRY_DEADLINE_REMINDER",
        MessageEventOutbox.source_biz_id == upcoming_id,
        MessageEventOutbox.is_deleted.is_(False),
    ).order_by(MessageEventOutbox.id.desc()).first()
    assert reminder is not None
    assert _recipient_ids(reminder) == {teacher_a_id}
    variables = (reminder.payload_json or {}).get("variables") or {}
    assert int(variables.get("milestoneDays")) == 7

    digests = db.query(MessageEventOutbox).filter(
        MessageEventOutbox.tenant_id == TID,
        MessageEventOutbox.event_code == "GRADE.ENTRY_OVERDUE_DIGEST",
        MessageEventOutbox.is_deleted.is_(False),
    ).all()
    by_recipient = {}
    expected_admins = {college_admin_a_id, college_admin_b_id, academic_admin_id}
    for row in digests:
        recipients = _recipient_ids(row)
        if len(recipients) == 1:
            uid = next(iter(recipients))
            if uid in expected_admins:
                by_recipient[uid] = row

    assert expected_admins.issubset(by_recipient)

    a_ids = {int(item["gradeTaskId"]) for item in _payload_items(by_recipient[college_admin_a_id])}
    b_ids = {int(item["gradeTaskId"]) for item in _payload_items(by_recipient[college_admin_b_id])}
    school_ids = {int(item["gradeTaskId"]) for item in _payload_items(by_recipient[academic_admin_id])}
    assert overdue_a_id in a_ids and overdue_b_id not in a_ids
    assert overdue_b_id in b_ids and overdue_a_id not in b_ids
    assert {overdue_a_id, overdue_b_id}.issubset(school_ids)
    db.close()
