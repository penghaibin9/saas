"""一键初始化本地 SQLite 开发库 + 造演示学生登录账号 + 基础档案。

用途：个人(无 MySQL)本地联调学生 PC 门户。SQLite 仅供开发/联调，非 MySQL 正式验收。
用法：
    cd backend
    python scripts/seed_dev_student.py
产出：
    - backend/data/dev.db（SQLite，全部表已建）
    - 学生登录账号：student / 123456（学校编码 demo-school）
随后：
    DB_ENABLED=true DATABASE_URL=sqlite+pysqlite:///./data/dev.db MOCK_LOGIN_ENABLED=true \
      uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import _dev_env  # noqa: F401  设置 SQLite backend/data/dev.db + DB_ENABLED=true

from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import metadata
from app.db.session import get_engine, get_sessionmaker, reset_state

DEMO_TID = 1000000000000000003
DEMO_CODE = "demo-school"
DEMO_NAME = "演示职业技术学校"


def main() -> dict:
    reset_state()
    engine = get_engine()
    metadata.create_all(bind=engine)  # 幂等建表

    from app.models import StudentProfile, Tenant, TenantBrandConfig, User
    db = get_sessionmaker()()
    created = []
    try:
        if db.get(Tenant, DEMO_TID) is None:
            db.add(Tenant(id=DEMO_TID, tenant_code=DEMO_CODE, school_name=DEMO_NAME,
                          short_name="演示职校", status="ACTIVE"))
            db.add(TenantBrandConfig(tenant_id=DEMO_TID,
                                     platform_name="高校学生全生命周期管理平台",
                                     browser_title="高校学生全生命周期管理平台",
                                     primary_color="#2563EB", default_theme="academy_blue",
                                     watermark_text="演示职校"))
            db.flush()
            created.append("tenant:demo-school")

        if db.scalars(select(User).where(User.login_name == "student",
                                         User.is_deleted.is_(False))).first() is None:
            db.add(User(tenant_id=DEMO_TID, login_name="student", real_name="张同学",
                        password_hash=hash_password("123456"), user_type="STUDENT",
                        status="ACTIVE", must_change_password=False))
            created.append("user:student")

        if db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == DEMO_TID, StudentProfile.real_name == "张同学",
                StudentProfile.is_deleted.is_(False))).first() is None:
            db.add(StudentProfile(tenant_id=DEMO_TID, student_no="DEMO2024001", real_name="张同学",
                                  gender="M", grade="2024", current_stage="ENROLLED",
                                  student_status="NORMAL", status="ACTIVE"))
            created.append("studentProfile:张同学")

        db.commit()
    finally:
        db.close()
    return {"db": str(engine.url), "created": created,
            "login": "student / 123456", "tenantCode": DEMO_CODE}


if __name__ == "__main__":
    import json
    print(json.dumps(main(), ensure_ascii=False, indent=2))
