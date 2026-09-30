"""包 5 学籍异动真实身份夹具。

异动收口为 fail-closed 之后，一次合法异动必须同时具备：
1. 唯一且可写的当前学期（否则无法冻结异动所属学期）；
2. 审批节点存在唯一真实受理人（辅导员来自班级 counselor_id，学院来自 College.secretary_id
   或 StaffAssignment，教务处来自权限成员）；
3. 受理人是 ``t_user`` 中启用的真实账号，并通过角色持有节点权限。

演示登录（mock-login）只发令牌不建账号，所以真库端到端用例必须自己把这张身份图种出来。
本模块提供 ``seed_status_change_identity``，各用例复用同一套账号与权限，不再各写一份。
"""
from __future__ import annotations

TID = 1000000000000000001

COUNSELOR_PERM = "academicAffairs.statusChange.counselorReview"
COLLEGE_PERM = "academicAffairs.statusChange.collegeReview"
OFFICE_PERM = "academicAffairs.statusChange.officeReview"

# mock-login 登录名 → (真实姓名, user_type, 该账号需要持有的审批权限)
_ACCOUNTS = {
    "counselor01": ("王莉", "TEACHER", (COUNSELOR_PERM,)),
    "college_admin01": ("张晓明", "SCHOOL_ADMIN", (COLLEGE_PERM,)),
    "school_admin01": ("陈校", "SCHOOL_ADMIN", (OFFICE_PERM,)),
}


def ensure_current_term(db, year_code="2026-2027", term_no=1):
    """保证租户内有且仅有一条 is_current 学期，并且未归档。"""
    from app.models import AaTerm

    for row in db.query(AaTerm).filter(
        AaTerm.tenant_id == TID, AaTerm.is_current.is_(True)
    ).all():
        row.is_current = False
    term = db.query(AaTerm).filter(
        AaTerm.tenant_id == TID, AaTerm.year_code == year_code, AaTerm.term_no == term_no
    ).first()
    if term is None:
        term = AaTerm(tenant_id=TID, year_code=year_code, term_no=term_no,
                      term_name=f"{year_code}学年第{term_no}学期")
        db.add(term)
    term.is_current = True
    term.status = "PUBLISHED"
    db.flush()
    return term


def _ensure_permission(db, code):
    from app.models import Permission

    row = db.query(Permission).filter(Permission.permission_code == code).first()
    if row is None:
        row = Permission(permission_code=code, permission_name=code, module_code="academicAffairs",
                         action="REVIEW")
        db.add(row)
        db.flush()
    return row


def _ensure_account(
    db,
    login_name,
    *,
    real_name=None,
    user_type=None,
    permissions=None,
):
    """建/取一个启用账号，并把它需要的审批权限经专属角色授予到位。"""
    from app.models import Role, RolePermission, User, UserRole

    if login_name in _ACCOUNTS:
        default_real_name, default_user_type, default_permissions = _ACCOUNTS[login_name]
        real_name = real_name or default_real_name
        user_type = user_type or default_user_type
        permissions = tuple(permissions or default_permissions)
    else:
        assert real_name and user_type and permissions, f"自定义测试账号缺少身份合同：{login_name}"
        permissions = tuple(permissions)

    user = db.query(User).filter(User.tenant_id == TID, User.login_name == login_name).first()
    if user is None:
        user = User(tenant_id=TID, login_name=login_name, real_name=real_name,
                    password_hash="x", user_type=user_type, status="ACTIVE")
        db.add(user)
        db.flush()
    else:
        user.real_name = real_name
        user.user_type = user_type
        user.status = "ACTIVE"
        user.is_deleted = False

    role_code = f"TEST_{login_name.upper()}"
    role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == role_code).first()
    if role is None:
        role = Role(tenant_id=TID, role_code=role_code, role_name=role_code, status="ACTIVE")
        db.add(role)
        db.flush()
    else:
        role.status = "ACTIVE"
        role.is_deleted = False
    link = db.query(UserRole).filter(
        UserRole.tenant_id == TID, UserRole.user_id == user.id, UserRole.role_id == role.id
    ).first()
    if link is None:
        db.add(UserRole(tenant_id=TID, user_id=user.id, role_id=role.id, status="ACTIVE"))
    else:
        link.status = "ACTIVE"
        link.is_deleted = False
    for code in permissions:
        permission = _ensure_permission(db, code)
        role_permission = db.query(RolePermission).filter(
            RolePermission.tenant_id == TID,
            RolePermission.role_id == role.id,
            RolePermission.permission_id == permission.id,
        ).first()
        if role_permission is None:
            db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=permission.id,
                                  status="ACTIVE"))
        else:
            role_permission.status = "ACTIVE"
            role_permission.is_deleted = False
    db.flush()
    return user


def seed_status_change_identity(db, *, class_ids=(), college_ids=()):
    """种出异动审批全链所需的真实身份图，返回各登录名对应的 user_id。

    默认情况下，class_ids 行政班统一设为 counselor01，保持历史测试行为。
    若测试已显式用 TeacherStudentScope 把 counselor01 限定到部分班级，则范围外班级
    必须分配独立真实辅导员，不能一边正式把班级交给 counselor01、一边又期待跨班 403。
    college_ids 仍统一由 college_admin01 作为学院节点真实受理人。
    """
    from app.models import College, SchoolClass, TeacherStudentScope

    ensure_current_term(db)
    users = {name: _ensure_account(db, name) for name in _ACCOUNTS}
    db.flush()

    explicit_default_classes: set[str] = set()
    scopes = db.query(TeacherStudentScope).filter(
        TeacherStudentScope.tenant_id == TID,
        TeacherStudentScope.teacher_key == "counselor01",
        TeacherStudentScope.role_code == "COUNSELOR",
        TeacherStudentScope.scope_type == "CLASS",
        TeacherStudentScope.status == "ACTIVE",
        TeacherStudentScope.is_deleted.is_(False),
    ).all()
    for scope in scopes:
        value = str(scope.ref_value or "").strip()
        if value:
            explicit_default_classes.add(value)
            explicit_default_classes.add(value.rstrip("班"))
            explicit_default_classes.add(value.rstrip("班") + "班")

    for class_id in class_ids:
        row = db.get(SchoolClass, int(class_id))
        if row is None:
            continue
        counselor = users["counselor01"]
        class_name = str(row.class_name or "").strip()
        if explicit_default_classes and class_name not in explicit_default_classes:
            counselor = _ensure_account(
                db,
                f"pytest_status_change_counselor_{row.id}",
                real_name=f"{class_name or row.id}测试辅导员",
                user_type="TEACHER",
                permissions=(COUNSELOR_PERM,),
            )
        row.counselor_id = int(counselor.id)
    for college_id in college_ids:
        row = db.get(College, int(college_id))
        if row is not None:
            row.secretary_id = int(users["college_admin01"].id)
    db.flush()
    return {name: int(user.id) for name, user in users.items()}
