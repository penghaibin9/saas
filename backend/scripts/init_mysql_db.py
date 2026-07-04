"""初始化 MySQL：建库（utf8mb4）+ 按 ORM metadata 建全部表（幂等，不删任何数据）。
先 CREATE DATABASE IF NOT EXISTS，再 metadata.create_all（已存在的表不会重建）。
无密码/连不上时给出明确指引，不抛裸异常。
"""
from __future__ import annotations

import os

import _mysql_env  # noqa: F401


def main() -> int:
    print(f"[init] 目标：{_mysql_env.describe()}")
    if _mysql_env.password_missing():
        print("⚠️  未检测到 MySQL 密码，无法建库。请在 backend/.env 填 DB_PASSWORD 后重跑：")
        print("    python scripts/init_mysql_db.py")
        return 2

    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = int(os.environ.get("DB_PORT", "3306"))
    user = os.environ.get("DB_USER", "saas_user")
    pwd = os.environ.get("DB_PASSWORD", "")
    name = os.environ.get("DB_NAME", "saas_lifecycle")

    # ── 1) 建库（utf8mb4 / utf8mb4_unicode_ci）──
    try:
        import pymysql
    except ModuleNotFoundError:
        print("⚠️  未安装 pymysql。请先 pip install -r requirements.txt 再重跑。")
        return 2
    try:
        conn = pymysql.connect(host=host, port=port, user=user, password=pwd,
                               charset="utf8mb4", connect_timeout=5)
    except Exception as e:  # noqa: BLE001
        print(f"❌ 连接 MySQL 失败：{e}")
        print("请先跑： python scripts/check_mysql_connection.py 排查。")
        return 1
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{name}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
        print(f"[init] 数据库 `{name}` 就绪（utf8mb4 / utf8mb4_unicode_ci）")
    finally:
        conn.close()

    # ── 2) 建表（SQLAlchemy metadata.create_all，指向含库名的连接串）──
    from app.db.base import metadata
    from app.db.session import get_engine, reset_state
    reset_state()
    engine = get_engine()
    metadata.create_all(bind=engine)
    print(f"[init] 建表完成：{len(metadata.tables)} 张 -> {engine.url.render_as_string(hide_password=True)}")
    for t in sorted(metadata.tables):
        print("   -", t)
    print("下一条命令： python scripts/seed_mysql_demo_data.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
