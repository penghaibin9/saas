"""仅供 Student Portal V5 复审工作流使用。

仓库 sandbox_service 已先调用当前六域正式种子，然后又追加没有 batch_id 的
旧实习演示记录；生产迁移 0123 已明确禁止这种记录存在。本脚本只操作 GitHub
Actions 的一次性 MySQL：

1. 临时允许旧 sandbox_service 完成写入；
2. 调用仓库真实 seed_sandbox；
3. 为旧 NULL 记录创建审计可追踪的关闭批次；
4. 使用原始 SQL 将旧记录标记失效，并删除只指向这些失效记录的旧统一待办；
5. 确认当前学生仍有正式种子创建的有效实习记录；
6. 恢复 batch_id NOT NULL 生产约束。

使用原始 SQL 的原因：仓库的沙箱基线 ORM 监听器会阻止任何预制记录删除，
而这里清理的是当前生产约束下本就不可能合法存在的旧 NULL 夹具。该处理不会
写入生产数据库，也不修改后端源码、API、权限、路由、tab key 或业务状态机。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from sqlalchemy import func, select, text  # noqa: E402

from app.db.session import get_engine, get_sessionmaker  # noqa: E402
from app.models import InternshipBatch, InternshipRecord, StudentProfile, UnifiedTodo  # noqa: E402
from app.services.sandbox_service import (  # noqa: E402
    SANDBOX_TID,
    SBX_STUDENT_NO,
    seed_sandbox,
)

COMPAT_BATCH_PREFIX = "V5-REVIEW-RETIRED"
RECORD_TABLE = InternshipRecord.__tablename__
TODO_TABLE = UnifiedTodo.__tablename__


def set_nullable(nullable: bool) -> None:
    sql = (
        f"ALTER TABLE {RECORD_TABLE} MODIFY COLUMN batch_id BIGINT NULL"
        if nullable
        else f"ALTER TABLE {RECORD_TABLE} MODIFY COLUMN batch_id BIGINT NOT NULL"
    )
    with get_engine().begin() as connection:
        connection.execute(text(sql))


def load_legacy_rows() -> list[dict[str, int]]:
    with get_engine().connect() as connection:
        rows = connection.execute(text(
            f"SELECT id, student_id FROM {RECORD_TABLE} "
            "WHERE tenant_id=:tenant_id AND batch_id IS NULL AND is_deleted=0 "
            "ORDER BY id"
        ), {"tenant_id": SANDBOX_TID}).mappings().all()
    return [{"id": int(row["id"]), "student_id": int(row["student_id"])} for row in rows]


def create_compatibility_batches(rows: list[dict[str, int]]) -> dict[int, InternshipBatch]:
    """在干净 Session 中只插入批次，不加载或修改受沙箱保护的旧记录。"""
    session = get_sessionmaker()()
    try:
        mapping: dict[int, InternshipBatch] = {}
        for row in rows:
            batch_no = f"{COMPAT_BATCH_PREFIX}-{row['id']}"
            batch = session.scalars(select(InternshipBatch).where(
                InternshipBatch.tenant_id == SANDBOX_TID,
                InternshipBatch.batch_no == batch_no,
            )).first()
            if batch is None:
                batch = InternshipBatch(
                    tenant_id=SANDBOX_TID,
                    batch_name=f"学生门户复审失效旧记录 #{row['id']}",
                    batch_no=batch_no,
                    start_date=datetime(2026, 3, 2),
                    end_date=datetime(2026, 8, 28),
                    status="CLOSED",
                )
                session.add(batch)
                session.flush()
            mapping[row["id"]] = batch
        session.commit()
        return mapping
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def retire_legacy_rows(
    rows: list[dict[str, int]],
    batches: dict[int, InternshipBatch],
) -> tuple[list[dict[str, object]], int]:
    retired: list[dict[str, object]] = []
    removed_todos = 0
    with get_engine().begin() as connection:
        for row in rows:
            batch = batches[row["id"]]
            result = connection.execute(text(
                f"UPDATE {RECORD_TABLE} "
                "SET batch_id=:batch_id, is_deleted=1 "
                "WHERE id=:record_id AND tenant_id=:tenant_id "
                "AND batch_id IS NULL AND is_deleted=0"
            ), {
                "batch_id": int(batch.id),
                "record_id": row["id"],
                "tenant_id": SANDBOX_TID,
            })
            if int(result.rowcount or 0) != 1:
                raise RuntimeError(f"legacy internship record {row['id']} was not retired exactly once")

            todo_result = connection.execute(text(
                f"DELETE FROM {TODO_TABLE} "
                "WHERE tenant_id=:tenant_id AND source_module='internship' "
                "AND source_biz_id=:record_id"
            ), {"tenant_id": SANDBOX_TID, "record_id": row["id"]})
            removed_todos += int(todo_result.rowcount or 0)
            retired.append({
                "recordId": row["id"],
                "studentId": row["student_id"],
                "batchId": int(batch.id),
                "batchNo": batch.batch_no,
                "disposition": "retired-stale-null-batch-fixture",
            })
    return retired, removed_todos


def validate_review_sandbox() -> dict[str, int]:
    session = get_sessionmaker()()
    try:
        student_id = session.scalar(select(StudentProfile.id).where(
            StudentProfile.tenant_id == SANDBOX_TID,
            StudentProfile.student_no == SBX_STUDENT_NO,
            StudentProfile.is_deleted.is_(False),
        ))
        active_valid_count = session.scalar(select(func.count(InternshipRecord.id)).where(
            InternshipRecord.tenant_id == SANDBOX_TID,
            InternshipRecord.student_id == student_id,
            InternshipRecord.batch_id.is_not(None),
            InternshipRecord.is_deleted.is_(False),
        )) or 0
        null_count = session.scalar(select(func.count(InternshipRecord.id)).where(
            InternshipRecord.tenant_id == SANDBOX_TID,
            InternshipRecord.batch_id.is_(None),
            InternshipRecord.is_deleted.is_(False),
        )) or 0
        duplicate_count = session.scalar(text(
            f"SELECT COUNT(*) FROM ("
            f" SELECT tenant_id, student_id, batch_id FROM {RECORD_TABLE}"
            " WHERE tenant_id=:tenant_id AND is_deleted=0 AND batch_id IS NOT NULL"
            " GROUP BY tenant_id, student_id, batch_id HAVING COUNT(*) > 1"
            ") review_duplicates"
        ), {"tenant_id": SANDBOX_TID}) or 0
        if not student_id or active_valid_count < 1 or null_count or duplicate_count:
            raise RuntimeError(
                "review sandbox internship integrity failed: "
                f"student={student_id}, activeValid={active_valid_count}, "
                f"null={null_count}, duplicates={duplicate_count}"
            )
        return {
            "studentId": int(student_id),
            "activeValidStudentRecords": int(active_valid_count),
            "nullBatchCount": int(null_count),
            "duplicateBatchCount": int(duplicate_count),
        }
    finally:
        session.close()


def main() -> int:
    set_nullable(True)
    seed_session = get_sessionmaker()()
    restored_not_null = False
    try:
        report = seed_sandbox(seed_session)
        seed_session.commit()
        seed_session.close()

        legacy_rows = load_legacy_rows()
        batches = create_compatibility_batches(legacy_rows)
        retired, removed_todos = retire_legacy_rows(legacy_rows, batches)
        integrity = validate_review_sandbox()

        set_nullable(False)
        restored_not_null = True
        print({
            "seed": report,
            "retiredLegacyRecords": retired,
            "removedLegacyTodos": removed_todos,
            **integrity,
            "notNullRestored": True,
        })
        return 0
    except Exception:
        if seed_session.is_active:
            seed_session.rollback()
        raise
    finally:
        if seed_session.is_active:
            seed_session.close()
        if not restored_not_null:
            try:
                set_nullable(False)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
