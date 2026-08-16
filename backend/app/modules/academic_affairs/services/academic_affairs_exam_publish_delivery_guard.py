"""C-W3 考务发布 / 监考改派消息补全。

正式发布、监考 Assignment 与改派状态机仍唯一由 ``academic_affairs_exam_facade`` 持有。
本 guard 只安装两个成熟事务内 hook：

1. 扩展 legacy ``_notify_publish(db, batch, courses)``：原学生通知原样执行，再给当前
   ``AaExamInvigilator`` 对应的真实教师 User 投递监考通知；
2. 扩展 legacy ``_audit(...)`` 的 ``EXAM_INVIGILATOR_CHANGE`` 单一动作：在 canonical
   ``change_invigilator`` 提交前再次要求批次已经 PUBLISHED/FINISHED，并在同一事务给旧教师
   发“原安排已调整”、给新教师发“请接替监考”。任何门禁/Outbox 失败都会让原改派整体回滚。

本模块绝不创建/修改监考 Assignment，不提交事务，也不替换 publish/change/assign Authority。
"""
from __future__ import annotations

import hashlib
import importlib
from datetime import datetime

from sqlalchemy import or_, select

from app.core.exceptions import AppException
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


def _invigilation_facts(db, invigilator_id: int):
    from app.models import AaExamBatch, AaExamCourse, AaExamInvigilator, AaExamRoom

    invigilator = db.scalars(select(AaExamInvigilator).where(
        AaExamInvigilator.id == int(invigilator_id),
        AaExamInvigilator.tenant_id == _tid(),
        AaExamInvigilator.is_deleted.is_(False),
    )).first()
    if not invigilator:
        raise AppException("DATA_CONFLICT", "监考改派后的正式安排不存在", http_status=409)
    room = db.scalars(select(AaExamRoom).where(
        AaExamRoom.id == int(invigilator.exam_room_id),
        AaExamRoom.tenant_id == _tid(),
        AaExamRoom.status == "ACTIVE",
        AaExamRoom.is_deleted.is_(False),
    )).first()
    if not room:
        raise AppException("DATA_CONFLICT", "监考改派对应考场不是有效考场", http_status=409)
    course = db.scalars(select(AaExamCourse).where(
        AaExamCourse.id == int(room.exam_course_id),
        AaExamCourse.tenant_id == _tid(),
        AaExamCourse.status == "CONFIRMED",
        AaExamCourse.is_deleted.is_(False),
    )).first()
    if not course:
        raise AppException("DATA_CONFLICT", "监考改派对应考试课程不是已确认课程", http_status=409)
    batch = db.scalars(select(AaExamBatch).where(
        AaExamBatch.id == int(course.batch_id),
        AaExamBatch.tenant_id == _tid(),
        AaExamBatch.is_deleted.is_(False),
    )).first()
    if not batch:
        raise AppException("DATA_CONFLICT", "监考改派对应考试批次不存在", http_status=409)
    if str(batch.status or "").upper() not in {"PUBLISHED", "FINISHED"}:
        raise AppException(
            "DATA_CONFLICT",
            "监考改派仅允许已发布/已结束考试批次；发布前请使用正常监考编排入口",
            http_status=409,
        )
    return invigilator, room, course, batch


def _delivery_marker(invigilator_id: int, before: str, after: str, detail: str) -> str:
    """事务内一次改派事件标识；回滚时 Outbox 同步回滚，成功请求不会二次执行同一 old-key。"""
    raw = (
        f"{int(invigilator_id)}|{before}|{after}|{detail}|"
        f"{datetime.utcnow().isoformat(timespec='microseconds')}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _change_notice_content(course, room, role: str, suffix: str) -> str:
    role_label = "主监考" if str(role or "").upper() == "CHIEF" else "副监考"
    classroom = room.classroom_text or f"考场{room.room_seq}"
    return (
        f"{course.exam_date or ''} {course.start_time or ''}-{course.end_time or ''} "
        f"{classroom} · {role_label} · {suffix}"
    ).strip()


def emit_invigilation_change_notices(
    db,
    invigilator_id: int,
    *,
    before: str,
    after: str,
    detail: str,
) -> int:
    """在 canonical 改派事务提交前投递新旧教师通知，并同时执行正式状态门禁。"""
    invigilator, room, course, batch = _invigilation_facts(db, int(invigilator_id))
    old_key = str(before or "").split(":", 1)[0].strip()
    new_key = str(invigilator.teacher_key or "").strip()
    users = _resolve_teacher_users(db, {old_key, new_key})
    marker = _delivery_marker(invigilator.id, before, after, detail)
    sent = 0

    old_user_id = users.get(old_key)
    if old_user_id and old_key != new_key:
        emit_message_event(
            db,
            event_code="EXAM.ARRANGED",
            source_module="academic-affairs",
            source_biz_type="exam_invigilator_change",
            source_biz_id=int(invigilator.id),
            recipient_refs=[{"userId": int(old_user_id)}],
            title=f"监考调整：{course.course_name or '考试课程'}",
            content=_change_notice_content(course, room, invigilator.role, "您原来的监考安排已调整"),
            dedup_key=f"EXAM.ARRANGED:change:{marker}:old",
        )
        sent += 1

    new_user_id = users.get(new_key)
    if new_user_id:
        emit_message_event(
            db,
            event_code="EXAM.ARRANGED",
            source_module="academic-affairs",
            source_biz_type="exam_invigilator_change",
            source_biz_id=int(invigilator.id),
            recipient_refs=[{"userId": int(new_user_id)}],
            title=f"监考调整：请接替 {course.course_name or '考试课程'}",
            content=_change_notice_content(course, room, invigilator.role, "请按最新安排到场监考"),
            dedup_key=f"EXAM.ARRANGED:change:{marker}:new",
        )
        sent += 1
    return sent


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
    """包装发布通知与单一监考改派审计 hook；幂等安装，不替换业务 Authority。"""
    legacy = importlib.import_module(
        "app.modules.academic_affairs.services.academic_affairs_exam_service"
    )
    if getattr(legacy, _INSTALLED_FLAG, False):
        return
    original_notify = legacy._notify_publish
    original_audit = legacy._audit

    def _notify_publish_with_invigilators(db, batch, courses):
        student_sent = int(original_notify(db, batch, courses) or 0)
        teacher_sent = emit_published_invigilation_notices(db, batch, courses)
        return student_sent + teacher_sent

    def _audit_with_invigilation_delivery(db, biz_type, biz_id, action, detail="", before="", after=""):
        if action == "EXAM_INVIGILATOR_CHANGE":
            # Validate before the canonical function reaches commit. The assignment row has already
            # been changed in this SQLAlchemy transaction; raising here rolls the whole mutation back.
            _invigilation_facts(db, int(biz_id))
        original_audit(db, biz_type, biz_id, action, detail, before, after)
        if action == "EXAM_INVIGILATOR_CHANGE":
            emit_invigilation_change_notices(
                db,
                int(biz_id),
                before=str(before or ""),
                after=str(after or ""),
                detail=str(detail or ""),
            )

    legacy._notify_publish = _notify_publish_with_invigilators
    legacy._audit = _audit_with_invigilation_delivery
    setattr(legacy, _INSTALLED_FLAG, True)
