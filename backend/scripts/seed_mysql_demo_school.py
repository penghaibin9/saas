"""独立执行：给演示租户 demo-school 补齐六大模块演示数据（服务器 MySQL）。
幂等 · 只新增，不修改/删除任何现有数据；可在生产库上安全执行。
用法：cd backend && python scripts/seed_mysql_demo_school.py
（读取 .env 的 MySQL 连接；执行前请确认 .env 指向目标库）
"""
from __future__ import annotations

import _mysql_env  # noqa: F401

from _seed_demo_school import seed_demo_school
from app.db.session import get_sessionmaker

db = get_sessionmaker()()
try:
    print("[seed] demo-school:", seed_demo_school(db))
finally:
    db.close()
