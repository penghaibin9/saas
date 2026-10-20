"""归档封存与双人纠错的真实权限、范围和任职，仅用于隔离数据库测试。"""
from datetime import datetime


def seed_archive_operator(db, tenant_id, login, user_id=None):
    from app.models import Role, RoleAssignmentScope, RolePermission, StaffAssignment, User, UserRole
    from tests.support_academic_review_identity import _ensure_permission

    user = db.query(User).filter(User.tenant_id == tenant_id, User.login_name == login).first()
    if user is None:
        user = User(id=user_id, tenant_id=tenant_id, login_name=login, real_name=login,
            password_hash="unused-in-service-test", user_type="SCHOOL_ADMIN", status="ACTIVE")
        db.add(user); db.flush()
    role = db.query(Role).filter(Role.tenant_id == tenant_id, Role.role_code == "V5_ARCHIVE_OPERATOR").first()
    if role is None:
        role = Role(tenant_id=tenant_id, role_code="V5_ARCHIVE_OPERATOR", role_name="归档责任测试岗位",
            role_type="CUSTOM", status="ACTIVE")
        db.add(role); db.flush()
    link = db.query(UserRole).filter(UserRole.tenant_id == tenant_id,
        UserRole.user_id == user.id, UserRole.role_id == role.id).first()
    if link is None:
        link = UserRole(tenant_id=tenant_id, user_id=user.id, role_id=role.id, status="ACTIVE")
        db.add(link); db.flush()
    for code in ("academicAffairs.archive.view", "academicAffairs.archive.manage"):
        permission = _ensure_permission(db, code)
        if not db.query(RolePermission).filter(RolePermission.tenant_id == tenant_id,
                RolePermission.role_id == role.id, RolePermission.permission_id == permission.id).first():
            db.add(RolePermission(tenant_id=tenant_id, role_id=role.id,
                permission_id=permission.id, status="ACTIVE"))
    if not db.query(RoleAssignmentScope).filter(RoleAssignmentScope.tenant_id == tenant_id,
            RoleAssignmentScope.user_role_id == link.id).first():
        db.add(RoleAssignmentScope(tenant_id=tenant_id, user_id=user.id, user_role_id=link.id,
            role_code=role.role_code, scope_type="SCHOOL", scope_id=0,
            effective_at=datetime(2020, 1, 1), status="ACTIVE"))
    if not db.query(StaffAssignment).filter(StaffAssignment.tenant_id == tenant_id,
            StaffAssignment.user_id == user.id, StaffAssignment.org_type == "SCHOOL",
            StaffAssignment.assignment_type == "ACADEMIC_REVIEWER").first():
        db.add(StaffAssignment(tenant_id=tenant_id, user_id=user.id, org_type="SCHOOL",
            org_node_id=tenant_id, assignment_type="ACADEMIC_REVIEWER",
            effective_at=datetime(2020, 1, 1), status="ACTIVE"))
    db.flush()
    return {"userId": str(user.id), "loginName": login, "realName": login,
        "tenantId": str(tenant_id), "userType": "SCHOOL_ADMIN", "currentRoleCode": role.role_code,
        "activeContextId": f"role:{role.id}"}
