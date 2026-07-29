"""课表手工、导入、调整、预发布和发布最终公开入口。"""
from __future__ import annotations

import importlib
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found

from . import academic_affairs_schedule_gate_service as gate_service
from . import academic_affairs_schedule_policy as policy

_base = importlib.import_module(
    ".academic_affairs_schedule_service",
    package=__package__,
)


def __getattr__(name):
    return getattr(_base, name)


def _value(source, key, default=None):
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def sanitize_import_rows(rows: list[dict]) -> list[dict]:
    """只做公式注入转义；周次由正式学期/教学任务决定，不再硬编码 1-18。"""
    output = []
    for source in rows or []:
        row = dict(source)
        for key in ("courseName", "teacherName", "teacherKey", "className", "classroom"):
            value = row.get(key)
            if isinstance(value, str) and value[:1] in _base._FORMULA_PREFIXES:
                row[key] = "'" + value
        row["weekParity"] = str(row.get("weekParity") or "ALL").strip().upper()
        output.append(row)
    return output


def _load_batch(db, batch_id, *, writable=True, lock=True):
    from app.models import AaScheduleBatch

    query = db.query(AaScheduleBatch).filter(
        AaScheduleBatch.id == int(batch_id),
        AaScheduleBatch.tenant_id == _base._tid(),
        AaScheduleBatch.is_deleted.is_(False),
    )
    if lock:
        query = query.with_for_update()
    batch = query.first()
    if not batch:
        raise not_found("课表批次不存在")
    policy.resolve_scope(
        db,
        term_id=batch.term_id,
        batch_id=batch.id,
        writable=writable,
    )
    return batch


def _task_batch_ids(db, batch) -> list[int]:
    from app.models import AaTeachingTaskBatch

    query = db.query(AaTeachingTaskBatch).filter(
        AaTeachingTaskBatch.tenant_id == _base._tid(),
        AaTeachingTaskBatch.term_id == int(batch.term_id),
        AaTeachingTaskBatch.status == "APPROVED",
        AaTeachingTaskBatch.is_deleted.is_(False),
    )
    if getattr(batch, "college_id", None):
        query = query.filter(AaTeachingTaskBatch.college_id == int(batch.college_id))
    return [int(row.id) for row in query.all()]


def _resolve_task(db, batch, source):
    from app.models import AaTeachingTask

    allowed_batches = _task_batch_ids(db, batch)
    task_id = _value(source, "taskId")
    query = db.query(AaTeachingTask).filter(
        AaTeachingTask.tenant_id == _base._tid(),
        AaTeachingTask.batch_id.in_(allowed_batches or [-1]),
        AaTeachingTask.status == "READY",
        AaTeachingTask.is_deleted.is_(False),
    )
    if task_id not in (None, ""):
        task = query.filter(AaTeachingTask.id == int(task_id)).first()
        if not task:
            raise AppException(
                "DATA_CONFLICT",
                "教学任务不存在、未终审 READY，或不属于该课表批次学期",
                details={"taskId": str(task_id), "termId": str(batch.term_id)},
                http_status=409,
            )
        return task

    course_name = str(_value(source, "courseName") or "").strip()
    teacher_key = str(_value(source, "teacherKey") or "").strip()
    class_id = _value(source, "classId")
    if not course_name or (not teacher_key and class_id in (None, "")):
        raise AppException(
            "VALIDATION_ERROR",
            "未填写教学任务ID时，至少需要课程名称和教师工号或班级ID用于唯一匹配",
        )
    query = query.filter(AaTeachingTask.course_name == course_name)
    if teacher_key:
        query = query.filter(AaTeachingTask.teacher_key == teacher_key)
    if class_id not in (None, ""):
        query = query.filter(AaTeachingTask.class_id == int(class_id))
    matches = query.limit(2).all()
    if not matches:
        raise AppException(
            "DATA_CONFLICT",
            "未匹配到同学期 READY 教学任务，请先核对教学任务ID",
            http_status=409,
        )
    if len(matches) > 1:
        raise AppException(
            "DATA_CONFLICT",
            "匹配到多个教学任务，必须填写教学任务ID",
            details={"taskIds": [str(row.id) for row in matches]},
            http_status=409,
        )
    return matches[0]


def _coordinate(db, batch, task, source):
    _term, teaching_weeks = policy.term_bounds(db, int(batch.term_id))
    enabled_slots = policy.enabled_slots(db)
    weekday = int(_value(source, "weekday"))
    slot_no = int(_value(source, "slotNo"))
    parity = str(_value(source, "weekParity", "ALL") or "ALL").strip().upper()
    task_start = int(task.start_week or 1)
    task_end = int(task.end_week or teaching_weeks)
    start_week = int(_value(source, "startWeek", task_start) or task_start)
    end_week = int(_value(source, "endWeek", task_end) or task_end)
    if weekday < 1 or weekday > 7:
        raise AppException("VALIDATION_ERROR", "星期只能为 1 至 7")
    if slot_no not in enabled_slots:
        raise AppException("VALIDATION_ERROR", f"节次 {slot_no} 未在学校作息中启用")
    if parity not in _base.PARITIES:
        raise AppException("VALIDATION_ERROR", "单双周仅支持 ALL/ODD/EVEN")
    if (
        task_start < 1
        or task_end < task_start
        or task_end > teaching_weeks
    ):
        raise AppException(
            "DATA_CONFLICT",
            "教学任务起止周配置无效，请先修复教学任务",
            details={
                "taskId": str(task.id),
                "startWeek": task.start_week,
                "endWeek": task.end_week,
                "teachingWeeks": teaching_weeks,
            },
            http_status=409,
        )
    if (
        start_week < task_start
        or end_week > task_end
        or end_week < start_week
    ):
        raise AppException(
            "VALIDATION_ERROR",
            f"排课周次必须位于教学任务的 {task_start}-{task_end} 周范围内",
        )
    return weekday, slot_no, start_week, end_week, parity


def _classroom(db, task, text):
    from app.models import AaClassroom

    classroom_text = str(text or "").strip() or None
    classroom_id = _base._resolve_classroom_id(db, classroom_text)
    room = None
    if classroom_id:
        room = db.query(AaClassroom).filter(
            AaClassroom.id == int(classroom_id),
            AaClassroom.tenant_id == _base._tid(),
            AaClassroom.is_deleted.is_(False),
        ).first()
        if not room or room.status != "AVAILABLE":
            raise AppException("DATA_CONFLICT", "所选教室当前不可用", http_status=409)
        if task.required_room_type and room.room_type != task.required_room_type:
            raise AppException(
                "DATA_CONFLICT",
                f"教学任务要求 {task.required_room_type} 类型教室，当前教室类型为 {room.room_type}",
                http_status=409,
            )
        if task.expected_students and int(room.capacity or 0) < int(task.expected_students):
            raise AppException(
                "DATA_CONFLICT",
                f"教室容量 {room.capacity or 0} 小于预计上课人数 {task.expected_students}",
                http_status=409,
            )
        classroom_text = (room.room_name or "").strip() or f"{room.building_name}{room.room_code}"
    elif classroom_text and (task.required_room_type or task.expected_students):
        raise AppException(
            "DATA_CONFLICT",
            "该教室未匹配到教室字典，无法核验类型和容量",
            http_status=409,
        )
    return classroom_id, classroom_text


def _ensure_task_capacity(db, batch, task, increment=1, exclude_item_id=None):
    from app.models import AaScheduleItem

    expected = int(task.weekly_hours or 0)
    if expected <= 0:
        raise AppException("DATA_CONFLICT", "教学任务未配置有效周学时", http_status=409)
    query = db.query(AaScheduleItem).filter(
        AaScheduleItem.tenant_id == _base._tid(),
        AaScheduleItem.batch_id == int(batch.id),
        AaScheduleItem.task_id == int(task.id),
        AaScheduleItem.status == "EFFECTIVE",
        AaScheduleItem.is_deleted.is_(False),
    )
    if exclude_item_id:
        query = query.filter(AaScheduleItem.id != int(exclude_item_id))
    actual = query.count()
    if actual + int(increment) > expected:
        raise AppException(
            "DATA_CONFLICT",
            f"该教学任务周学时为 {expected}，当前已排 {actual} 节，继续排课将超排",
            details={"taskId": str(task.id), "weeklyHours": expected, "scheduled": actual},
            http_status=409,
        )


def _build_item(db, batch, task, source, *, item_source):
    from app.models import AaScheduleItem

    weekday, slot_no, start_week, end_week, parity = _coordinate(db, batch, task, source)
    _ensure_task_capacity(db, batch, task)
    classroom_id, classroom_text = _classroom(db, task, _value(source, "classroom"))
    conflict = _base._detect_conflict(
        db,
        batch.id,
        weekday,
        slot_no,
        start_week,
        end_week,
        parity,
        task.teacher_key,
        task.class_id,
        classroom_text,
    )
    if conflict:
        raise AppException(
            "DATA_CONFLICT",
            f"排课冲突（{conflict['type']}）：{conflict['detail']}",
            details=conflict,
            http_status=409,
        )
    return AaScheduleItem(
        tenant_id=_base._tid(),
        batch_id=batch.id,
        task_id=task.id,
        course_id=task.course_id,
        course_name=task.course_name,
        class_id=task.class_id,
        class_name=task.teaching_class_name,
        teacher_key=task.teacher_key,
        teacher_name=task.teacher_name,
        weekday=weekday,
        slot_no=slot_no,
        start_week=start_week,
        end_week=end_week,
        week_parity=parity,
        classroom_id=classroom_id,
        classroom_text=classroom_text,
        status="EFFECTIVE",
        source=item_source,
    )


def create_batch(body, user) -> dict:
    from app.models import AaScheduleBatch

    with _base.session() as db:
        term, _unused, _weeks = policy.resolve_scope(
            db,
            term_id=body.termId,
            writable=True,
        )
        name = str(getattr(body, "batchName", None) or f"{term.term_name or term.year_code}课表").strip()
        duplicate = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.tenant_id == _base._tid(),
            AaScheduleBatch.term_id == term.id,
            AaScheduleBatch.batch_name == name,
            AaScheduleBatch.is_deleted.is_(False),
        ).first()
        if duplicate:
            raise AppException("DATA_CONFLICT", "同学期已存在同名课表批次", http_status=409)
        row = AaScheduleBatch(
            tenant_id=_base._tid(),
            term_id=term.id,
            batch_name=name,
            college_id=(int(body.collegeId) if getattr(body, "collegeId", None) else None),
            status="DRAFT",
        )
        db.add(row)
        db.flush()
        _base._audit(db, "AA_SCHEDULE_BATCH", row.id, "CREATE", f"termId={term.id}")
        db.commit()
        return {"batchId": str(row.id), "batchName": row.batch_name, "status": row.status}


def add_item(batch_id, user, body) -> dict:
    with _base.session() as db:
        batch = _load_batch(db, batch_id)
        if batch.status not in {"DRAFT", "PRE_PUBLISHED"}:
            raise AppException("DATA_CONFLICT", "已发布课表不可直接修改", http_status=409)
        task = _resolve_task(db, batch, body)
        item = _build_item(db, batch, task, body, item_source="MANUAL")
        db.add(item)
        db.flush()
        reset = batch.status == "PRE_PUBLISHED"
        if reset:
            batch.status = "DRAFT"
        _base._audit(
            db,
            "AA_SCHEDULE",
            item.id,
            "ADD_ITEM",
            f"taskId={task.id};周{item.weekday}第{item.slot_no}节;prePublishReset={reset}",
        )
        db.commit()
        return {**_base._item_row(item), "prePublishReset": reset}


def import_items(batch_id, user, items) -> dict:
    imported = 0
    errors = []
    reset = False
    with _base.session() as db:
        batch = _load_batch(db, batch_id)
        if batch.status not in {"DRAFT", "PRE_PUBLISHED"}:
            raise AppException("DATA_CONFLICT", "已发布课表不可导入", http_status=409)
        for index, source in enumerate(items or [], start=1):
            try:
                task = _resolve_task(db, batch, source)
                item = _build_item(db, batch, task, source, item_source="IMPORT")
                db.add(item)
                db.flush()
                imported += 1
            except AppException as exc:
                errors.append({
                    "row": index,
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                })
        if imported and batch.status == "PRE_PUBLISHED":
            batch.status = "DRAFT"
            reset = True
        _base._audit(
            db,
            "AA_SCHEDULE_BATCH",
            batch.id,
            "IMPORT",
            f"imported={imported};errors={len(errors)};prePublishReset={reset}",
        )
        db.commit()
    return {
        "batchId": str(batch_id),
        "imported": imported,
        "conflicts": errors,
        "errors": errors,
        "prePublishReset": reset,
    }


def move_item(item_id, user, body) -> dict:
    from app.models import AaScheduleItem

    with _base.session() as db:
        item = db.query(AaScheduleItem).filter(
            AaScheduleItem.id == int(item_id),
            AaScheduleItem.tenant_id == _base._tid(),
            AaScheduleItem.is_deleted.is_(False),
        ).with_for_update().first()
        if not item:
            raise not_found("排课条目不存在")
        batch = _load_batch(db, item.batch_id)
        if batch.status not in {"DRAFT", "PRE_PUBLISHED"}:
            raise AppException("DATA_CONFLICT", "已发布课表不可直接改动", http_status=409)
        task = _resolve_task(db, batch, {"taskId": item.task_id})
        source = {
            "weekday": body.weekday,
            "slotNo": body.slotNo,
            "startWeek": item.start_week,
            "endWeek": item.end_week,
            "weekParity": item.week_parity,
            "classroom": item.classroom_text,
        }
        weekday, slot_no, start_week, end_week, parity = _coordinate(db, batch, task, source)
        conflict = _base._detect_conflict(
            db,
            batch.id,
            weekday,
            slot_no,
            start_week,
            end_week,
            parity,
            task.teacher_key,
            task.class_id,
            item.classroom_text,
            exclude_id=item.id,
        )
        if conflict:
            raise AppException(
                "DATA_CONFLICT",
                f"排课冲突（{conflict['type']}）：{conflict['detail']}",
                details=conflict,
                http_status=409,
            )
        item.weekday = weekday
        item.slot_no = slot_no
        if item.source == "AUTO":
            item.source = "MANUAL"
        reset = batch.status == "PRE_PUBLISHED"
        if reset:
            batch.status = "DRAFT"
        _base._audit(
            db,
            "AA_SCHEDULE",
            item.id,
            "MOVE_ITEM",
            f"周{weekday}第{slot_no}节;prePublishReset={reset}",
        )
        db.commit()
        return {**_base._item_row(item), "prePublishReset": reset}


def adjust_item(batch_id, item_id, user, weekday, slot_no, classroom, week_parity="ALL") -> dict:
    from app.models import AaScheduleItem

    with _base.session() as db:
        batch = _load_batch(db, batch_id)
        if batch.status not in {"DRAFT", "PRE_PUBLISHED"}:
            raise AppException("DATA_CONFLICT", "已发布课表不可直接改动", http_status=409)
        item = db.query(AaScheduleItem).filter(
            AaScheduleItem.id == int(item_id),
            AaScheduleItem.batch_id == batch.id,
            AaScheduleItem.tenant_id == _base._tid(),
            AaScheduleItem.is_deleted.is_(False),
        ).with_for_update().first()
        if not item:
            raise not_found("排课条目不存在")
        task = _resolve_task(db, batch, {"taskId": item.task_id})
        source = {
            "weekday": weekday,
            "slotNo": slot_no,
            "startWeek": item.start_week,
            "endWeek": item.end_week,
            "weekParity": week_parity,
            "classroom": classroom,
        }
        new_weekday, new_slot, start_week, end_week, parity = _coordinate(db, batch, task, source)
        classroom_id, classroom_text = _classroom(db, task, classroom)
        conflict = _base._detect_conflict(
            db,
            batch.id,
            new_weekday,
            new_slot,
            start_week,
            end_week,
            parity,
            task.teacher_key,
            task.class_id,
            classroom_text,
            exclude_id=item.id,
        )
        if conflict:
            raise AppException(
                "DATA_CONFLICT",
                f"排课冲突（{conflict['type']}）：{conflict['detail']}",
                details=conflict,
                http_status=409,
            )
        item.weekday = new_weekday
        item.slot_no = new_slot
        item.week_parity = parity
        item.classroom_id = classroom_id
        item.classroom_text = classroom_text
        item.objection_status = None
        item.objection_reason = None
        if item.source == "AUTO":
            item.source = "MANUAL"
        reset = batch.status == "PRE_PUBLISHED"
        if reset:
            batch.status = "DRAFT"
        _base._audit(
            db,
            "AA_SCHEDULE",
            item.id,
            "ADJUST_ITEM",
            f"周{new_weekday}第{new_slot}节;prePublishReset={reset}",
        )
        db.commit()
        return {**_base._item_row(item), "prePublishReset": reset}


def _pending_objections(db, batch_id) -> int:
    from app.models import AaScheduleItem

    return db.query(AaScheduleItem).filter(
        AaScheduleItem.tenant_id == _base._tid(),
        AaScheduleItem.batch_id == int(batch_id),
        AaScheduleItem.objection_status == "PENDING",
        AaScheduleItem.is_deleted.is_(False),
    ).count()


def pre_publish(batch_id, user) -> dict:
    with _base.session() as db:
        batch = _load_batch(db, batch_id)
        if batch.status != "DRAFT":
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅 DRAFT 批次可预发布", http_status=409)
        pending_objections = _pending_objections(db, batch.id)
        if pending_objections:
            raise AppException(
                "DATA_CONFLICT",
                f"仍有 {pending_objections} 条教师异议未处理，不能预发布",
                http_status=409,
            )
        gate = gate_service.require_publishable(db, batch)
        batch.status = "PRE_PUBLISHED"
        _base._audit(
            db,
            "AA_SCHEDULE_BATCH",
            batch.id,
            "PRE_PUBLISH",
            f"tasks={gate['totalTasks']};items={gate['scheduledSessions']};soft={gate['softConflicts']}",
        )
        db.commit()
        return {
            "batchId": str(batch.id),
            "status": "PRE_PUBLISHED",
            "gate": gate,
        }


def publish(batch_id, user) -> dict:
    from app.models import AaScheduleItem, AaSchedulePublish, User
    from app.services.message_event_outbox_service import emit_receiver_notice

    with _base.session() as db:
        batch = _load_batch(db, batch_id)
        if batch.status == "PUBLISHED":
            last = db.query(AaSchedulePublish).filter(
                AaSchedulePublish.tenant_id == _base._tid(),
                AaSchedulePublish.batch_id == batch.id,
                AaSchedulePublish.action == "PUBLISH",
                AaSchedulePublish.is_deleted.is_(False),
            ).order_by(AaSchedulePublish.id.desc()).first()
            return {
                "batchId": str(batch.id),
                "status": "PUBLISHED",
                "notified": int(last.notified_count or 0) if last else 0,
                "idempotent": True,
            }
        if batch.status != "PRE_PUBLISHED":
            raise AppException(
                "APPROVAL_VERSION_CONFLICT",
                "课表必须先通过预发布检查，禁止从 DRAFT 直接正式发布",
                http_status=409,
            )
        pending_objections = _pending_objections(db, batch.id)
        if pending_objections:
            raise AppException(
                "DATA_CONFLICT",
                f"仍有 {pending_objections} 条教师异议未处理，不能发布",
                http_status=409,
            )
        gate = gate_service.require_publishable(db, batch)
        batch.status = "PUBLISHED"
        batch.publish_at = datetime.utcnow()

        teacher_keys = {
            row.teacher_key for row in db.query(AaScheduleItem).filter(
                AaScheduleItem.tenant_id == _base._tid(),
                AaScheduleItem.batch_id == batch.id,
                AaScheduleItem.status == "EFFECTIVE",
                AaScheduleItem.is_deleted.is_(False),
            ).all() if row.teacher_key
        }
        notified = 0
        for teacher_key in sorted(teacher_keys):
            account = db.query(User).filter(
                User.tenant_id == _base._tid(),
                User.login_name == teacher_key,
                User.is_deleted.is_(False),
                User.status == "ACTIVE",
            ).first()
            if not account:
                continue
            emit_receiver_notice(
                db,
                event_code="COURSE.SCHEDULE_PUBLISHED",
                source_module="academic-affairs",
                source_biz_type="aa_schedule_batch",
                source_biz_id=batch.id,
                receiver_id=account.id,
                title="课表已发布",
                content=f"{batch.batch_name} 已发布，请查看你的课表",
                receiver_as="user",
                dedup_extra=str(teacher_key),
            )
            notified += 1
        operator_name, _role, operator_id = _base._op()
        db.add(AaSchedulePublish(
            tenant_id=_base._tid(),
            batch_id=batch.id,
            term_id=batch.term_id,
            action="PUBLISH",
            operator_name=operator_name or operator_id,
            notified_count=notified,
        ))
        _base._audit(
            db,
            "AA_SCHEDULE_BATCH",
            batch.id,
            "PUBLISH",
            f"teachers={notified};gateVersion={gate['ruleVersion']}",
        )
        db.commit()

    from app.services.message_event_outbox_service import try_process_pending_outbox
    try_process_pending_outbox(worker_id="aa-schedule-inline")
    return {
        "batchId": str(batch_id),
        "status": "PUBLISHED",
        "notified": notified,
        "gate": gate,
    }
