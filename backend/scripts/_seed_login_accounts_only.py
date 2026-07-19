"""仅写入登录所需演示账号（租户 + admin/teacher/student），不跑全量业务种子。"""
from __future__ import annotations

import json

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models import Tenant, TenantBrandConfig, User

DEMO_TID = 1000000000000000003
DEMO_CODE = "demo-school"
DEMO_NAME = "演示职业技术学校"
SANDBOX_TID = 1000000000000000007
SANDBOX_CODE = "sandbox-school"
SANDBOX_NAME = "体验沙箱学校"

ACCOUNTS = [
    (DEMO_TID, DEMO_CODE, DEMO_NAME, "演示职校", "admin", "陈管理", "ADMIN"),
    (DEMO_TID, DEMO_CODE, DEMO_NAME, "演示职校", "teacher", "李导师", "TEACHER"),
    (DEMO_TID, DEMO_CODE, DEMO_NAME, "演示职校", "student", "张同学", "STUDENT"),
    (SANDBOX_TID, SANDBOX_CODE, SANDBOX_NAME, "沙箱职校", "admin2", "沙箱管理", "ADMIN"),
    (SANDBOX_TID, SANDBOX_CODE, SANDBOX_NAME, "沙箱职校", "teacher2", "王老师", "TEACHER"),
    (SANDBOX_TID, SANDBOX_CODE, SANDBOX_NAME, "沙箱职校", "student2", "李体验", "STUDENT"),
]


def _ensure_tenant(db, tid: int, code: str, name: str, short: str) -> None:
    t = db.get(Tenant, tid)
    if t is None:
        db.add(
            Tenant(
                id=tid,
                tenant_code=code,
                school_name=name,
                short_name=short,
                status="ACTIVE",
            )
        )
        db.add(
            TenantBrandConfig(
                tenant_id=tid,
                platform_name="高校学生全生命周期管理平台",
                browser_title="高校学生全生命周期管理平台",
                primary_color="#2563EB",
                default_theme="academy_blue",
                watermark_text=short,
            )
        )
        db.flush()


def seed_login_accounts(db) -> dict:
    created = []
    for tid, code, name, short, login, rname, utype in ACCOUNTS:
        _ensure_tenant(db, tid, code, name, short)
        u = db.scalars(
            select(User).where(User.login_name == login, User.is_deleted.is_(False))
        ).first()
        if u is None:
            db.add(
                User(
                    tenant_id=tid,
                    login_name=login,
                    real_name=rname,
                    password_hash=hash_password("123456"),
                    user_type=utype,
                    status="ACTIVE",
                )
            )
            created.append(login)
    db.commit()
    return {"created": created, "password": "123456"}


if __name__ == "__main__":
    db = get_sessionmaker()()
    try:
        print(json.dumps(seed_login_accounts(db), ensure_ascii=False, indent=2))
    finally:
        db.close()
