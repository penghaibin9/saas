"""毕业审核夹具的真实校院账号、权限与任职；不替换生产权限守卫。"""
from tests.support_grade_review_identity import TID, _ensure_permission, seed_grade_review_identity


def seed_graduation_review_identity(db):
    from app.models import College, Role, RolePermission
    college = db.query(College).filter(
        College.tenant_id == TID, College.college_name == "毕业审核测试学院",
        College.is_deleted.is_(False),
    ).first()
    if college is None:
        college = College(tenant_id=TID, college_name="毕业审核测试学院", status="ACTIVE")
        db.add(college); db.flush()
    seed_grade_review_identity(db, college_ids=[college.id])
    for login, permission in (
        ("college_admin01", "academicAffairs.graduation.collegeReview"),
        ("school_admin01", "academicAffairs.graduation.final"),
    ):
        role = db.query(Role).filter(
            Role.tenant_id == TID, Role.role_code == f"TEST_GRADE_{login.upper()}",
        ).one()
        grant = _ensure_permission(db, permission)
        if not db.query(RolePermission).filter(
            RolePermission.tenant_id == TID, RolePermission.role_id == role.id,
            RolePermission.permission_id == grant.id,
        ).first():
            db.add(RolePermission(tenant_id=TID, role_id=role.id, permission_id=grant.id, status="ACTIVE"))
    db.flush()
    return college
