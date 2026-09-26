"""教务课程/培养方案两级审核的真实学院身份夹具。

仅为真库 E2E 种出当前 Authority 已要求的最小事实：
- college_admin01 具备课程学院审核、培养方案学院审核的 DB 权限；
- college_admin01 通过 TeacherStudentScope 显式绑定到目标学院，并有有效秘书任职；
- 培养方案两级审核另补 school_admin01 的真实账号、审批权限与学校终审任职；
- 不修改生产权限映射，不给校级账号模拟学院节点，也不绕过 scope 校验。
"""
from __future__ import annotations

from datetime import datetime

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


def _ensure_review_account(db, *, login_name, real_name, role_code, permissions):
    """仅补齐本组显式调用的真实审核账号及具体审批权限。"""
    from app.models import Role, RolePermission, User, UserRole

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
            user_type="SCHOOL_ADMIN",
            status="ACTIVE",
        )
        db.add(user)
        db.flush()
    else:
        user.status = "ACTIVE"
        user.is_deleted = False

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

    for code in permissions:
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
    return user


def _ensure_review_assignment(db, *, user_id, org_type, org_id, assignment_type):
    from app.models import StaffAssignment

    row = db.query(StaffAssignment).filter(
        StaffAssignment.tenant_id == TID,
        StaffAssignment.user_id == int(user_id),
        StaffAssignment.org_type == org_type,
        StaffAssignment.org_node_id == int(org_id),
        StaffAssignment.assignment_type == assignment_type,
    ).order_by(StaffAssignment.id).first()
    if row is None:
        row = StaffAssignment(
            tenant_id=TID, user_id=int(user_id), org_type=org_type,
            org_node_id=int(org_id), assignment_type=assignment_type,
            effective_at=datetime(2020, 1, 1), source_type="MANUAL",
            reason="课程与培养方案真库回归：当前两级审核岗位",
        )
        db.add(row)
    row.status = "ACTIVE"
    row.is_deleted = False
    row.is_primary = True
    row.expires_at = None
    if row.effective_at is None or row.effective_at > datetime.utcnow():
        row.effective_at = datetime(2020, 1, 1)
    db.flush()


def seed_college_review_scope(db, *, college_ids=(), major_ids=()) -> list[int]:
    """把 college_admin01 显式绑定到指定学院/专业所属学院，返回实际学院 id。"""
    from app.models import College, Major, TeacherStudentScope

    reviewer = _ensure_review_account(
        db, login_name=COLLEGE_LOGIN, real_name="张晓明", role_code=COLLEGE_ROLE,
        permissions=(COURSE_REVIEW_PERMISSION, PROGRAM_REVIEW_PERMISSION),
    )
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
        _ensure_review_assignment(
            db, user_id=reviewer.id, org_type="COLLEGE", org_id=college.id,
            assignment_type="SECRETARY",
        )
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
    """培养方案 HTTP 接力前补齐两级责任，提交后供独立权限会话读取。"""
    from app.db.session import get_sessionmaker

    db = get_sessionmaker()()
    try:
        resolved = seed_college_review_scope(db, college_ids=college_ids, major_ids=major_ids)
        school = _ensure_review_account(
            db, login_name="school_admin01", real_name="陈校", role_code="SCHOOL_ADMIN",
            permissions=(PROGRAM_REVIEW_PERMISSION,),
        )
        _ensure_review_assignment(
            db, user_id=school.id, org_type="SCHOOL", org_id=TID,
            assignment_type="ACADEMIC_REVIEWER",
        )
        db.commit()
        return resolved
    finally:
        db.close()
