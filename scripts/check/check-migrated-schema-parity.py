#!/usr/bin/env python
"""迁移库 ↔ ORM 模型一致性门禁（包 14）。

为什么需要这条检查：

包 10 的 `t_affairs_funding_amount_adjustment` 只在 Alembic 迁移里建表、ORM 里没有
对应 model（service 走裸 SQL + `_table_exists` 兜底），而它带一个指向
`t_affairs_funding_application` 的外键。后果是 `metadata.drop_all()` 根本看不见这张
子表，排不出删除顺序，在任何真跑过 alembic 的库上都会撞 MySQL 3730。

这个问题在 CI 里从没暴露过——因为主 CI 的后端 pytest 用 `metadata.create_all()` 建库，
测的是 ORM 推导出的 schema，而不是迁移真正产出的 schema。两边一旦分裂，测试全绿，
生产却是另一套结构。

本脚本在**跑完 alembic upgrade head 的真实库**上比对两侧表集合：

- 迁移建了、ORM 没有 → 该表参与不了 metadata 级操作（drop_all/create_all/反射），
  外键还会连累父表；必须补 model，或明确登记为「不归 ORM 管」的例外。
- ORM 有、迁移没建 → 生产库上线后这张表根本不存在，任何写入直接 1146。

例外清单只接受显式登记，且必须写明理由——不允许用「先加进白名单回头再说」把分裂
永久化。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

# 显式例外：仅限确实不该由 ORM 托管的表，必须写清理由。
# 格式：表名 -> 理由
MIGRATION_ONLY_ALLOWED: dict[str, str] = {
    "alembic_version": "Alembic 自身的版本表，不属于业务模型",
    # 以下三张是包 9/10 有意采用「迁移建表 + service 裸 SQL 读写」的表，暂不补 model。
    # 已确认它们不会像包 10 的外键那样连累父表的 metadata 操作；后续若要参与
    # drop_all/create_all 或被其它 model 外键引用，必须先补 model 再从本清单移除。
    "t_affairs_funding_amount_adjustment":
        "包 10 人工调整表，affairs_funding_authority_service 走裸 SQL + _table_exists 兜底",
    "t_gd_archive_version": "包 9 归档版本链，毕设归档服务走裸 SQL",
    "t_gd_migration_issue": "包 9 迁移欠账登记表，仅由迁移脚本与巡检读写",
}

ORM_ONLY_ALLOWED: dict[str, str] = {}


def main() -> int:
    # Windows 本地控制台默认 GBK，编码不了 ✅/❌；CI 是 UTF-8。统一强制 UTF-8 输出。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    os.environ.setdefault("APP_ENV", "test")
    url = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not url:
        print("❌ 未提供 DATABASE_URL / TEST_DATABASE_URL，无法比对迁移库")
        return 1
    if url.startswith("sqlite"):
        print("❌ 本门禁必须在真实 MySQL 迁移库上运行，拒绝 SQLite")
        return 1

    from sqlalchemy import create_engine, inspect

    import app.models  # noqa: F401  触发全部 model 注册
    from app.db.base import metadata

    engine = create_engine(url)
    db_tables = set(inspect(engine).get_table_names())
    orm_tables = set(metadata.tables.keys())

    migration_only = db_tables - orm_tables - set(MIGRATION_ONLY_ALLOWED)
    orm_only = orm_tables - db_tables - set(ORM_ONLY_ALLOWED)

    failed = False
    if migration_only:
        failed = True
        print("❌ 迁移建了表但 ORM 没有对应 model：")
        for name in sorted(migration_only):
            print(f"   - {name}")
        print("   这些表无法参与 metadata.drop_all()/create_all()，若带外键还会连累父表；")
        print("   请补 model，或在本脚本 MIGRATION_ONLY_ALLOWED 里登记并写明理由。")

    if orm_only:
        failed = True
        print("❌ ORM 有 model 但迁移没建表：")
        for name in sorted(orm_only):
            print(f"   - {name}")
        print("   生产库上线后这些表不存在，任何写入会直接 1146；请补迁移。")

    if failed:
        return 1

    print(f"✅ 迁移库与 ORM 模型一致（{len(orm_tables)} 张表）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
