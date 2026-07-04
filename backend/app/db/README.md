# app/db

- `session.py`：engine/session 惰性创建；`DB_ENABLED=false`（默认）时不连库、不建表、不删表。
- `base.py`：聚合全部模型 metadata（Alembic 入口）。
- `init_db.py`：开发辅助建表（手动调用；生产一律走 Alembic）。

启用数据库：backend/.env 设 `DB_ENABLED=true` + `DATABASE_URL=postgresql+psycopg://...`，
然后 `alembic upgrade head`。测试用 `TEST_DATABASE_URL`（SQLite 内存）。
