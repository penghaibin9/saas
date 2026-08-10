"""成绩审核真实受理人与有效成绩策略夹具。

成绩提交/发布已经 fail-closed：工作流节点必须解析到真实启用账号，正式成绩也必须冻结生效策略。
本模块只为真库端到端测试种出与生产一致的最小事实图，不修改生产权限或策略判断：
- 学院审核：学院 secretary_id 对应启用账号，并通过角色持有 academicAffairs.grade.collegeReview；
- 教务终审：唯一校级启用账号通过角色持有 academicAffairs.grade.publish，且不绑定学院范围；
- 正式成绩：租户至少存在一条 ACTIVE BASE 策略，发布时仍由生产 resolver 正常解析并冻结快照。
"""
from __future__ import annotations

from datetime import datetime

TID = 1000000000000000001
COLLEGE_REVIEW_PERM = "academicAffairs.grade.collegeReview"
ACADEMIC_PUBLISH_PERM = "academicAffairs.grade.publish"

_ACCOUNTS = {
    "college_admin01": ("张晓明", "SCHOOL_ADMIN", (COLLEGE_REVIEW_PERM,)),
    "school_admin01": ("陈校", "SCHOOL_ADMIN", (ACADEMIC_PUBLISH_PERM,)),
}


def _ensure_permission(db, code):
    from app.models import Permission

    row = db.query(Permission).filter(Permission.permission_code == code).first()
    if row is None:
        row = Permission(
            permission_code=code,
            permission_name=code,
            module_code="academicAffairs",
            action="REVIEW",
        )
        db.add(row)
        db.flush()
    return row


def _ensure_account(db, login_name):
    from app.models import Role, RolePermission, User, UserRole

    real_name, user_type, permissions = _ACCOUNTS[login_name]
    user = db.query(User).filter(
        User.tenant_id == TID,
        User.login_name == login_name,
    ).first()
    if user is None:
        user = User(
            tenant_id=TID,
            login_name=login_name,
            real_name=real_name,
            password_hash="x",
            user_type=user_type,
            status="ACTIVE",
        )
        db.add(user)
        db.flush()

    role_code = f"TEST_GRADE_{login_name.upper()}"
    role = db.query(Role).filter(
        Role.tenant_id == TID,
        Role.role_code == role_code,
    ).first()
    if role is None:
        role = Role(
            tenant_id=TID,
            role_code=role_code,
            role_name=role_code,
            status="ACTIVE",
        )
        db.add(role)
        db.flush()

    if db.query(UserRole).filter(
        UserRole.tenant_id == TID,
        UserRole.user_id == user.id,
        UserRole.role_id == role.id,
    ).first() is None:
        db.add(UserRole(
            tenant_id=TID,
            user_id=user.id,
            role_id=role.id,
            status="ACTIVE",
        ))

    for code in permissions:
        permission = _ensure_permission(db, code)
        if db.query(RolePermission).filter(
            RolePermission.tenant_id == TID,
            RolePermission.role_id == role.id,
            RolePermission.permission_id == permission.id,
        ).first() is None:
            db.add(RolePermission(
                tenant_id=TID,
                role_id=role.id,
                permission_id=permission.id,
                status="ACTIVE",
            ))
    db.flush()
    return user


def _ensure_base_grade_policy(db):
    """种出生产允许的租户级 BASE 策略；禁止用 bypass 绕过正式成绩策略冻结。"""
    from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicy

    row = db.query(AaEffectiveGradePolicy).filter(
        AaEffectiveGradePolicy.tenant_id == TID,
        AaEffectiveGradePolicy.status == "ACTIVE",
        AaEffectiveGradePolicy.active_scope_key == "BASE",
        AaEffectiveGradePolicy.is_deleted.is_(False),
    ).first()
    if row is None:
        row = AaEffectiveGradePolicy(
            tenant_id=TID,
            policy_code="TEST_BASE_POLICY",
            policy_version=1,
            active_scope_key="BASE",
            attempt_strategy="LATEST_ATTEMPT",
            makeup_strategy="CAP_AND_OVERRIDE",
            makeup_cap=60,
            retake_strategy="REPLACE_IF_PASSED",
            recognition_priority=75,
            effective_from_term_id=None,
            status="ACTIVE",
            activated_at=datetime.utcnow(),
        )
        db.add(row)
        db.flush()
    return row


def seed_grade_review_identity(db, *, college_ids=()):
    """种出成绩审核两级真实受理人、学院绑定和 ACTIVE BASE 成绩策略。"""
    from app.models import College

    users = {name: _ensure_account(db, name) for name in _ACCOUNTS}
    _ensure_base_grade_policy(db)
    for college_id in college_ids:
        college = db.get(College, int(college_id))
        if college is not None:
            college.secretary_id = int(users["college_admin01"].id)
    db.flush()
    return {name: int(user.id) for name, user in users.items()}
