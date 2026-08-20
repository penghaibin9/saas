#!/usr/bin/env python3
"""V3 §11.1 / Teacher T9 capacity seed for a 12k-student school.

**Only for staging / CI capacity databases.** Three hard guards prevent accidental production use:
1. ``--confirm`` is mandatory;
2. the database name must contain capacity/staging/test/ci;
3. every generated row is tenant-scoped to a dedicated capacity tenant and uses ``CAP-`` labels.

Default scale:
    StudentProfile              12,000 / 300 classes
    UnifiedTodo                 84,000
    student UnifiedMessage     300,000
    teacher message identities     500 active contexts
    teacher UnifiedMessage      50,000 (100/context, same >300k table)
    business cases              60,000

Teacher identities are deterministic *message receiver identities*, not login credentials. Real p1000/p3000
runs still require a pre-issued teacher token pool from the staging identity system; this script never prints or
commits secrets. EXPLAIN can discover the seeded STAFF receiver/context directly.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta

import _mysql_env  # noqa: F401

from sqlalchemy import delete, func, select

ALLOWED_DB_NAME_HINTS = ("capacity", "staging", "test", "ci")
DEFAULT_CAPACITY_TENANT = 1000000000000000900
STUDENT_PREFIX = "CAP-"
TEACHER_PREFIX = "CAP-TEACHER-"
TEACHER_USER_ID_BASE = 9_000_000_000
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
    """Only delete rows owned by the capacity tenant."""
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
    from app.models import UnifiedTodo

    now = datetime.utcnow()
    types = ["LEAVE_APPROVAL", "AID_APPROVAL", "FUNDING_APPROVAL", "ACAD_WARNING_HANDLE"]
    made = 0
    rows = []
    for position, student_id in enumerate(student_ids):
        for slot in range(per_student):
            offset = (position + slot) % 7
            due = None if offset == 6 else now + timedelta(hours=(offset - 2) * 18)
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
                receiver_type="STUDENT",
                receiver_context_key="GLOBAL",
                message_type="EMERGENCY" if emergency else "NOTICE",
                category="EMERGENCY" if emergency else "SYSTEM",
                priority="EMERGENCY" if emergency else "NORMAL",
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
                print(f"[capacity-seed] student messages {made}")
    if rows:
        db.add_all(rows)
        db.commit()
    print(f"[capacity-seed] student messages done: {made}")
    return made


def _teacher_identity(index: int) -> tuple[int, str]:
    return TEACHER_USER_ID_BASE + index, f"{TEACHER_PREFIX}CTX-{index:04d}"


def _seed_teacher_messages(db, tenant_id: int, contexts: int, per_context: int) -> int:
    """Seed T9 message rows across many receiver/context identities on the 300k+ message table."""
    from app.models import UnifiedMessage

    now = datetime.utcnow()
    made = 0
    rows = []
    specs = (
        ("SYSTEM", "SYSTEM", "NORMAL", "系统通知"),
        ("BUSINESS", "BUSINESS", "NORMAL", "学生动态"),
        ("EMERGENCY", "EMERGENCY", "EMERGENCY", "风险预警"),
        ("TODO_NOTICE", "TODO", "IMPORTANT", "催办提醒"),
    )
    for index in range(contexts):
        receiver_uid, context = _teacher_identity(index)
        for slot in range(per_context):
            message_type, category, priority, title = specs[(index + slot) % len(specs)]
            rows.append(UnifiedMessage(
                tenant_id=tenant_id,
                receiver_id=receiver_uid,
                receiver_user_id=receiver_uid,
                receiver_type="STAFF",
                receiver_context_key=context,
                message_type=message_type,
                category=category,
                priority=priority,
                title=f"{TEACHER_PREFIX}{title}-{index:04d}-{slot:03d}",
                content="Teacher V3 T9 容量压测正文，不含任何真实教师或学生信息。",
                status="UNREAD" if slot % 5 else "READ",
                require_ack=category == "EMERGENCY",
                source_module="capacity-teacher-v3",
                delivered_at=now - timedelta(seconds=(index * per_context + slot) % 86400),
                created_at=now - timedelta(seconds=(index * per_context + slot) % 86400),
            ))
            made += 1
            if len(rows) >= BATCH:
                db.add_all(rows)
                db.commit()
                rows = []
                print(f"[capacity-seed] teacher messages {made}/{contexts * per_context}")
    if rows:
        db.add_all(rows)
        db.commit()
    print(f"[capacity-seed] teacher messages done: {made} contexts={contexts}")
    return made


def _seed_cases(db, tenant_id: int, student_ids: list[int], per_student: int) -> int:
    from app.models import CsLeave

    now = datetime.utcnow()
    statuses = ["PENDING_REVIEW", "RETURNED", "APPROVED", "DRAFT", "REJECTED"]
    made = 0
    rows = []
    for position, student_id in enumerate(student_ids):
        for slot in range(per_student):
            status = statuses[(position + slot) % len(statuses)]
            rows.append(CsLeave(
                tenant_id=tenant_id,
                student_id=student_id,
                leave_type="PERSONAL",
                status=status,
                affairs_status=status,
                code=f"{STUDENT_PREFIX}LV{position}-{slot}",
                apply_time=now - timedelta(hours=(position + slot) % 4000),
                reviewer="容量辅导员" if status != "DRAFT" else None,
                return_reason="材料不全，请补充" if status == "RETURNED" else None,
            ))
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
    parser.add_argument("--teacher-contexts", type=int, default=500)
    parser.add_argument("--teacher-messages-per-context", type=int, default=100)
    parser.add_argument("--cases-per-student", type=int, default=5)
    parser.add_argument("--purge", action="store_true", help="先清空本 capacity 租户旧数据")
    parser.add_argument("--seed", type=int, default=20260819)
    args = parser.parse_args()

    if not args.confirm:
        _fail("缺少 --confirm。大规模种子必须显式确认。")
    if args.students < 1 or args.classes < 1 or args.teacher_contexts < 1:
        _fail("students/classes/teacher-contexts 必须大于 0")
    if args.teacher_messages_per_context < 1:
        _fail("teacher-messages-per-context 必须大于 0")
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
        student_messages = _seed_messages(db, args.tenant_id, student_ids, args.messages_per_student)
        teacher_messages = _seed_teacher_messages(
            db, args.tenant_id, args.teacher_contexts, args.teacher_messages_per_context
        )
        cases = _seed_cases(db, args.tenant_id, student_ids, args.cases_per_student)
    finally:
        db.close()

    print(
        "[capacity-seed] 完成："
        f"students={len(student_ids)} todos={todos} studentMessages={student_messages} "
        f"teacherContexts={args.teacher_contexts} teacherMessages={teacher_messages} cases={cases}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
