"""C-W3 考务发布监考通知补全。

正式发布 Authority 仍唯一由 ``academic_affairs_exam_facade.publish_batch`` 持有。本 guard
只扩展 legacy ``_notify_publish(db, batch, courses)``：原学生通知原样执行，再把已经存在的
``AaExamInvigilator`` 当前行投递给可解析的真实教师 User。所有 Outbox 仍与发布状态写入处于
同一数据库事务；本模块不创建/修改监考 Assignment，也不拥有发布状态机。
"""
from __future__ import annotations

import importlib

from sqlalchemy import or_, select

from app.services.db_service import _tid
from app.services.message_event_outbox_service import emit_message_event

_INSTALLED_FLAG = "_c_w3_exam_publish_delivery_installed"


def _numeric_user_id(key: str) -> int | None:
    value = str(key or "").strip()
    if value.startswith("db-"):
        value = value[3:]
    elif value.startswith("u_"):
        value = value[2:]
    return int(value) if value.isdigit() and int(value) > 0 else None


def _resolve_teacher_users(db, teacher_keys: set[str]) -> dict[str, int]:
    """批量把正式监考 teacher_key 解析到真实 active User；无法证明身份时不猜。"""
    from app.models import User

    keys = {str(key or "").strip() for key in teacher_keys if str(key or "").strip()}
    if not keys:
        return {}
    numeric_ids = {_numeric_user_id(key) for key in keys}
    numeric_ids.discard(None)
    conditions = [User.login_name.in_(sorted(keys))]
    if numeric_ids:
        conditions.append(User.id.in_(sorted(numeric_ids)))
    users = db.scalars(select(User).where(
        User.tenant_id == _tid(),
        or_(*conditions),
        User.status == "ACTIVE",
        User.is_deleted.is_(False),
    )).all()

    by_login = {str(user.login_name or "").strip(): int(user.id) for user in users if user.login_name}
    by_id = {int(user.id): int(user.id) for user in users}
    resolved: dict[str, int] = {}
    for key in keys:
        if key in by_login:
            resolved[key] = by_login[key]
            continue
        numeric = _numeric_user_id(key)
        if numeric and numeric in by_id:
            resolved[key] = numeric
    return resolved


def emit_published_invigilation_notices(db, batch, courses) -> int:
    """给发布瞬间当前 canonical 监考行投递通知；不解析展示名作为身份。"""
    from app.models import AaExamInvigilator, AaExamRoom

    course_by_id = {int(course.id): course for course in courses or [] if getattr(course, "id", None)}
    if not course_by_id:
        return 0
    rooms = db.scalars(select(AaExamRoom).where(
        AaExamRoom.tenant_id == _tid(),
        AaExamRoom.exam_course_id.in_(sorted(course_by_id)),
        AaExamRoom.status == "ACTIVE",
        AaExamRoom.is_deleted.is_(False),
    )).all()
    room_by_id = {int(room.id): room for room in rooms}
    if not room_by_id:
        return 0
    invigilators = db.scalars(select(AaExamInvigilator).where(
        AaExamInvigilator.tenant_id == _tid(),
        AaExamInvigilator.exam_room_id.in_(sorted(room_by_id)),
        AaExamInvigilator.is_deleted.is_(False),
    )).all()
    user_by_key = _resolve_teacher_users(
        db,
        {str(row.teacher_key or "").strip() for row in invigilators},
    )

    sent = 0
    for invigilator in invigilators:
        teacher_key = str(invigilator.teacher_key or "").strip()
        user_id = user_by_key.get(teacher_key)
        room = room_by_id.get(int(invigilator.exam_room_id or 0))
        course = course_by_id.get(int(room.exam_course_id or 0)) if room else None
        if not user_id or not room or not course:
            continue
        role_label = "主监考" if str(invigilator.role or "").upper() == "CHIEF" else "副监考"
        classroom = room.classroom_text or f"考场{room.room_seq}"
        emit_message_event(
            db,
            event_code="EXAM.ARRANGED",
            source_module="academic-affairs",
            source_biz_type="exam_invigilator",
            source_biz_id=int(invigilator.id),
            recipient_refs=[{"userId": int(user_id)}],
            title=f"监考通知：{course.course_name or '考试课程'}",
            content=(
                f"{course.exam_date or ''} {course.start_time or ''}-{course.end_time or ''} "
                f"{classroom} · {role_label}"
            ).strip(),
            dedup_key=f"EXAM.ARRANGED:invigilator:{int(invigilator.id)}:batch:{int(batch.id)}",
        )
        sent += 1
    return sent


def install() -> None:
    """只包装 legacy 发布通知 hook；幂等安装，不替换 publish_batch Authority。"""
    legacy = importlib.import_module(
        "app.modules.academic_affairs.services.academic_affairs_exam_service"
    )
    if getattr(legacy, _INSTALLED_FLAG, False):
        return
    original = legacy._notify_publish

    def _notify_publish_with_invigilators(db, batch, courses):
        student_sent = int(original(db, batch, courses) or 0)
        teacher_sent = emit_published_invigilation_notices(db, batch, courses)
        return student_sent + teacher_sent

    legacy._notify_publish = _notify_publish_with_invigilators
    setattr(legacy, _INSTALLED_FLAG, True)
