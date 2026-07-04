"""写入演示种子数据（本地 SQLite dev.db）。逻辑单一来源见 scripts/_seed_core.py。
MySQL 版见 scripts/seed_mysql_demo_data.py。"""
from __future__ import annotations

import _dev_env  # noqa: F401  （设置 SQLite DATABASE_URL / DB_ENABLED=true）

from _seed_core import run

raise SystemExit(run())
