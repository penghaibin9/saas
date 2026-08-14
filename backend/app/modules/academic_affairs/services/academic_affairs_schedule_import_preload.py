"""排课批量导入的定向预载上下文。

只替换 `_apply_import_rows()` 内重复的数据读取方式；教师/班级/教室冲突仍调用
`academic_affairs_schedule_service._detect_conflict()` 唯一实现，手工单笔排课不使用本上下文。
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import and_, func, or_, select

from . import academic_affairs_schedule_service as _base


def _value(source, key, default=None):
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _PreloadedScalarDB:
    """给既有只读 helper 提供 `scalars(...).all()`，让规则实现本身保持唯一。"""

    def __init__(self, rows):
        self._rows = rows

    def scalars(self, _statement):
        return _ScalarResult(self._rows)


class ScheduleImportPreload:
    def __init__(
        self,
        *,
        allowed_batch_ids,
        teaching_weeks,
        enabled_slots,
        tasks,
        classrooms,
        task_counts,
        conflict_rows,
    ):
        self.allowed_batch_ids = tuple(int(v) for v in allowed_batch_ids)
        self.teaching_weeks = int(teaching_weeks)
        self.enabled_slots = tuple(int(v) for v in enabled_slots)
        self._tasks = list(tasks)
        self._task_by_id = {int(row.id): row for row in self._tasks}
        self._classrooms = list(classrooms)
        self._classroom_by_id = {int(row.id): row for row in self._classrooms}
        self._task_counts = {int(k): int(v) for k, v in task_counts.items()}
        buckets = defaultdict(list)
        for row in conflict_rows:
            buckets[(int(row.weekday), int(row.slot_no))].append(row)
        self._conflict_rows = buckets

    def task_by_id(self, task_id: int):
        return self._task_by_id.get(int(task_id))

    def task_matches(self, course_name: str, teacher_key: str, class_id):
        matches = []
        class_id_int = int(class_id) if class_id not in (None, "") else None
        for row in self._tasks:
            if row.course_name != course_name:
                continue
            if teacher_key and row.teacher_key != teacher_key:
                continue
            if class_id_int is not None and (
                row.class_id is None or int(row.class_id) != class_id_int
            ):
                continue
            matches.append(row)
            if len(matches) >= 2:
                break
        return matches

    def resolve_classroom_id(self, text):
        return _base._resolve_classroom_id(_PreloadedScalarDB(self._classrooms), text)

    def classroom_by_id(self, classroom_id):
        if classroom_id in (None, ""):
            return None
        return self._classroom_by_id.get(int(classroom_id))

    def scheduled_count(self, task_id: int) -> int:
        return int(self._task_counts.get(int(task_id), 0))

    def detect_conflict(
        self,
        *,
        batch_id,
        weekday,
        slot_no,
        start_week,
        end_week,
        parity,
        teacher_key,
        class_id,
        classroom,
        exclude_id=None,
    ):
        rows = self._conflict_rows.get((int(weekday), int(slot_no)), ())
        return _base._detect_conflict(
            _PreloadedScalarDB(rows),
            batch_id,
            weekday,
            slot_no,
            start_week,
            end_week,
            parity,
            teacher_key,
            class_id,
            classroom,
            exclude_id=exclude_id,
        )

    def record_item(self, item) -> None:
        if item.task_id is not None:
            task_id = int(item.task_id)
            self._task_counts[task_id] = self._task_counts.get(task_id, 0) + 1
        self._conflict_rows[(int(item.weekday), int(item.slot_no))].append(item)


def build_preload(
    db,
    batch,
    items,
    *,
    allowed_batch_ids,
    teaching_weeks,
    enabled_slots,
) -> ScheduleImportPreload:
    """只预载本批输入会触达的数据，避免把全租户任务/教室 materialize 到 Python。"""
    from app.models import AaClassroom, AaScheduleItem, AaTeachingTask

    direct_task_ids: set[int] = set()
    match_keys: set[tuple[str, str, int | None]] = set()
    classroom_texts: set[str] = set()
    coordinates: set[tuple[int, int]] = set()

    for source in items or []:
        task_id = _value(source, "taskId")
        if task_id not in (None, ""):
            try:
                direct_task_ids.add(int(task_id))
            except (TypeError, ValueError):
                pass
        else:
            course_name = str(_value(source, "courseName") or "").strip()
            teacher_key = str(_value(source, "teacherKey") or "").strip()
            class_id = _value(source, "classId")
            if course_name and (teacher_key or class_id not in (None, "")):
                try:
                    class_id_int = int(class_id) if class_id not in (None, "") else None
                except (TypeError, ValueError):
                    class_id_int = None
                match_keys.add((course_name, teacher_key, class_id_int))

        classroom_text = str(_value(source, "classroom") or "").strip()
        if classroom_text:
            classroom_texts.add(classroom_text)

        try:
            weekday = int(_value(source, "weekday"))
            slot_no = int(_value(source, "slotNo"))
        except (TypeError, ValueError):
            continue
        if 1 <= weekday <= 7 and slot_no > 0:
            coordinates.add((weekday, slot_no))

    task_conditions = []
    if direct_task_ids:
        task_conditions.append(AaTeachingTask.id.in_(sorted(direct_task_ids)))
    for course_name, teacher_key, class_id in sorted(
        match_keys, key=lambda item: (item[0], item[1], item[2] or -1)
    ):
        parts = [AaTeachingTask.course_name == course_name]
        if teacher_key:
            parts.append(AaTeachingTask.teacher_key == teacher_key)
        if class_id is not None:
            parts.append(AaTeachingTask.class_id == class_id)
        task_conditions.append(and_(*parts))

    tasks = []
    if task_conditions:
        tasks = db.scalars(
            select(AaTeachingTask).where(
                AaTeachingTask.tenant_id == _base._tid(),
                AaTeachingTask.batch_id.in_(list(allowed_batch_ids) or [-1]),
                AaTeachingTask.status == "READY",
                AaTeachingTask.is_deleted.is_(False),
                or_(*task_conditions),
            )
        ).all()

    classrooms = []
    if classroom_texts:
        labels = sorted(classroom_texts)
        stripped_name = func.trim(func.coalesce(AaClassroom.room_name, ""))
        fallback_label = func.concat(
            func.coalesce(AaClassroom.building_name, ""),
            func.coalesce(AaClassroom.room_code, ""),
        )
        classrooms = db.scalars(
            select(AaClassroom).where(
                AaClassroom.tenant_id == _base._tid(),
                AaClassroom.is_deleted.is_(False),
                or_(
                    stripped_name.in_(labels),
                    and_(stripped_name == "", fallback_label.in_(labels)),
                ),
            )
        ).all()

    task_counts = {}
    task_ids = sorted({int(row.id) for row in tasks})
    if task_ids:
        count_rows = db.execute(
            select(AaScheduleItem.task_id, func.count(AaScheduleItem.id))
            .where(
                AaScheduleItem.tenant_id == _base._tid(),
                AaScheduleItem.batch_id == int(batch.id),
                AaScheduleItem.task_id.in_(task_ids),
                AaScheduleItem.status == "EFFECTIVE",
                AaScheduleItem.is_deleted.is_(False),
            )
            .group_by(AaScheduleItem.task_id)
        ).all()
        task_counts = {int(task_id): int(count) for task_id, count in count_rows}

    conflict_rows = []
    if coordinates:
        coordinate_filter = or_(*[
            and_(AaScheduleItem.weekday == weekday, AaScheduleItem.slot_no == slot_no)
            for weekday, slot_no in sorted(coordinates)
        ])
        conflict_rows = db.scalars(
            select(AaScheduleItem).where(
                AaScheduleItem.tenant_id == _base._tid(),
                AaScheduleItem.batch_id == int(batch.id),
                coordinate_filter,
                AaScheduleItem.status == "EFFECTIVE",
                AaScheduleItem.is_deleted.is_(False),
            )
        ).all()

    return ScheduleImportPreload(
        allowed_batch_ids=allowed_batch_ids,
        teaching_weeks=teaching_weeks,
        enabled_slots=enabled_slots,
        tasks=tasks,
        classrooms=classrooms,
        task_counts=task_counts,
        conflict_rows=conflict_rows,
    )
