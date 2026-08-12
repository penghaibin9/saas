"""D1-U 学期/校历/作息便利性只读预览。

本模块不写任何正式事实：
- 校历复制只计算目标日期、复核项与阻断项；
- 8/10 节模板只与当前真实节次做冲突比较。

真正确认仍由现有 academic_affairs_service.add_calendar_event()/create_time_slot()
逐条进入 canonical 写链并执行服务端最终校验，避免产生第二套状态机或事实表。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.modules.academic_affairs.services import academic_affairs_service as canonical
from app.services.db_service import _iso, _tid, session


_STANDARD_8 = (
    (1, "第1节", "08:00", "08:45"),
    (2, "第2节", "08:55", "09:40"),
    (3, "第3节", "10:00", "10:45"),
    (4, "第4节", "10:55", "11:40"),
    (5, "第5节", "14:00", "14:45"),
    (6, "第6节", "14:55", "15:40"),
    (7, "第7节", "16:00", "16:45"),
    (8, "第8节", "16:55", "17:40"),
)
_STANDARD_10 = _STANDARD_8 + (
    (9, "第9节", "19:00", "19:45"),
    (10, "第10节", "19:55", "20:40"),
)
_TEMPLATES = {
    "STANDARD_8": ("标准 8 节作息", _STANDARD_8),
    "STANDARD_10": ("标准 10 节作息", _STANDARD_10),
}


def _term_or_404(db, term_id):
    from app.models import AaTerm

    term = db.get(AaTerm, int(term_id))
    if not term or term.is_deleted or term.tenant_id != _tid():
        raise not_found("学期不存在")
    return term


def _date_only(value: datetime | None) -> str | None:
    return value.date().isoformat() if value else None


def _target_limit(term) -> datetime | None:
    if term.end_date:
        return term.end_date
    if term.start_date and term.teaching_weeks:
        return term.start_date + timedelta(days=int(term.teaching_weeks) * 7 - 1)
    return None


def _map_point(source_term, target_term, point: datetime | None, event_type: str) -> datetime | None:
    if point is None:
        return None
    source_offset = (point.date() - source_term.start_date.date()).days
    source_week_no = source_offset // 7 + 1
    weekday_offset = source_offset % 7

    # 考试事件优先对齐目标学期的考试周，而不是按自然年平移。
    if (
        event_type == "EXAM"
        and source_term.exam_week_start
        and target_term.exam_week_start
        and source_week_no >= int(source_term.exam_week_start)
    ):
        exam_week_delta = source_week_no - int(source_term.exam_week_start)
        target_week_no = int(target_term.exam_week_start) + exam_week_delta
        return target_term.start_date + timedelta(days=(target_week_no - 1) * 7 + weekday_offset)

    return target_term.start_date + timedelta(days=(source_week_no - 1) * 7 + weekday_offset)


def calendar_copy_preview(target_term_id, source_term_id, user) -> dict:
    """把源校历映射到目标学期，仅返回 preview，不落库。"""
    if int(target_term_id) == int(source_term_id):
        raise AppException("VALIDATION_ERROR", "源学期与目标学期不能相同")

    from app.models import AaCalendarEvent

    with session() as db:
        source = _term_or_404(db, source_term_id)
        target = _term_or_404(db, target_term_id)
        if target.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "仅草稿学期可复制校历，请先选择未发布的新学期")
        if not source.start_date:
            raise AppException("VALIDATION_ERROR", "源学期缺少开始日期，无法计算教学周映射")
        if not target.start_date or not target.teaching_weeks:
            raise AppException("VALIDATION_ERROR", "目标学期需先维护开始日期与教学周数")

        source_events = db.scalars(
            select(AaCalendarEvent).where(
                AaCalendarEvent.tenant_id == _tid(),
                AaCalendarEvent.term_id == source.id,
                AaCalendarEvent.is_deleted.is_(False),
            ).order_by(AaCalendarEvent.start_date, AaCalendarEvent.id)
        ).all()
        target_events = db.scalars(
            select(AaCalendarEvent).where(
                AaCalendarEvent.tenant_id == _tid(),
                AaCalendarEvent.term_id == target.id,
                AaCalendarEvent.is_deleted.is_(False),
            )
        ).all()

        target_limit = _target_limit(target)
        items: list[dict] = []
        ready = review = blocked = 0
        for event in source_events:
            mapped_start = _map_point(source, target, event.start_date, event.event_type)
            mapped_end = None
            if mapped_start and event.end_date and event.start_date:
                mapped_end = mapped_start + (event.end_date - event.start_date)
            elif mapped_start and event.end_date:
                mapped_end = _map_point(source, target, event.end_date, event.event_type)
            mapped_swap = _map_point(source, target, event.swap_to_date, "SWAP")

            reasons: list[str] = []
            status = "READY"
            for label, value in (("开始日期", mapped_start), ("结束日期", mapped_end), ("调至日期", mapped_swap)):
                if value and target_limit and (value < target.start_date or value > target_limit):
                    status = "BLOCKED"
                    reasons.append(f"{label}超出目标学期范围")
            needs_review = event.event_type in {"HOLIDAY", "SWAP"}
            if status != "BLOCKED" and needs_review:
                status = "REVIEW"
                reasons.append("节假日/调休按教学周位置映射，需人工核对法定日期")

            if status == "READY":
                ready += 1
            elif status == "REVIEW":
                review += 1
            else:
                blocked += 1

            items.append(
                {
                    "sourceEventId": str(event.id),
                    "eventType": event.event_type,
                    "sourceStartDate": _date_only(event.start_date),
                    "startDate": _date_only(mapped_start),
                    "endDate": _date_only(mapped_end),
                    "swapToDate": _date_only(mapped_swap),
                    "remark": event.remark or "",
                    "status": status,
                    "needsReview": needs_review,
                    "reasons": reasons,
                }
            )

        target_existing_count = len(target_events)
        if target_existing_count:
            blocked += target_existing_count
        can_confirm = bool(items) and blocked == 0 and target_existing_count == 0
        if target_existing_count:
            next_step = "目标学期已有校历事件，请先确认现有内容；为避免重复，本次复制不允许直接确认。"
        elif blocked:
            next_step = "先处理超出目标学期范围的阻断项，再重新预览。"
        elif review:
            next_step = "先核对节假日/调休日期，再确认复制。"
        elif items:
            next_step = "预览无阻断，可确认复制；正式写入仍逐条经过校历 canonical 校验。"
        else:
            next_step = "源学期没有可复制的校历事件。"

        return {
            "sourceTerm": {
                "termId": str(source.id),
                "termName": source.term_name or f"{source.year_code} 第{source.term_no}学期",
                "startDate": _date_only(source.start_date),
                "teachingWeeks": source.teaching_weeks,
                "examWeekStart": source.exam_week_start,
            },
            "targetTerm": {
                "termId": str(target.id),
                "termName": target.term_name or f"{target.year_code} 第{target.term_no}学期",
                "startDate": _date_only(target.start_date),
                "endDate": _date_only(target_limit),
                "teachingWeeks": target.teaching_weeks,
                "examWeekStart": target.exam_week_start,
            },
            "mappingRule": "TEACHING_WEEK_RELATIVE_WITH_EXAM_WEEK_ALIGNMENT",
            "items": items,
            "readyCount": ready,
            "reviewCount": review,
            "blockedCount": blocked,
            "targetExistingCount": target_existing_count,
            "canConfirm": can_confirm,
            "nextStep": next_step,
        }


def _slot_payload(slot_no: int, slot_name: str, start_time: str, end_time: str) -> dict:
    return {
        "slotNo": slot_no,
        "slotName": slot_name,
        "startTime": start_time,
        "endTime": end_time,
    }


def time_slot_template_preview(template_key: str, user) -> dict:
    """标准作息模板与当前真实节次做只读冲突预览。"""
    template_key = (template_key or "").strip().upper()
    if template_key not in _TEMPLATES:
        raise AppException("VALIDATION_ERROR", "作息模板不存在（仅支持 STANDARD_8 / STANDARD_10）")

    from app.models import AaTimeSlot

    label, template = _TEMPLATES[template_key]
    with session() as db:
        existing = db.scalars(
            select(AaTimeSlot).where(
                AaTimeSlot.tenant_id == _tid(),
                AaTimeSlot.is_deleted.is_(False),
            ).order_by(AaTimeSlot.slot_no)
        ).all()
        by_no = {int(row.slot_no): row for row in existing}
        items: list[dict] = []
        ready = exists = blocked = 0

        for slot_no, slot_name, start_time, end_time in template:
            desired = _slot_payload(slot_no, slot_name, start_time, end_time)
            same_no = by_no.get(slot_no)
            status = "READY"
            reason = ""
            current = None
            if same_no:
                current = canonical._time_slot_row(same_no)
                if same_no.start_time == start_time and same_no.end_time == end_time:
                    status = "EXISTS"
                    reason = "同序号节次已存在且时间一致，无需重复创建"
                else:
                    status = "BLOCKED"
                    reason = (
                        f"第{slot_no}节已存在，当前为 "
                        f"{same_no.start_time or '未设'}-{same_no.end_time or '未设'}"
                    )
            else:
                for other in existing:
                    if not other.enabled:
                        continue
                    if canonical._times_overlap(start_time, end_time, other.start_time, other.end_time):
                        status = "BLOCKED"
                        current = canonical._time_slot_row(other)
                        reason = (
                            f"模板时间与第{other.slot_no}节 "
                            f"{other.start_time or '未设'}-{other.end_time or '未设'} 重叠"
                        )
                        break

            if status == "READY":
                ready += 1
            elif status == "EXISTS":
                exists += 1
            else:
                blocked += 1
            items.append({"desired": desired, "status": status, "reason": reason, "current": current})

        can_confirm = ready > 0 and blocked == 0
        if blocked:
            next_step = "先处理冲突节次，再重新预览模板。"
        elif ready:
            next_step = "可确认应用；仅创建 READY 项，每一项仍进入 create_time_slot() 最终校验。"
        else:
            next_step = "当前作息已覆盖该模板，无需重复应用。"
        return {
            "templateKey": template_key,
            "templateLabel": label,
            "items": items,
            "readyCount": ready,
            "existingCount": exists,
            "blockedCount": blocked,
            "canConfirm": can_confirm,
            "nextStep": next_step,
        }
