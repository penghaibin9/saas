"""删除本地 dev.db（仅限开发库；不会触碰任何远程/生产数据库）。"""
from __future__ import annotations

from _dev_env import DEV_DB_PATH

if DEV_DB_PATH.exists():
    DEV_DB_PATH.unlink()
    print(f"[reset] removed {DEV_DB_PATH}")
else:
    print(f"[reset] no dev.db at {DEV_DB_PATH} (nothing to do)")
