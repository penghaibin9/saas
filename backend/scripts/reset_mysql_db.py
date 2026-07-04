"""重置 MySQL 演示库：DROP DATABASE 后重建空库（utf8mb4）。⚠️ 会清空数据。

多重安全闸（任一不满足即拒绝，绝不误删生产库）：
  1) 必须显式 CONFIRM_RESET_MYSQL=YES（缺失即拒绝）。
  2) 只会操作 .env 里配置的 DB_NAME（默认 saas_lifecycle）；不接受命令行随意指定别的库。
  3) 若 DB_NAME 命中疑似生产关键词（prod/product/online/master…）直接拒绝。
  4) 需要 MySQL 密码；缺失即拒绝。
用法（PowerShell 示例）：
    $env:CONFIRM_RESET_MYSQL="YES"; python scripts/reset_mysql_db.py
"""
from __future__ import annotations

import os

import _mysql_env  # noqa: F401

PROD_HINTS = ("prod", "product", "online", "master", "release", "正式", "生产")


def main() -> int:
    name = os.environ.get("DB_NAME", "saas_lifecycle")
    print(f"[reset] 目标库：{name}    {_mysql_env.describe()}")

    # 闸 1：二次确认变量
    if os.environ.get("CONFIRM_RESET_MYSQL") != "YES":
        print("⛔ 已阻止：未设置 CONFIRM_RESET_MYSQL=YES。")
        print("   这是清库高危操作，必须显式确认。PowerShell：")
        print('   $env:CONFIRM_RESET_MYSQL="YES"; python scripts/reset_mysql_db.py')
        return 3

    # 闸 3：生产关键词保护
    low = name.lower()
    if any(h in low for h in PROD_HINTS):
        print(f"⛔ 已阻止：库名 `{name}` 命中疑似生产关键词，拒绝重置。")
        print("   如确属演示库，请改用不含 prod/online/master 等词的库名。")
        return 3

    # 闸 4：密码
    if _mysql_env.password_missing():
        print("⛔ 已阻止：未检测到 MySQL 密码。请在 backend/.env 填 DB_PASSWORD 后重跑。")
        return 2

    host = os.environ.get("DB_HOST", "127.0.0.1")
    port = int(os.environ.get("DB_PORT", "3306"))
    user = os.environ.get("DB_USER", "saas_user")
    pwd = os.environ.get("DB_PASSWORD", "")

    try:
        import pymysql
    except ModuleNotFoundError:
        print("⚠️  未安装 pymysql。请先 pip install -r requirements.txt。")
        return 2
    try:
        conn = pymysql.connect(host=host, port=port, user=user, password=pwd,
                               charset="utf8mb4", connect_timeout=5)
    except Exception as e:  # noqa: BLE001
        print(f"❌ 连接 MySQL 失败：{e}")
        return 1
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
            cur.execute(
                f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
        print(f"[reset] 已重建空库 `{name}`（utf8mb4）。")
        print("下一条命令： python scripts/init_mysql_db.py && python scripts/seed_mysql_demo_data.py")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
