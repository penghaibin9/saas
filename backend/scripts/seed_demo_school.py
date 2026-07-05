"""独立执行：给演示租户 demo-school 补齐六大模块演示数据（本地 SQLite dev.db）。
幂等 · 只新增，不修改/删除任何现有数据；可在已运行的库上安全执行。
服务器 MySQL 版：python scripts/seed_mysql_demo_school.py
"""
from __future__ import annotations

import _dev_env  # noqa: F401

from _seed_demo_school import seed_demo_school
from app.db.session import get_sessionmaker

db = get_sessionmaker()()
try:
    print("[seed] demo-school:", seed_demo_school(db))
finally:
    db.close()
