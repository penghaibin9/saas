"""C15-18 relation-aware teacher schedule reads.

The schedule table keeps one ``teacher_key`` snapshot for conflict detection and
legacy display.  Once a formal TeachingClass exists, teacher-facing visibility must
instead follow ACTIVE ``AaTeachingClassTeacher`` relations and their week windows.
This adapter patches only the two teacher read entrypoints:

- explicit batch ``teacher_view``;
- current published ``teacher_schedule``.

Admins keep the mature ability to query a specified teacher. Normal teachers may
query only their own stable key. Formal relation windows clip recurrence ranges;
CO_TEACHER and week-split teachers therefore see the same course occurrence in their
own valid weeks. Tasks without a TeachingClass projection retain schedule-item
teacher_key migration fallback.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from app.core.affairs_security import _derive_keys
from app.core.exceptions import AppException, no_data_scope, not_found

from . import academic_affairs_schedule_service as schedule


def _keys(user) -> set[str]:
    return {str(value).strip() for value in (_derive_keys(user or {}) or set()) if str(value).strip()}


def _check_query_scope(user, teacher_key: str) -> None:
    role = str((user or {}).get("currentRoleCode") or "").upper()
    if role in schedule._REVIEW_ROLES:
        return
    if str(teacher_key or "").strip() not in _keys(user):
        raise no_data_scope("任课教师仅可查看本人的正式课表")


def _merge_windows(relations, default_end: int) -> tuple[list[tuple[int, int]], list[str], list[str]]:
    windows = []
    relation_ids = []
    role_types = set()
    for relation in relations or []:
        start = int(relation.start_week) if relation.start_week is not None else 1
        end = int(relation.end_week) if relation.end_week is not None else int(default_end)
        if start <= 0 or end <= 0 or end < start:
            raise AppException(
                "DATA_CONFLICT",
                "正式教师关系存在非法有效周次，教师课表无法安全投影",
                details={"teacherRelationId": str(relation.id), "startWeek": start, "endWeek": end},
                http_status=409,
            )
        windows.append((start, end))
        relation_ids.append(str(relation.id))
        role_types.add(str(relation.role_type or "PRIMARY").upper())
    windows.sort()
    merged: list[list[int]] = []
    for start, end in windows:
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged], relation_ids, sorted(role_types)


def _teacher_items(db, batch, teacher_key: str) -> list[dict]:
    from app.models import AaScheduleItem, AaTeachingClass, AaTeachingClassTeacher, AaTerm

    items = db.scalars(select(AaScheduleItem).where(
        AaScheduleItem.tenant_id == schedule._tid(),
        AaScheduleItem.batch_id == int(batch.id),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    ).order_by(AaScheduleItem.weekday, AaScheduleItem.slot_no, AaScheduleItem.id)).all()
    task_ids = sorted({int(row.task_id) for row in items if row.task_id})
    classes = []
    if task_ids:
        classes = db.scalars(select(AaTeachingClass).where(
            AaTeachingClass.tenant_id == schedule._tid(),
            AaTeachingClass.teaching_task_id.in_(task_ids),
            AaTeachingClass.is_deleted.is_(False),
        )).all()
    class_by_task = {int(row.teaching_task_id): row for row in classes}
    class_ids = sorted({int(row.id) for row in classes})
    relations_by_class = defaultdict(list)
    if class_ids:
        relations = db.scalars(select(AaTeachingClassTeacher).where(
            AaTeachingClassTeacher.tenant_id == schedule._tid(),
            AaTeachingClassTeacher.teaching_class_id.in_(class_ids),
            AaTeachingClassTeacher.teacher_key == str(teacher_key),
            AaTeachingClassTeacher.status == "ACTIVE",
            AaTeachingClassTeacher.is_deleted.is_(False),
        )).all()
        for relation in relations:
            relations_by_class[int(relation.teaching_class_id)].append(relation)

    term = db.scalars(select(AaTerm).where(
        AaTerm.id == int(batch.term_id),
        AaTerm.tenant_id == schedule._tid(),
        AaTerm.is_deleted.is_(False),
    )).first()
    default_end = int(getattr(term, "teaching_weeks", 0) or 0) or 9999

    output = []
    for item in items:
        task_id = int(item.task_id or 0)
        teaching_class = class_by_task.get(task_id) if task_id else None
        if teaching_class is not None:
            relations = relations_by_class.get(int(teaching_class.id), [])
            if not relations:
                continue
            windows, relation_ids, role_types = _merge_windows(relations, default_end)
            authority_source = "TEACHING_CLASS_TEACHER"
        else:
            if str(item.teacher_key or "").strip() != str(teacher_key):
                continue
            windows = [(1, default_end)]
            relation_ids = []
            role_types = ["MIGRATION_FALLBACK"]
            authority_source = "SCHEDULE_ITEM_MIGRATION_FALLBACK"

        start = int(item.start_week or 1)
        end = int(item.end_week or default_end)
        for w_start, w_end in windows:
            clipped_start = max(start, w_start)
            clipped_end = min(end, w_end)
            if clipped_start > clipped_end:
                continue
            dto = schedule._item_row(item)
            dto["startWeek"] = clipped_start
            dto["endWeek"] = clipped_end
            dto["teacherKey"] = str(teacher_key)
            dto["teacherAuthoritySource"] = authority_source
            dto["teacherRelationIds"] = relation_ids
            dto["teacherRoleTypes"] = role_types
            dto["teachingClassId"] = str(teaching_class.id) if teaching_class else None
            output.append(dto)

    output.sort(key=lambda row: (
        int(row.get("weekday") or 0),
        int(row.get("slotNo") or 0),
        int(row.get("startWeek") or 0),
        int(row.get("scheduleItemId") or row.get("itemId") or 0),
    ))
    return output


def teacher_view(batch_id, user, teacher_key):
    """Explicit batch teacher view, relation-first and teacher-self scoped."""
    from app.models import AaScheduleBatch

    key = str(teacher_key or "").strip()
    if not key:
        raise AppException("VALIDATION_ERROR", "teacherKey 必填")
    _check_query_scope(user, key)
    with schedule.session() as db:
        batch = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == int(batch_id),
            AaScheduleBatch.tenant_id == schedule._tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("课表批次不存在")
        return {
            "items": _teacher_items(db, batch, key),
            "batchId": str(batch.id),
            "teacherKey": key,
            "teacherAuthorityPolicy": "TEACHING_CLASS_TEACHER_BY_WEEK",
        }


teacher_view._schedule_teacher_relation_guard = True


def teacher_schedule(user, teacher_key, term_id=None, week=None) -> dict:
    """Current published teacher schedule with relation-week clipping."""
    key = str(teacher_key or "").strip()
    if not key:
        raise AppException("VALIDATION_ERROR", "teacherKey 必填")
    _check_query_scope(user, key)
    with schedule.session() as db:
        batch = schedule._current_published_batch(db, term_id)
        if not batch:
            return {
                "items": [], "batchId": None, "weeklyHours": 0,
                "teacherKey": key,
                "teacherAuthorityPolicy": "TEACHING_CLASS_TEACHER_BY_WEEK",
                "note": "本学期暂无授课安排",
            }
        all_rows = _teacher_items(db, batch, key)
        rows = [row for row in all_rows if schedule._week_in_range(row, week)]
        return {
            "items": rows,
            "batchId": str(batch.id),
            "weeklyHours": len(all_rows),
            "teacherKey": key,
            "teacherAuthorityPolicy": "TEACHING_CLASS_TEACHER_BY_WEEK",
            "note": "正式教师关系周窗投影；weeklyHours 仅保留旧课表条目参考，不作为薪酬工时",
        }


teacher_schedule._schedule_teacher_relation_guard = True


def install() -> None:
    for name, replacement in (("teacher_view", teacher_view), ("teacher_schedule", teacher_schedule)):
        original_name = f"_teacher_relation_guard_original_{name}"
        if not hasattr(schedule, original_name):
            setattr(schedule, original_name, getattr(schedule, name))
        setattr(schedule, name, replacement)
