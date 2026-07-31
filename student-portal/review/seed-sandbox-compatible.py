"""仅供 Student Portal V5 复审工作流使用。

仓库 sandbox_service 的尾部兼容种子仍创建 batch_id=NULL 的旧实习记录，
而生产迁移 0123 已要求 NOT NULL。本脚本只在一次性 CI MySQL 中：
1. 临时允许旧种子写入；
2. 调用仓库真实 seed_sandbox；
3. 将每条旧记录归入独立且明确命名的复审兼容批次；
4. 验证无 NULL 后恢复 NOT NULL。

每条旧记录使用独立批次，是为了同时遵守生产唯一约束
(tenant_id, student_id, batch_id)，不猜测历史记录的真实批次归属。

不修改后端源码、生产数据库、API、状态机或权限。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from sqlalchemy import select, text  # noqa: E402

from app.db.session import get_engine, get_sessionmaker  # noqa: E402
from app.models import InternshipBatch, InternshipRecord  # noqa: E402
from app.services.sandbox_service import SANDBOX_TID, seed_sandbox  # noqa: E402

COMPAT_BATCH_PREFIX = "V5-REVIEW-COMPAT"


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
        batch_name=f"学生门户 V5 复审兼容批次 #{row.id}",
        batch_no=batch_no,
        start_date=datetime(2026, 3, 2),
        end_date=datetime(2026, 8, 28),
        status="RUNNING",
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

        rows = session.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == SANDBOX_TID,
            InternshipRecord.batch_id.is_(None),
            InternshipRecord.is_deleted.is_(False),
        ).order_by(InternshipRecord.id)).all()

        mapped = []
        for row in rows:
            batch = compatibility_batch(session, row)
            row.batch_id = batch.id
            mapped.append({
                "recordId": row.id,
                "studentId": row.student_id,
                "batchId": batch.id,
                "batchNo": batch.batch_no,
            })
        session.commit()

        null_count = session.scalar(text(
            "SELECT COUNT(*) FROM t_internship_record "
            "WHERE tenant_id=:tenant_id AND batch_id IS NULL AND is_deleted=0"
        ), {"tenant_id": SANDBOX_TID}) or 0
        duplicate_count = session.scalar(text(
            "SELECT COUNT(*) FROM ("
            " SELECT tenant_id, student_id, batch_id FROM t_internship_record"
            " WHERE tenant_id=:tenant_id AND is_deleted=0 AND batch_id IS NOT NULL"
            " GROUP BY tenant_id, student_id, batch_id HAVING COUNT(*) > 1"
            ") review_duplicates"
        ), {"tenant_id": SANDBOX_TID}) or 0
        if null_count or duplicate_count:
            raise RuntimeError(
                "review sandbox internship integrity failed: "
                f"null={null_count}, duplicates={duplicate_count}"
            )

        session.close()
        set_nullable(False)
        restored_not_null = True
        print({
            "seed": report,
            "compatRecords": len(rows),
            "compatMappings": mapped,
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
            # 即使建数失败，也尽力恢复一次性复审库的生产约束；原异常仍会使工作流失败。
            try:
                set_nullable(False)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
