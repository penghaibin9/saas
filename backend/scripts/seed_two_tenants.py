"""独立执行：初始化/补齐双真实租户演示体系（本地 SQLite dev.db）。
demo-school（admin/teacher/student · 123456，只读富数据）
sandbox-school（admin2/teacher2/student2 · 123456，可重置沙箱）
幂等 · 只新增；服务器 MySQL 版：python scripts/seed_mysql_two_tenants.py
"""
from __future__ import annotations

import json

import _dev_env  # noqa: F401

from _seed_demo_school import seed_demo_school
from _seed_two_tenants import seed_two_tenants
from app.db.session import get_sessionmaker

db = get_sessionmaker()()
try:
    print("[seed] demo-school 富数据:", seed_demo_school(db))          # 张同学六域（幂等）
    print("[seed] two-tenants:", json.dumps(seed_two_tenants(db), ensure_ascii=False))
finally:
    db.close()
