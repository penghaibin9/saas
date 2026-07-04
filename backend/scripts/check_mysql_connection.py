"""检查 MySQL 连接是否可用（只读，绝不建表/改数据）。
成功：打印版本/字符集/目标库是否存在。
失败：打印缺什么参数、该填什么、下一条命令是什么（不抛裸异常，不中断整条流水）。
"""
from __future__ import annotations

import os

import _mysql_env  # noqa: F401


def _guide_password():
    print("─" * 60)
    print("⚠️  未检测到 MySQL 密码（DB_PASSWORD 或 DATABASE_URL）。")
    print("请在 backend/.env 里补上（该文件已 gitignore，不会提交）：")
    print("    DB_ENABLED=true")
    print("    DB_DRIVER=mysql")
    print("    DB_HOST=127.0.0.1")
    print("    DB_PORT=3306")
    print("    DB_NAME=saas_lifecycle")
    print("    DB_USER=saas_user")
    print("    DB_PASSWORD=你的MySQL密码")
    print("然后重跑： python scripts/check_mysql_connection.py")
    print("─" * 60)


def main() -> int:
    print(f"[check] 目标：{_mysql_env.describe()}")
    if _mysql_env.password_missing():
        _guide_password()
        return 2

    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = int(os.environ.get("DB_PORT", "3306"))
    user = os.environ.get("DB_USER", "saas_user")
    pwd = os.environ.get("DB_PASSWORD", "")
    name = os.environ.get("DB_NAME", "saas_lifecycle")

    try:
        import pymysql
    except ModuleNotFoundError:
        print("⚠️  未安装 pymysql。请先： pip install -r requirements.txt")
        print("    下一条命令： python scripts/check_mysql_connection.py")
        return 2

    try:
        conn = pymysql.connect(host=host, port=port, user=user, password=pwd,
                               charset="utf8mb4", connect_timeout=5)
    except Exception as e:  # noqa: BLE001
        print(f"❌ 连接 MySQL 失败：{e}")
        print("排查：① MySQL 是否已启动；② host/port 是否正确；③ 账号密码是否正确；")
        print(f"     ④ 用户 {user} 是否有权限（GRANT ALL ON {name}.* TO '{user}'@'%'）。")
        print("修正后重跑： python scripts/check_mysql_connection.py")
        return 1

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION()")
            ver = cur.fetchone()[0]
            cur.execute("SELECT @@character_set_server, @@collation_server")
            cs, coll = cur.fetchone()
            cur.execute("SHOW DATABASES LIKE %s", (name,))
            db_exists = cur.fetchone() is not None
        print(f"✅ 连接成功  MySQL {ver}")
        print(f"   服务器字符集={cs} 排序={coll}")
        print(f"   目标库 `{name}` 是否已存在：{'是' if db_exists else '否（下一步跑 init_mysql_db.py 建库建表）'}")
        if not db_exists:
            print("   下一条命令： python scripts/init_mysql_db.py")
        else:
            print("   下一条命令（如需灌数据）： python scripts/seed_mysql_demo_data.py")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
