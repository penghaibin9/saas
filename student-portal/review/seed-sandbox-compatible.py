"""仅供 Student Portal V5 复审工作流使用。

仓库 sandbox_service 的尾部兼容种子仍创建 batch_id=NULL 的旧实习记录，
而生产迁移 0123 已要求 NOT NULL。本脚本只在一次性 CI MySQL 中：
1. 临时允许旧种子写入；
2. 调用仓库真实 seed_sandbox；
3. 将旧记录归入明确命名的复审兼容批次；
4. 验证无 NULL 后恢复 NOT NULL。

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

COMPAT_BATCH_NO = "V5-REVIEW-COMPAT"


def set_nullable(nullable: bool) -> None:
    sql = (
        "ALTER TABLE t_internship_record MODIFY COLUMN batch_id BIGINT NULL"
        if nullable
        else "ALTER TABLE t_internship_record MODIFY COLUMN batch_id BIGINT NOT NULL"
    )
    with get_engine().begin() as connection:
        connection.execute(text(sql))


def main() -> int:
    set_nullable(True)
    session = get_sessionmaker()()
    try:
        report = seed_sandbox(session)
        session.commit()

        rows = session.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == SANDBOX_TID,
            InternshipRecord.batch_id.is_(None),
            InternshipRecord.is_deleted.is_(False),
        )).all()
        if rows:
            batch = session.scalars(select(InternshipBatch).where(
                InternshipBatch.tenant_id == SANDBOX_TID,
                InternshipBatch.batch_no == COMPAT_BATCH_NO,
            )).first()
            if batch is None:
                batch = InternshipBatch(
                    tenant_id=SANDBOX_TID,
                    batch_name="学生门户 V5 复审兼容批次",
                    batch_no=COMPAT_BATCH_NO,
                    start_date=datetime(2026, 3, 2),
                    end_date=datetime(2026, 8, 28),
                    status="RUNNING",
                )
                session.add(batch)
                session.flush()
            for row in rows:
                row.batch_id = batch.id
            session.commit()

        null_count = session.scalar(text(
            "SELECT COUNT(*) FROM t_internship_record "
            "WHERE tenant_id=:tenant_id AND batch_id IS NULL AND is_deleted=0"
        ), {"tenant_id": SANDBOX_TID}) or 0
        if null_count:
            raise RuntimeError(f"review sandbox still has {null_count} active null batch records")
        print({"seed": report, "compatRecords": len(rows), "nullBatchCount": int(null_count)})
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    set_nullable(False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
