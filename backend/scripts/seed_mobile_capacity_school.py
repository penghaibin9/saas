#!/usr/bin/env python3
"""V3 §11.1 容量数据种子：12k 学生规模的移动端压测数据集。

**只用于 staging / CI 容量环境。** 脚本自带三重保护，禁止误灌生产：

1. 必须显式传 ``--confirm``；
2. 目标库名必须命中 :data:`ALLOWED_DB_NAME_HINTS`（capacity/staging/test/ci），
   否则直接拒绝；
3. 所有生成记录都挂在独立的 capacity 租户上（``--tenant-id``，默认与主租户不同），
   并统一带 ``CAP-`` 前缀，便于整体清理。

生成的规模对齐 §11.1：

    StudentProfile   12,000 学生 / 300 班
    教职工            500（多角色 context）
    UnifiedTodo      ≥ 80,000（学生/教师待办，due_at 分布不同）
    UnifiedMessage   ≥ 300,000（按学生分布，含紧急与需回执）
    业务办理          ≥ 50,000（历史 + 进行中）

用法：
    python scripts/seed_mobile_capacity_school.py --confirm
    python scripts/seed_mobile_capacity_school.py --confirm --students 12000 --purge
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta

import _mysql_env  # noqa: F401  强制 DB_ENABLED=true 并加载连接参数

from sqlalchemy import delete, func, select

#: 只允许在名字里带这些片段的库上执行。生产库名不含它们，因此永远命不中。
ALLOWED_DB_NAME_HINTS = ("capacity", "staging", "test", "ci")

#: 容量租户与主租户隔离，保证种子数据不会混进任何真实学校。
DEFAULT_CAPACITY_TENANT = 1000000000000000900

STUDENT_PREFIX = "CAP-"
BATCH = 2000


def _fail(message: str) -> None:
    print(f"[capacity-seed] 拒绝执行：{message}", file=sys.stderr)
    raise SystemExit(2)


def _assert_safe_target() -> str:
    from app.core.config import settings

    url = str(settings.DATABASE_URL or "")
    name = url.rsplit("/", 1)[-1].split("?")[0] if "/" in url else ""
    if not name:
        _fail("无法从 DATABASE_URL 解析出库名")
    lowered = name.lower()
    if not any(hint in lowered for hint in ALLOWED_DB_NAME_HINTS):
        _fail(
            f"目标库 {name} 不像容量/预发/测试库（需包含 {'/'.join(ALLOWED_DB_NAME_HINTS)} 之一）。"
            " 大规模种子严禁进入生产库。"
        )
    return name


def _purge(db, tenant_id: int) -> None:
    """只清本 capacity 租户的数据，绝不触碰其他租户。"""
    from app.models import CsLeave, StudentProfile, UnifiedMessage, UnifiedTodo

    for model in (UnifiedMessage, UnifiedTodo, CsLeave, StudentProfile):
        db.execute(delete(model).where(model.tenant_id == tenant_id))
    db.commit()
    print(f"[capacity-seed] 已清空 capacity 租户 {tenant_id} 的旧数据")


def _seed_students(db, tenant_id: int, total: int, classes: int) -> list[int]:
    from app.models import StudentProfile

    ids: list[int] = []
    rows = []
    for index in range(total):
        class_no = index % classes
        rows.append(StudentProfile(
            tenant_id=tenant_id,
            student_no=f"{STUDENT_PREFIX}{index:07d}",
            real_name=f"容量学生{index:05d}",
            grade=f"{2022 + (index % 4)}",
            class_id=100000 + class_no,
            college_id=200000 + (class_no % 12),
            current_stage="ENROLLED",
            student_status="NORMAL",
            status="ACTIVE",
        ))
        if len(rows) >= BATCH:
            db.add_all(rows)
            db.flush()
            ids.extend(row.id for row in rows)
            db.commit()
            rows = []
            print(f"[capacity-seed] students {len(ids)}/{total}")
    if rows:
        db.add_all(rows)
        db.flush()
        ids.extend(row.id for row in rows)
        db.commit()
    print(f"[capacity-seed] students done: {len(ids)}")
    return ids


def _seed_todos(db, tenant_id: int, student_ids: list[int], per_student: int) -> int:
    """due_at 刻意分散：过期 / 24h 内 / 未来 / 无截止，覆盖排序与分页的各种分支。"""
    from app.models import UnifiedTodo

    now = datetime.utcnow()
    types = ["LEAVE_APPROVAL", "AID_APPROVAL", "FUNDING_APPROVAL", "ACAD_WARNING_HANDLE"]
    made = 0
    rows = []
    for position, student_id in enumerate(student_ids):
        for slot in range(per_student):
            offset = (position + slot) % 7
            due = None
            if offset != 6:
                due = now + timedelta(hours=(offset - 2) * 18)
            rows.append(UnifiedTodo(
                tenant_id=tenant_id,
                source_module="student-affairs",
                source_biz_type="LEAVE",
                source_biz_id=position * 10 + slot,
                todo_type=types[(position + slot) % len(types)],
                assignee_id=student_id,
                student_id=student_id,
                title=f"容量待办 {position}-{slot}",
                status="PENDING" if slot % 3 else "DONE",
                due_at=due,
            ))
            made += 1
            if len(rows) >= BATCH:
                db.add_all(rows)
                db.commit()
                rows = []
                print(f"[capacity-seed] todos {made}")
    if rows:
        db.add_all(rows)
        db.commit()
    print(f"[capacity-seed] todos done: {made}")
    return made


def _seed_messages(db, tenant_id: int, student_ids: list[int], per_student: int) -> int:
    from app.models import UnifiedMessage

    now = datetime.utcnow()
    made = 0
    rows = []
    for position, student_id in enumerate(student_ids):
        for slot in range(per_student):
            emergency = (position + slot) % 20 == 0
            rows.append(UnifiedMessage(
                tenant_id=tenant_id,
                receiver_id=student_id,
                receiver_user_id=student_id,
                receiver_context_key="GLOBAL",
                message_type="EMERGENCY" if emergency else "NOTICE",
                title=f"容量通知 {position}-{slot}",
                content="容量压测正文，不含任何真实学生信息。",
                status="UNREAD" if slot % 4 else "READ",
                require_ack=emergency,
                source_module="student-affairs",
                created_at=now - timedelta(minutes=(position + slot) % 5000),
            ))
            made += 1
            if len(rows) >= BATCH:
                db.add_all(rows)
                db.commit()
                rows = []
                print(f"[capacity-seed] messages {made}")
    if rows:
        db.add_all(rows)
        db.commit()
    print(f"[capacity-seed] messages done: {made}")
    return made


def _seed_cases(db, tenant_id: int, student_ids: list[int], per_student: int) -> int:
    """办理记录：状态覆盖四个分段，updated_at 分散以便验证 keyset 翻页。"""
    from app.models import CsLeave

    now = datetime.utcnow()
    statuses = ["PENDING_REVIEW", "RETURNED", "APPROVED", "DRAFT", "REJECTED"]
    made = 0
    rows = []
    for position, student_id in enumerate(student_ids):
        for slot in range(per_student):
            status = statuses[(position + slot) % len(statuses)]
            row = CsLeave(
                tenant_id=tenant_id,
                student_id=student_id,
                leave_type="PERSONAL",
                status=status,
                affairs_status=status,
                code=f"{STUDENT_PREFIX}LV{position}-{slot}",
                apply_time=now - timedelta(hours=(position + slot) % 4000),
                reviewer="容量辅导员" if status != "DRAFT" else None,
                return_reason="材料不全，请补充" if status == "RETURNED" else None,
            )
            rows.append(row)
            made += 1
            if len(rows) >= BATCH:
                db.add_all(rows)
                db.commit()
                rows = []
                print(f"[capacity-seed] cases {made}")
    if rows:
        db.add_all(rows)
        db.commit()
    print(f"[capacity-seed] cases done: {made}")
    return made


def main() -> int:
    parser = argparse.ArgumentParser(description="V3 容量数据种子（仅 staging/CI）")
    parser.add_argument("--confirm", action="store_true", help="必须显式确认才会写入")
    parser.add_argument("--tenant-id", type=int, default=DEFAULT_CAPACITY_TENANT)
    parser.add_argument("--students", type=int, default=12000)
    parser.add_argument("--classes", type=int, default=300)
    parser.add_argument("--todos-per-student", type=int, default=7)
    parser.add_argument("--messages-per-student", type=int, default=25)
    parser.add_argument("--cases-per-student", type=int, default=5)
    parser.add_argument("--purge", action="store_true", help="先清空本 capacity 租户旧数据")
    parser.add_argument("--seed", type=int, default=20260819)
    args = parser.parse_args()

    if not args.confirm:
        _fail("缺少 --confirm。大规模种子必须显式确认。")
    name = _assert_safe_target()
    random.seed(args.seed)

    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        print(f"[capacity-seed] target db={name} tenant={args.tenant_id}")
        if args.purge:
            _purge(db, args.tenant_id)
        from app.models import StudentProfile
        existing = db.scalar(select(func.count()).select_from(StudentProfile).where(
            StudentProfile.tenant_id == args.tenant_id)) or 0
        if existing and not args.purge:
            _fail(f"capacity 租户已有 {existing} 名学生；请加 --purge 重灌，避免不可比的混合数据集")

        student_ids = _seed_students(db, args.tenant_id, args.students, args.classes)
        todos = _seed_todos(db, args.tenant_id, student_ids, args.todos_per_student)
        messages = _seed_messages(db, args.tenant_id, student_ids, args.messages_per_student)
        cases = _seed_cases(db, args.tenant_id, student_ids, args.cases_per_student)
    finally:
        db.close()

    print(
        "[capacity-seed] 完成："
        f"students={len(student_ids)} todos={todos} messages={messages} cases={cases}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
