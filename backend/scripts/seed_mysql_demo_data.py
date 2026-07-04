"""写入演示种子数据到 MySQL（逻辑单一来源见 scripts/_seed_core.py，与 SQLite 版一致）。
幂等：已有主租户学生则跳过。无密码/连不上时给出指引，不抛裸异常。
先决条件：已跑过 init_mysql_db.py（库表就绪）。
"""
from __future__ import annotations

import _mysql_env  # noqa: F401


def main() -> int:
    print(f"[seed-mysql] 目标：{_mysql_env.describe()}")
    if _mysql_env.password_missing():
        print("⚠️  未检测到 MySQL 密码。请在 backend/.env 填 DB_PASSWORD 后重跑：")
        print("    python scripts/seed_mysql_demo_data.py")
        return 2
    try:
        from _seed_core import run
        return run()
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        print(f"❌ 种子写入失败：{msg}")
        if "doesn't exist" in msg or "no such table" in msg.lower() or "1146" in msg:
            print("看起来表还没建。请先跑： python scripts/init_mysql_db.py")
        else:
            print("请先跑： python scripts/check_mysql_connection.py 排查连接。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
