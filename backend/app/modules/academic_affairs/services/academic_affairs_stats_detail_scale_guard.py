"""教务统计下钻的大校规模安全层。

当前只接管课表冲突下钻的纯读实现：保持 public stats → legacy 动态调用和返回 DTO 不变，
把“全量冲突组 materialize → Python 切页 → 每组再查一次明细”的路径收敛为：
SQL group count + SQL page + 当前页一次批量明细查询。任何排课事实/写链均不在本模块实现。
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import and_, func, or_, select

from app.core.exceptions import AppException

from . import academic_affairs_stats_service as stats
from .academic_affairs_production_audit_guard import _bounded_page_size


def _page_values(page, page_size) -> tuple[int, int]:
    try:
        page_no = int(1 if page is None else page)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "page 必须为整数") from None
    if page_no < 1:
        raise AppException("VALIDATION_ERROR", "page 必须大于等于 1")
    return page_no, _bounded_page_size(page_size, default=20)


def schedule_conflicts(user, college_id=None, term_id=None, page=1, page_size=20):
    """课表冲突下钻：SQL 真分页 + 单次页面明细查询，判定口径保持原实现。"""
    from app.models import AaScheduleBatch, AaScheduleItem

    page_no, size = _page_values(page, page_size)
    with stats.session() as db:
        scope = stats._resolve_scope(user, db)
        stats._validate_college_param(scope, college_id)
        colleges = stats._college_ids_scope(db, scope, college_id)
        if colleges is not None and not colleges:
            return [], 0

        batch_conditions = [
            AaScheduleBatch.tenant_id == stats._tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ]
        if term_id:
            batch_conditions.append(AaScheduleBatch.term_id == int(term_id))
        if colleges is not None:
            batch_conditions.append(AaScheduleBatch.college_id.in_(colleges))
        batch_ids = select(AaScheduleBatch.id).where(*batch_conditions)

        group_query = (
            select(
                AaScheduleItem.class_id.label("class_id"),
                AaScheduleItem.class_name.label("class_name"),
                AaScheduleItem.weekday.label("weekday"),
                AaScheduleItem.slot_no.label("slot_no"),
                AaScheduleItem.week_parity.label("week_parity"),
                func.count(AaScheduleItem.id).label("c"),
            )
            .where(
                AaScheduleItem.tenant_id == stats._tid(),
                AaScheduleItem.is_deleted.is_(False),
                AaScheduleItem.status == "EFFECTIVE",
                AaScheduleItem.batch_id.in_(batch_ids),
                AaScheduleItem.class_id.isnot(None),
            )
            .group_by(
                AaScheduleItem.class_id,
                AaScheduleItem.class_name,
                AaScheduleItem.weekday,
                AaScheduleItem.slot_no,
                AaScheduleItem.week_parity,
            )
            .having(func.count(AaScheduleItem.id) > 1)
        )
        total = int(db.scalar(select(func.count()).select_from(group_query.subquery())) or 0)
        page_groups = db.execute(
            group_query.order_by(
                AaScheduleItem.class_id.asc(),
                AaScheduleItem.weekday.asc(),
                AaScheduleItem.slot_no.asc(),
                AaScheduleItem.week_parity.asc(),
                AaScheduleItem.class_name.asc(),
            )
            .offset((page_no - 1) * size)
            .limit(size)
        ).all()
        if not page_groups:
            return [], total

        detail_predicates = []
        for group in page_groups:
            predicate = and_(
                AaScheduleItem.class_id == group.class_id,
                AaScheduleItem.weekday == group.weekday,
                AaScheduleItem.slot_no == group.slot_no,
            )
            if group.week_parity is None:
                predicate = and_(predicate, AaScheduleItem.week_parity.is_(None))
            else:
                predicate = and_(predicate, AaScheduleItem.week_parity == group.week_parity)
            detail_predicates.append(predicate)

        detail_rows = db.scalars(
            select(AaScheduleItem)
            .where(
                AaScheduleItem.tenant_id == stats._tid(),
                AaScheduleItem.is_deleted.is_(False),
                AaScheduleItem.status == "EFFECTIVE",
                AaScheduleItem.batch_id.in_(batch_ids),
                or_(*detail_predicates),
            )
            .order_by(AaScheduleItem.id.asc())
        ).all()
        details_by_key = defaultdict(list)
        for row in detail_rows:
            key = (row.class_id, row.weekday, row.slot_no, row.week_parity)
            details_by_key[key].append({
                "courseName": row.course_name,
                "teacherName": row.teacher_name,
                "classroomText": row.classroom_text,
            })

        items = []
        for group in page_groups:
            key = (group.class_id, group.weekday, group.slot_no, group.week_parity)
            items.append({
                "className": group.class_name,
                "weekday": group.weekday,
                "slotNo": group.slot_no,
                "weekParity": group.week_parity,
                "conflictCount": int(group.c),
                "courses": details_by_key.get(key, []),
            })
        return items, total


schedule_conflicts._stats_detail_sql_paging_guard = True


def install() -> None:
    if not hasattr(stats, "_stats_detail_scale_original_schedule_conflicts"):
        stats._stats_detail_scale_original_schedule_conflicts = stats.schedule_conflicts
    if not getattr(stats.schedule_conflicts, "_stats_detail_sql_paging_guard", False):
        stats.schedule_conflicts = schedule_conflicts
