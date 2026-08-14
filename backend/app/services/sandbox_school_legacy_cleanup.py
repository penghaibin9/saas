"""standard-20k 沙箱旧假身份清洗。

全量重建会按 tenant 清空业务表，但出于登录/RBAC安全原因历史 reset 会保留 t_user/t_role/t_user_role。
因此旧的小规模教务 seed 曾创建的固定教师账号可能跨重建残留。本模块只识别高置信旧种子身份，
不按姓名、学号或通用 teacher 前缀猜测，避免误删当前真实试点账号。
"""
from __future__ import annotations

from sqlalchemy import delete, func, or_, select

LEGACY_ACADEMIC_DEMO_LOGINS = (
    "t_dong_kejian",
    "t_luo_yaqin",
    "t_wu_zhigang",
    "t_he_xiaoyan",
    "t_zhou_bin",
    "t_tan_weiguo",
    "t_peng_lina",
    "t_liu_zhiqiang",
    "t_chen_xiaoli",
    "t_huang_junfeng",
    "t_zeng_fang",
    "t_liang_shuqin",
    "t_xie_yumei",
    "t_deng_haiyan",
    "t_lin_xiaofeng",
    "t_ma_yuling",
)
LEGACY_EXACT_LOGINS = LEGACY_ACADEMIC_DEMO_LOGINS + ("demo_intern_mentor",)
LEGACY_PASSWORD_MARKER = "demo-not-a-real-login"


def _legacy_users(db, tenant_id: int):
    from app.models import User

    return list(db.scalars(select(User).where(
        User.tenant_id == tenant_id,
        User.is_deleted.is_(False),
        or_(
            User.login_name.in_(LEGACY_EXACT_LOGINS),
            User.password_hash.like(f"%{LEGACY_PASSWORD_MARKER}%"),
        ),
    ).order_by(User.id)).all())


def legacy_identity_report(db, tenant_id: int) -> dict:
    from app.models import UserRole

    users = _legacy_users(db, tenant_id)
    ids = [int(row.id) for row in users]
    bindings = 0
    if ids:
        bindings = int(db.scalar(select(func.count()).select_from(UserRole).where(
            UserRole.tenant_id == tenant_id,
            UserRole.user_id.in_(ids),
        )) or 0)
    return {
        "legacyUsers": len(users),
        "legacyUserRoles": bindings,
        "legacyLogins": [row.login_name for row in users],
        "passed": len(users) == 0 and bindings == 0,
    }


def clean_legacy_identity_residue(db, tenant_id: int) -> dict:
    """删除高置信旧种子账号及其角色绑定；只允许固定 sandbox-school。"""
    from app.models import AuthRefreshToken, User, UserRole
    from app.services.sandbox_service import SANDBOX_TID, _assert_target_is_sandbox

    if tenant_id != SANDBOX_TID:
        raise RuntimeError("旧沙箱身份清洗只允许固定 sandbox-school")
    _assert_target_is_sandbox(db)

    before = legacy_identity_report(db, tenant_id)
    users = _legacy_users(db, tenant_id)
    ids = [int(row.id) for row in users]
    if not ids:
        return {"before": before, "removedUsers": 0, "removedUserRoles": 0, "revokedRefreshTokens": 0,
                "after": before}

    refresh_ids = [f"db-{uid}" for uid in ids]
    refresh_res = db.execute(delete(AuthRefreshToken).where(AuthRefreshToken.user_id.in_(refresh_ids)))
    role_res = db.execute(delete(UserRole).where(
        UserRole.tenant_id == tenant_id,
        UserRole.user_id.in_(ids),
    ))
    user_res = db.execute(delete(User).where(
        User.tenant_id == tenant_id,
        User.id.in_(ids),
    ))
    db.commit()
    after = legacy_identity_report(db, tenant_id)
    if not after["passed"]:
        raise RuntimeError(f"旧沙箱身份清洗后仍有残留: {after}")
    return {
        "before": before,
        "removedUsers": int(user_res.rowcount or 0),
        "removedUserRoles": int(role_res.rowcount or 0),
        "revokedRefreshTokens": int(refresh_res.rowcount or 0),
        "after": after,
    }


def validate_no_legacy_identity_residue(db, tenant_id: int) -> dict:
    report = legacy_identity_report(db, tenant_id)
    if not report["passed"]:
        raise RuntimeError(f"standard-20k 仍含旧假身份数据: {report}")
    return report
