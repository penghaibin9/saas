"""仅供 Student Portal V5 复审工作流使用。

仓库 sandbox_service 已先调用当前六域正式种子，然后又追加一条没有 batch_id 的
旧实习演示记录；生产迁移 0123 已明确禁止这种记录存在。本脚本只在一次性 CI MySQL 中：

1. 临时允许旧 sandbox_service 完成写入；
2. 调用仓库真实 seed_sandbox；
3. 给无法映射真实业务批次的旧 NULL 记录分配审计可追踪的兼容批次并标记为已删除；
4. 删除只指向这些失效旧记录的统一待办，避免污染学生真实页面；
5. 确认当前学生仍有正式种子创建的有效实习记录；
6. 恢复 batch_id NOT NULL 生产约束。

不修改后端源码、生产数据库、API、权限、路由、tab key 或业务状态机。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from sqlalchemy import delete, func, select, text  # noqa: E402

from app.db.session import get_engine, get_sessionmaker  # noqa: E402
from app.models import InternshipBatch, InternshipRecord, StudentProfile, UnifiedTodo  # noqa: E402
from app.services.sandbox_service import (  # noqa: E402
    SANDBOX_TID,
    SBX_STUDENT_NO,
    seed_sandbox,
)

COMPAT_BATCH_PREFIX = "V5-REVIEW-RETIRED"


def set_nullable(nullable: bool) -> None:
    sql = (
        "ALTER TABLE t_internship_record MODIFY COLUMN batch_id BIGINT NULL"
        if nullable
        else "ALTER TABLE t_internship_record MODIFY COLUMN batch_id BIGINT NOT NULL"
    )
    with get_engine().begin() as connection:
        connection.execute(text(sql))


def compatibility_batch(session, row: InternshipRecord) -> InternshipBatch:
    batch_no = f"{COMPAT_BATCH_PREFIX}-{row.id}"
    batch = session.scalars(select(InternshipBatch).where(
        InternshipBatch.tenant_id == SANDBOX_TID,
        InternshipBatch.batch_no == batch_no,
    )).first()
    if batch is not None:
        return batch
    batch = InternshipBatch(
        tenant_id=SANDBOX_TID,
        batch_name=f"学生门户复审失效旧记录 #{row.id}",
        batch_no=batch_no,
        start_date=datetime(2026, 3, 2),
        end_date=datetime(2026, 8, 28),
        status="CLOSED",
    )
    session.add(batch)
    session.flush()
    return batch


def main() -> int:
    set_nullable(True)
    session = get_sessionmaker()()
    restored_not_null = False
    try:
        report = seed_sandbox(session)
        session.commit()

        legacy_rows = session.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == SANDBOX_TID,
            InternshipRecord.batch_id.is_(None),
            InternshipRecord.is_deleted.is_(False),
        ).order_by(InternshipRecord.id)).all()

        retired = []
        legacy_ids = []
        for row in legacy_rows:
            batch = compatibility_batch(session, row)
            row.batch_id = batch.id
            row.is_deleted = True
            legacy_ids.append(row.id)
            retired.append({
                "recordId": row.id,
                "studentId": row.student_id,
                "batchId": batch.id,
                "batchNo": batch.batch_no,
                "disposition": "retired-stale-null-batch-fixture",
            })

        removed_todos = 0
        if legacy_ids:
            result = session.execute(delete(UnifiedTodo).where(
                UnifiedTodo.tenant_id == SANDBOX_TID,
                UnifiedTodo.source_module == "internship",
                UnifiedTodo.source_biz_id.in_(legacy_ids),
            ))
            removed_todos = int(result.rowcount or 0)
        session.commit()

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
            "SELECT COUNT(*) FROM ("
            " SELECT tenant_id, student_id, batch_id FROM t_internship_record"
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

        session.close()
        set_nullable(False)
        restored_not_null = True
        print({
            "seed": report,
            "retiredLegacyRecords": retired,
            "removedLegacyTodos": removed_todos,
            "activeValidStudentRecords": int(active_valid_count),
            "nullBatchCount": int(null_count),
            "duplicateBatchCount": int(duplicate_count),
            "notNullRestored": True,
        })
        return 0
    except Exception:
        session.rollback()
        raise
    finally:
        if session.is_active:
            session.close()
        if not restored_not_null:
            try:
                set_nullable(False)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
