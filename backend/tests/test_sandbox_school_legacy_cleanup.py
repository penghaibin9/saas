"""旧假身份清洗数据库合同：先识别历史残留、再造脏，证明只删高置信旧 seed 身份。"""
from __future__ import annotations


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
