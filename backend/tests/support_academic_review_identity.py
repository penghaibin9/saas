"""教务课程/培养方案两级审核的真实学院身份夹具。

仅为真库 E2E 种出当前 Authority 已要求的最小事实：
- college_admin01 具备课程学院审核、培养方案学院审核的 DB 权限；
- college_admin01 通过 TeacherStudentScope 显式绑定到目标学院；
- 不修改生产权限映射，不给校级账号模拟学院节点，也不绕过 scope 校验。
"""
from __future__ import annotations

TID = 1000000000000000001
COLLEGE_LOGIN = "college_admin01"
COLLEGE_ROLE = "COLLEGE_ADMIN"
COURSE_REVIEW_PERMISSION = "academicAffairs.course.approve"
PROGRAM_REVIEW_PERMISSION = "academicAffairs.program.review"


def _ensure_permission(db, code: str):
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


def _ensure_college_reviewer_permissions(db) -> None:
    """若真库已有 college_admin01 账号，则补齐本组 E2E 所需的两个正式审批权限。"""
    from app.models import Role, RolePermission, User, UserRole

    user = db.query(User).filter(
        User.tenant_id == TID,
        User.login_name == COLLEGE_LOGIN,
        User.is_deleted.is_(False),
    ).first()
    if user is None:
        user = User(
            tenant_id=TID,
            login_name=COLLEGE_LOGIN,
            real_name="张晓明",
            password_hash="x",
            user_type="SCHOOL_ADMIN",
            status="ACTIVE",
        )
        db.add(user)
        db.flush()
    else:
        user.status = "ACTIVE"

    role = db.query(Role).filter(
        Role.tenant_id == TID,
        Role.role_code == COLLEGE_ROLE,
    ).first()
    if role is None:
        role = Role(
            tenant_id=TID,
            role_code=COLLEGE_ROLE,
            role_name=COLLEGE_ROLE,
            status="ACTIVE",
        )
        db.add(role)
        db.flush()
    else:
        role.status = "ACTIVE"
        role.is_deleted = False

    link = db.query(UserRole).filter(
        UserRole.tenant_id == TID,
        UserRole.user_id == user.id,
        UserRole.role_id == role.id,
    ).first()
    if link is None:
        db.add(UserRole(
            tenant_id=TID,
            user_id=user.id,
            role_id=role.id,
            status="ACTIVE",
        ))
    else:
        link.status = "ACTIVE"
        link.is_deleted = False

    for code in (COURSE_REVIEW_PERMISSION, PROGRAM_REVIEW_PERMISSION):
        permission = _ensure_permission(db, code)
        grant = db.query(RolePermission).filter(
            RolePermission.tenant_id == TID,
            RolePermission.role_id == role.id,
            RolePermission.permission_id == permission.id,
        ).first()
        if grant is None:
            db.add(RolePermission(
                tenant_id=TID,
                role_id=role.id,
                permission_id=permission.id,
                status="ACTIVE",
            ))
        else:
            grant.status = "ACTIVE"
            grant.is_deleted = False
    db.flush()


def seed_college_review_scope(db, *, college_ids=(), major_ids=()) -> list[int]:
    """把 college_admin01 显式绑定到指定学院/专业所属学院，返回实际学院 id。"""
    from app.models import College, Major, TeacherStudentScope

    _ensure_college_reviewer_permissions(db)
    resolved = {int(value) for value in college_ids if value not in (None, "")}
    for major_id in major_ids:
        if major_id in (None, ""):
            continue
        major = db.query(Major).filter(
            Major.id == int(major_id),
            Major.tenant_id == TID,
            Major.is_deleted.is_(False),
        ).first()
        if major is not None and major.college_id:
            resolved.add(int(major.college_id))

    for college_id in sorted(resolved):
        college = db.query(College).filter(
            College.id == int(college_id),
            College.tenant_id == TID,
            College.is_deleted.is_(False),
        ).first()
        if college is None:
            continue
        row = db.query(TeacherStudentScope).filter(
            TeacherStudentScope.tenant_id == TID,
            TeacherStudentScope.teacher_key == COLLEGE_LOGIN,
            TeacherStudentScope.role_code == COLLEGE_ROLE,
            TeacherStudentScope.scope_type == "COLLEGE",
            TeacherStudentScope.ref_value == college.college_name,
            TeacherStudentScope.is_deleted.is_(False),
        ).first()
        if row is None:
            row = TeacherStudentScope(
                tenant_id=TID,
                teacher_key=COLLEGE_LOGIN,
                role_code=COLLEGE_ROLE,
                scope_type="COLLEGE",
                ref_value=college.college_name,
                status="ACTIVE",
            )
            db.add(row)
        else:
            row.status = "ACTIVE"
    db.flush()
    return sorted(resolved)


def ensure_course_review_college() -> int:
    """为无组织前置的课程回归创建稳定开课学院并授予真实学院审核 scope。"""
    from app.db.session import get_sessionmaker
    from app.models import College

    db = get_sessionmaker()()
    try:
        college = db.query(College).filter(
            College.tenant_id == TID,
            College.code == "PYTEST_AA_COURSE_REVIEW",
            College.is_deleted.is_(False),
        ).first()
        if college is None:
            college = College(
                tenant_id=TID,
                college_name="教务课程审核回归学院",
                code="PYTEST_AA_COURSE_REVIEW",
                status="ACTIVE",
            )
            db.add(college)
            db.flush()
        seed_college_review_scope(db, college_ids=[college.id])
        college_id = int(college.id)
        db.commit()
        return college_id
    finally:
        db.close()


def ensure_college_review_scope(*, college_ids=(), major_ids=()) -> list[int]:
    """独立事务版本，供 HTTP helper 在提交审核前补齐真实 scope。"""
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        resolved = seed_college_review_scope(db, college_ids=college_ids, major_ids=major_ids)
        db.commit()
        return resolved
    finally:
        db.close()
