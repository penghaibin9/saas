"""D5-U1：课表批量导入读查询去线性化（真实 MySQL 查询数合同）。

批量导入仍走 `academic_affairs_schedule_final_service._apply_import_rows()` 唯一校验链；
本测试只证明读取 teaching-task / term / slot / classroom / schedule-item 的 SELECT
不会随导入行数线性增长，同时锁住同一任务多行时的容量递增语义。
"""
from __future__ import annotations

import re

from sqlalchemy import event

TID = 1000000000000000001


def _ctx():
    from app.core.context import set_current_user, set_tenant

    user = {
        "tenantId": str(TID),
        "userId": "81002",
        "realName": "D5U排课性能测试",
        "userType": "TEACHER",
        "currentRoleCode": "ACADEMIC_ADMIN",
        "permissions": ["*"],
        "dataScope": "ALL",
    }
    set_tenant({"tenantId": str(TID)})
    set_current_user(user)
    return user


def _clear_ctx():
    from app.core.context import set_current_user, set_tenant

    set_current_user(None)
    set_tenant(None)


def _seed(*, weekly_hours: int = 12):
    from app.db.session import get_sessionmaker
    from app.models import (
        AaClassroom,
        AaScheduleBatch,
        AaTeachingTask,
        AaTeachingTaskBatch,
        AaTerm,
        AaTimeSlot,
    )

    db = get_sessionmaker()()
    term = AaTerm(
        tenant_id=TID,
        year_code="2097-2098-D5U",
        term_no=1,
        term_name="D5U批量导入性能学期",
        status="PUBLISHED",
        is_current=False,
        teaching_weeks=18,
    )
    db.add(term)
    db.flush()

    batch = AaScheduleBatch(
        tenant_id=TID,
        term_id=term.id,
        batch_name="D5U批量导入性能课表",
        status="DRAFT",
    )
    db.add(batch)
    db.flush()

    task_batch = AaTeachingTaskBatch(
        tenant_id=TID,
        term_id=term.id,
        batch_name="D5U批量导入性能教学任务",
        status="APPROVED",
    )
    db.add(task_batch)
    db.flush()

    for slot_no in range(1, 6):
        db.add(
            AaTimeSlot(
                tenant_id=TID,
                slot_no=slot_no,
                slot_name=f"D5U第{slot_no}节",
                start_time="00:00",
                end_time="23:59",
                enabled=True,
                status="ENABLED",
            )
        )

    room = AaClassroom(
        tenant_id=TID,
        building_code="D5U",
        building_name="D5U楼",
        room_code="A101",
        room_name="D5U-A101",
        capacity=80,
        room_type="LECTURE",
        status="AVAILABLE",
    )
    db.add(room)
    db.flush()

    task = AaTeachingTask(
        tenant_id=TID,
        batch_id=task_batch.id,
        course_id=99101,
        course_name="D5U查询数课程",
        class_id=99101,
        teaching_class_name="D5U性能班",
        teacher_key="D5U_T01",
        teacher_name="D5U老师",
        expected_students=40,
        weekly_hours=weekly_hours,
        total_hours=weekly_hours * 18,
        required_room_type="LECTURE",
        start_week=1,
        end_week=18,
        status="READY",
    )
    db.add(task)
    db.commit()
    result = {"batch_id": batch.id, "task_id": task.id}
    db.close()
    return result


def _rows(task_id: int, count: int) -> list[dict]:
    rows = []
    for index in range(count):
        weekday = index // 5 + 1
        slot_no = index % 5 + 1
        rows.append(
            {
                "taskId": str(task_id),
                "weekday": weekday,
                "slotNo": slot_no,
                "classroom": "D5U-A101",
                "weekParity": "ALL",
            }
        )
    return rows


def _count_relevant_selects(engine, fn) -> dict[str, int]:
    tables = (
        "t_aa_teaching_task_batch",
        "t_aa_teaching_task",
        "t_aa_term",
        "t_aa_time_slot",
        "t_aa_classroom",
        "t_aa_schedule_item",
    )
    counts = {table: 0 for table in tables}
    table_patterns = {
        table: re.compile(
            rf"(?<![A-Z0-9_]){re.escape(table.upper())}(?![A-Z0-9_])"
        )
        for table in tables
    }

    def before_cursor_execute(_conn, _cursor, statement, *_args, **_kwargs):
        upper = statement.strip().upper()
        if not upper.startswith("SELECT"):
            return
        # 必须按完整 SQL 标识符计数，不能做子串包含：
        # t_aa_teaching_task_batch 会包含 t_aa_teaching_task 前缀，子串统计会把
        # 同一条 task-batch SELECT 误计到 teaching-task，制造固定开销假红灯。
        for table, pattern in table_patterns.items():
            if pattern.search(upper):
                counts[table] += 1

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
    return counts


def test_schedule_import_read_queries_do_not_scale_with_row_count(client, db_mode):
    from app.db.session import get_engine
    from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as sched

    ids = _seed(weekly_hours=12)
    user = _ctx()
    try:
        engine = get_engine()
        small = _count_relevant_selects(
            engine,
            lambda: sched.import_dry_run(
                ids["batch_id"], user, _rows(ids["task_id"], 2)
            ),
        )
        large = _count_relevant_selects(
            engine,
            lambda: sched.import_dry_run(
                ids["batch_id"], user, _rows(ids["task_id"], 10)
            ),
        )
    finally:
        _clear_ctx()

    assert small == large, (
        f"批量导入读查询不应随行数增长：2行={small}, 10行={large}；"
        "不同说明某一热点重新退化成逐行查询"
    )
    assert small["t_aa_teaching_task_batch"] <= 1
    assert small["t_aa_teaching_task"] <= 1
    assert small["t_aa_time_slot"] <= 1
    assert small["t_aa_classroom"] <= 1
    assert small["t_aa_schedule_item"] <= 2
    assert small["t_aa_term"] <= 2


def test_schedule_import_preload_updates_capacity_for_later_rows(client, db_mode):
    """预载计数必须在每个成功行后递增；不能因缓存把同一任务超排放过去。"""
    from app.modules.academic_affairs.services import academic_affairs_schedule_final_service as sched

    ids = _seed(weekly_hours=12)
    user = _ctx()
    try:
        preview = sched.import_dry_run(
            ids["batch_id"], user, _rows(ids["task_id"], 13)
        )
    finally:
        _clear_ctx()

    assert preview["validRows"] == 12
    assert preview["invalidRows"] == 1
    assert preview["errors"][0]["row"] == 13
    assert "超排" in preview["errors"][0]["message"]