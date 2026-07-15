"""安全、幂等地开通 SaaS 运营平台超级管理员。

该脚本只会创建/读取 tenant_code=platform 下的一名 PLATFORM_SUPER_ADMIN，
不会建表、不会运行全量种子、不会触及任何学校租户或学生业务数据。

首次运行须通过环境变量提供密码（避免 shell 历史、Git 和日志泄露）：

  $env:PLATFORM_OWNER_INITIAL_PASSWORD = '至少12位的随机强密码'
  python scripts/bootstrap_platform_owner.py --login platform_owner --name "平台超级管理员"

若账号已存在，默认不改变密码；仅在确认需要重置时加 --reset-password。
"""
from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import db_enabled, get_sessionmaker
from app.models import Tenant, User

PLATFORM_TENANT_CODE = "platform"
PLATFORM_TENANT_NAME = "SaaS 运营平台"


def _password_from_env() -> str:
    password = os.environ.get("PLATFORM_OWNER_INITIAL_PASSWORD", "")
    if len(password) < 12:
        raise ValueError("请设置 PLATFORM_OWNER_INITIAL_PASSWORD，且长度至少 12 位")
    return password


def bootstrap(login_name: str, real_name: str, *, reset_password: bool = False) -> dict:
    if not db_enabled():
        raise RuntimeError("数据库未启用：请先在 backend/.env 配置 DB_ENABLED=true 和 MySQL 连接，再运行本脚本")
    login_name = login_name.strip()
    real_name = real_name.strip()
    if not login_name or not real_name:
        raise ValueError("--login 和 --name 均不能为空")

    db = get_sessionmaker()()
    try:
        tenant = db.scalars(select(Tenant).where(
            Tenant.tenant_code == PLATFORM_TENANT_CODE,
            Tenant.is_deleted.is_(False),
        )).first()
        if tenant is None:
            tenant = Tenant(tenant_code=PLATFORM_TENANT_CODE,
                            school_name=PLATFORM_TENANT_NAME,
                            short_name="平台运营",
                            deploy_mode="SAAS", db_mode="SHARED", status="ACTIVE")
            db.add(tenant)
            db.flush()

        user = db.scalars(select(User).where(
            User.tenant_id == tenant.id,
            User.login_name == login_name,
            User.is_deleted.is_(False),
        )).first()
        if user is not None:
            if (user.user_type or "").upper() != "PLATFORM_SUPER_ADMIN":
                raise RuntimeError("同名账号已存在但不是平台超级管理员；为防止越权，脚本已拒绝修改")
            if reset_password:
                user.password_hash = hash_password(_password_from_env())
                user.must_change_password = True
                user.version = int(user.version or 0) + 1
                action = "password_reset"
            else:
                action = "already_exists"
        else:
            user = User(tenant_id=tenant.id, login_name=login_name, real_name=real_name,
                        password_hash=hash_password(_password_from_env()),
                        user_type="PLATFORM_SUPER_ADMIN", status="ACTIVE",
                        must_change_password=True)
            db.add(user)
            action = "created"
        db.commit()
        return {"action": action, "tenantCode": PLATFORM_TENANT_CODE,
                "loginName": login_name, "role": "PLATFORM_SUPER_ADMIN"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="开通 SaaS 运营平台超级管理员（幂等，不触及学校业务数据）")
    parser.add_argument("--login", default="platform_owner", help="平台超级管理员登录名")
    parser.add_argument("--name", default="平台超级管理员", help="平台超级管理员姓名")
    parser.add_argument("--reset-password", action="store_true", help="仅对已存在的同名平台超管重置密码")
    args = parser.parse_args()
    try:
        result = bootstrap(args.login, args.name, reset_password=args.reset_password)
    except Exception as exc:  # CLI 入口：不给出数据库连接密码等敏感配置
        print(f"[platform-owner] failed: {exc}", file=sys.stderr)
        return 1
    print(f"[platform-owner] {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
