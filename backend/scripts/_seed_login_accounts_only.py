"""Local/CI login accounts with explicit UserRole links; never run in production."""
from __future__ import annotations

import json

import _mysql_env  # noqa: F401
from sqlalchemy import select

from app.core.config import settings
from app.core.auth_hardening_policy import strict_security_environment
from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.models import Tenant, TenantBrandConfig, User
from _seed_fixture_roles import ensure_fixture_role

PLATFORM_TID = 1000000000000000001
PLATFORM_CODE = "platform"
PLATFORM_NAME = "跃科 SaaS 运营平台"
PLATFORM_SHORT_NAME = "运营平台"
DEMO_TID = 1000000000000000003
DEMO_CODE = "demo-school"
DEMO_NAME = "演示职业技术学校"
SANDBOX_TID = 1000000000000000007
SANDBOX_CODE = "sandbox-school"
SANDBOX_NAME = "体验沙箱学校"

ACCOUNTS = [
    (PLATFORM_TID, PLATFORM_CODE, PLATFORM_NAME, PLATFORM_SHORT_NAME, "platform_admin", "平台管理员", "PLATFORM_SUPER_ADMIN", None),
    (DEMO_TID, DEMO_CODE, DEMO_NAME, "演示职校", "admin", "陈管理", "ADMIN", "SCHOOL_ADMIN"),
    (DEMO_TID, DEMO_CODE, DEMO_NAME, "演示职校", "teacher", "李导师", "TEACHER", "COUNSELOR"),
    (DEMO_TID, DEMO_CODE, DEMO_NAME, "演示职校", "student", "张同学", "STUDENT", "STUDENT"),
    (SANDBOX_TID, SANDBOX_CODE, SANDBOX_NAME, "沙箱职校", "admin2", "沙箱管理", "ADMIN", "SCHOOL_ADMIN"),
    (SANDBOX_TID, SANDBOX_CODE, SANDBOX_NAME, "沙箱职校", "teacher2", "王老师", "TEACHER", "COUNSELOR"),
    (SANDBOX_TID, SANDBOX_CODE, SANDBOX_NAME, "沙箱职校", "student2", "李体验", "STUDENT", "STUDENT"),
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
    elif t.tenant_code != code:
        raise RuntimeError("Fixture tenant ID is owned by a different tenant; refusing to overwrite")


def seed_login_accounts(db) -> dict:
    if strict_security_environment(settings):
        raise RuntimeError("Login fixture seeding is prohibited in production/staging")
    from app.services.school_iam_authority_service import converge_school_iam_authority
    converge_school_iam_authority(
        source="auth-login-e2e-explicit-roles",
        source_commit_sha="auth-login-e2e-explicit-roles",
        actor_user_id=None,
    )
    created = []
    for tid, code, name, short, login, rname, utype, role_code in ACCOUNTS:
        _ensure_tenant(db, tid, code, name, short)
        u = db.scalars(
            select(User).where(User.tenant_id == tid, User.login_name == login,
                               User.is_deleted.is_(False))
        ).first()
        if u is None:
            u = User(
                tenant_id=tid, login_name=login, real_name=rname,
                password_hash=hash_password("123456"), user_type=utype, status="ACTIVE",
            )
            db.add(u)
            db.flush()
            created.append(login)
        if role_code:
            ensure_fixture_role(db, u, role_code)
    db.commit()
    return {"created": created, "rolesExplicit": True, "fixtureOnly": True}


if __name__ == "__main__":
    db = get_sessionmaker()()
    try:
        print(json.dumps(seed_login_accounts(db), ensure_ascii=False, indent=2))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
