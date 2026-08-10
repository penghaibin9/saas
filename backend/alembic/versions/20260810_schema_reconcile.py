"""schema reconcile — 让老库与全新安装收敛到同一套结构

Revision ID: 20260810_schema_reconcile
Revises: 20260809_pwreset_sms_job
Create Date: 2026-08-10

────────────────────────────────────────────────────────────────────────────
为什么需要这个迁移
────────────────────────────────────────────────────────────────────────────
`0001_init_core_tables` 长期用 `metadata.create_all()` 把当天 ORM 里的表一次建光，
于是那些**本来有正式建表脚本**的表被抢先按 ORM 建了出来（没有 server_default、
索引按 ORM 单列定义），后面正式的建表迁移一看"表已存在"就整段 return。

2026-08-10 已修复 0001（它不再抢建这 291 张表），但那只解决**新装**的学校。
早就装好的学校库里，这些表仍然是当年被抢建出来的降级版本。本迁移负责把它们补齐，
让老库和新库落到同一套结构上。

同时统一排序规则：两种安装路径都出现过 `utf8mb4_unicode_ci` 与
`utf8mb4_0900_ai_ci` 混用（裸 SQL 里 `DEFAULT CHARSET=utf8mb4` 不写 COLLATE 时，
MySQL 8 会给 0900_ai_ci）。混用会让跨表字符串比较直接报错 1267。
生产声明的排序规则是 utf8mb4_unicode_ci（见 deploy/docker/docker-compose.mysql.yml），
这里统一收敛到它。

────────────────────────────────────────────────────────────────────────────
本迁移的性质
────────────────────────────────────────────────────────────────────────────
- **冻结**：要执行的列/索引差异一次性算好，存在同目录的
  `20260810_schema_reconcile_data.json`，不在运行时读 ORM。
  （运行时读 ORM 就是把"时间旅行"换个地方重演。）
- **幂等**：每条都先查 information_schema，已经对了就跳过。已经正确的库上是空操作。
- **只补不删**：不删列、不删表、不动任何一行业务数据。多余索引会删，
  但删之前会避开外键依赖的索引。

验证方式见 docs/06-开发施工与质量验收/迁移基线重建-待办.md。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from alembic import op
from sqlalchemy import text

revision = "20260810_schema_reconcile"
down_revision = "20260809_pwreset_sms_job"
branch_labels = None
depends_on = None

_log = logging.getLogger("alembic.schema_reconcile")

TARGET_COLLATION = "utf8mb4_unicode_ci"
TARGET_CHARSET = "utf8mb4"
_DATA = Path(__file__).with_name("20260810_schema_reconcile_data.json")


def _payload() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def _schema(bind) -> str:
    return bind.execute(text("SELECT DATABASE()")).scalar()


def _column_state(bind, schema: str) -> dict:
    rows = bind.execute(text("""
        SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
        FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = :s
    """), {"s": schema}).fetchall()
    return {(t, c): (ctype, nullable, default) for t, c, ctype, nullable, default in rows}


def _index_names(bind, schema: str) -> set:
    rows = bind.execute(text("""
        SELECT TABLE_NAME, INDEX_NAME FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = :s AND INDEX_NAME <> 'PRIMARY'
    """), {"s": schema}).fetchall()
    return {(t, n) for t, n in rows}


def _fk_backed_indexes(bind, schema: str) -> set:
    """被外键依赖的索引不能删（MySQL errno 1553）。"""
    rows = bind.execute(text("""
        SELECT DISTINCT TABLE_NAME, CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = :s AND REFERENCED_TABLE_NAME IS NOT NULL
    """), {"s": schema}).fetchall()
    return {(t, n) for t, n in rows}


def upgrade() -> None:
    bind = op.get_bind()
    schema = _schema(bind)
    data = _payload()
    stats = {"collation": 0, "column": 0, "index_added": 0, "index_dropped": 0,
             "skipped": 0, "failed": 0}

    # ── ① 统一表级字符集与排序规则 ────────────────────────────────────
    wrong = bind.execute(text("""
        SELECT TABLE_NAME FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = :s AND TABLE_TYPE = 'BASE TABLE'
          AND TABLE_COLLATION IS NOT NULL AND TABLE_COLLATION <> :c
    """), {"s": schema, "c": TARGET_COLLATION}).scalars().all()
    for table in wrong:
        if table == "alembic_version":
            continue
        try:
            bind.execute(text(
                f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET {TARGET_CHARSET} "
                f"COLLATE {TARGET_COLLATION}"))
            stats["collation"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["failed"] += 1
            _log.warning("排序规则统一失败 table=%s err=%s", table, exc)

    # ── ② 补齐列定义（默认值 / 可空性 / 类型）──────────────────────────
    state = _column_state(bind, schema)
    existing_tables = {t for (t, _c) in state}
    for item in data["mod_cols"]:
        table, column, ddl = item["table"], item["column"], item["ddl"]
        if table not in existing_tables:
            stats["skipped"] += 1
            continue
        if item.get("add") and (table, column) not in state:
            sql = f"ALTER TABLE `{table}` ADD COLUMN `{column}` {ddl}"
        elif (table, column) in state:
            sql = f"ALTER TABLE `{table}` MODIFY COLUMN `{column}` {ddl}"
        else:
            stats["skipped"] += 1
            continue
        try:
            bind.execute(text(sql))
            stats["column"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["failed"] += 1
            _log.warning("列补齐失败 %s.%s err=%s", table, column, exc)

    # ── ③ 索引对齐 ────────────────────────────────────────────────────
    have = _index_names(bind, schema)
    protected = _fk_backed_indexes(bind, schema)
    for item in data["add_idx"]:
        key = (item["table"], item["name"])
        if key in have or item["table"] not in existing_tables:
            continue
        cols = ", ".join(f"`{c}`" for c in item["cols"])
        unique = "UNIQUE " if item["unique"] else ""
        try:
            bind.execute(text(
                f"CREATE {unique}INDEX `{item['name']}` ON `{item['table']}` ({cols})"))
            stats["index_added"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["failed"] += 1
            _log.warning("建索引失败 %s.%s err=%s", item["table"], item["name"], exc)
    for item in data["drop_idx"]:
        key = (item["table"], item["name"])
        if key not in have or key in protected:
            continue
        try:
            bind.execute(text(f"DROP INDEX `{item['name']}` ON `{item['table']}`"))
            stats["index_dropped"] += 1
        except Exception as exc:  # noqa: BLE001
            # 外键依赖等原因删不掉的索引只是冗余，不阻塞升级
            _log.info("冗余索引保留 %s.%s err=%s", item["table"], item["name"], exc)
    print(f"[schema_reconcile] 排序规则统一={stats['collation']} 列补齐={stats['column']} "
          f"新建索引={stats['index_added']} 删冗余索引={stats['index_dropped']} "
          f"跳过={stats['skipped']} 失败={stats['failed']}")


def downgrade() -> None:
    # 本迁移只做"补齐到正确结构"，回退没有业务意义：
    # 把默认值/索引再撤回去只会让库重新变成两种结构。
    pass
