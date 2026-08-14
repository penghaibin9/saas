"""旧假身份清洗数据库合同：先识别历史残留、再造脏，证明只删高置信旧 seed 身份。"""
from __future__ import annotations

import os

import pytest


def test_legacy_identity_cleanup_removes_only_old_seed_account(db_mode):
    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models import Role, User, UserRole
    from app.services.sandbox_service import SANDBOX_TID, seed_sandbox
    from app.services.sandbox_school_legacy_cleanup import (
        LEGACY_PASSWORD_MARKER,
        clean_legacy_identity_residue,
        legacy_identity_report,
    )

    db = get_sessionmaker()()
    try:
        seed_sandbox(db)
        fixed_before = {
            row.login_name: int(row.id)
            for row in db.scalars(select(User).where(
                User.tenant_id == SANDBOX_TID,
                User.login_name.in_(("admin2", "teacher2", "student2")),
                User.is_deleted.is_(False),
            )).all()
        }
        assert set(fixed_before) == {"admin2", "teacher2", "student2"}

        # legacy-100 自己就会经旧岗位实习种子产生 demo_intern_mentor；
        # 这正是 standard-20k 重建时必须清掉的历史残留，不能在测试里假装基线为 0。
        baseline = legacy_identity_report(db, SANDBOX_TID)
        assert baseline["legacyUsers"] >= 1
        assert "demo_intern_mentor" in baseline["legacyLogins"]
        assert baseline["passed"] is False

        role = db.scalars(select(Role).where(
            Role.tenant_id == SANDBOX_TID,
            Role.role_code == "SCHOOL_ADMIN",
            Role.is_deleted.is_(False),
        )).one()
        insert_result = db.execute(User.__table__.insert().values(
            tenant_id=SANDBOX_TID,
            login_name="t_dong_kejian",
            real_name="历史假教师",
            password_hash=f"pbkdf2_sha256$200000$demo${LEGACY_PASSWORD_MARKER}",
            user_type="TEACHER",
            status="ACTIVE",
            must_change_password=False,
            is_deleted=False,
            version=0,
        ))
        legacy_user_id = int(insert_result.inserted_primary_key[0])
        db.execute(UserRole.__table__.insert().values(
            tenant_id=SANDBOX_TID,
            user_id=legacy_user_id,
            role_id=int(role.id),
            status="ACTIVE",
            is_deleted=False,
            version=0,
        ))
        db.commit()

        dirty = legacy_identity_report(db, SANDBOX_TID)
        assert dirty["legacyUsers"] == baseline["legacyUsers"] + 1
        assert dirty["legacyUserRoles"] == baseline["legacyUserRoles"] + 1
        assert "t_dong_kejian" in dirty["legacyLogins"]
        assert dirty["passed"] is False

        result = clean_legacy_identity_residue(db, SANDBOX_TID)
        assert result["removedUsers"] == dirty["legacyUsers"]
        assert result["removedUserRoles"] == dirty["legacyUserRoles"]
        assert result["after"]["legacyUsers"] == 0
        assert result["after"]["legacyUserRoles"] == 0
        assert result["after"]["passed"] is True

        fixed_after = {
            row.login_name: int(row.id)
            for row in db.scalars(select(User).where(
                User.tenant_id == SANDBOX_TID,
                User.login_name.in_(("admin2", "teacher2", "student2")),
                User.is_deleted.is_(False),
            )).all()
        }
        assert fixed_after == fixed_before
    finally:
        db.close()


def test_legacy_identity_cleanup_never_touches_pilot_tenant(db_mode):
    """即使真实试点租户碰巧存在同名/同 marker 账号，也只能清 sandbox-school。"""
    from sqlalchemy import select

    from app.db.session import get_sessionmaker
    from app.models import Tenant, User
    from app.services.sandbox_service import SANDBOX_TID, seed_sandbox
    from app.services.sandbox_school_legacy_cleanup import (
        LEGACY_PASSWORD_MARKER,
        clean_legacy_identity_residue,
    )

    db = get_sessionmaker()()
    try:
        seed_sandbox(db)
        pilot = Tenant(
            tenant_code="pilot-protection-school",
            school_name="真实试点保护学校",
            short_name="试点保护校",
            deploy_mode="SAAS",
            db_mode="SHARED",
            status="ACTIVE",
        )
        db.add(pilot)
        db.flush()
        pilot_tid = int(pilot.id)
        assert pilot_tid != SANDBOX_TID

        insert_result = db.execute(User.__table__.insert().values(
            tenant_id=pilot_tid,
            login_name="t_dong_kejian",
            real_name="试点真实教师",
            password_hash=f"pbkdf2_sha256$200000$pilot${LEGACY_PASSWORD_MARKER}",
            user_type="TEACHER",
            status="ACTIVE",
            must_change_password=False,
            is_deleted=False,
            version=0,
        ))
        pilot_user_id = int(insert_result.inserted_primary_key[0])
        db.commit()

        clean_legacy_identity_residue(db, SANDBOX_TID)
        pilot_user = db.scalars(select(User).where(
            User.id == pilot_user_id,
            User.tenant_id == pilot_tid,
            User.login_name == "t_dong_kejian",
            User.is_deleted.is_(False),
        )).one_or_none()
        assert pilot_user is not None
        assert pilot_user.real_name == "试点真实教师"

        with pytest.raises(RuntimeError, match="只允许固定 sandbox-school"):
            clean_legacy_identity_residue(db, pilot_tid)

        pilot_user_after_reject = db.scalars(select(User).where(
            User.id == pilot_user_id,
            User.tenant_id == pilot_tid,
            User.is_deleted.is_(False),
        )).one_or_none()
        assert pilot_user_after_reject is not None
    finally:
        db.close()


def test_20k_gate_primes_demo_school_neighbor_sentinel(db_mode):
    """专门门禁先落旁租户哨兵，让后续全量 reset 的 demo-school 前后对账真正执行。"""
    if os.getenv("GITHUB_WORKFLOW") != "Sandbox 20K Real-School Data Gate":
        pytest.skip("仅用于 20K 专门门禁的跨租户持久哨兵")

    from sqlalchemy import func, select

    from app.db.session import get_sessionmaker
    from app.models import StudentProfile, Tenant
    from scripts._seed_two_tenants import DEMO_CODE, DEMO_TID, seed_demo_tenant

    db = get_sessionmaker()()
    try:
        seed_demo_tenant(db)
        tenant = db.get(Tenant, DEMO_TID)
        assert tenant is not None
        assert tenant.tenant_code == DEMO_CODE
        student_count = int(db.scalar(
            select(func.count()).select_from(StudentProfile).where(
                StudentProfile.tenant_id == DEMO_TID,
                StudentProfile.is_deleted.is_(False),
            )
        ) or 0)
        assert student_count >= 20
        print(f"[20k-neighbor-sentinel] demo-school students={student_count}")
    finally:
        db.close()
