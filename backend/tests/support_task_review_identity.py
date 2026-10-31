"""教学任务回归的最小真实责任身份，复用已有学院范围、任职和账号夹具。"""
from __future__ import annotations

from datetime import datetime

from tests.support_academic_review_identity import TID, _ensure_permission, seed_college_review_scope
from tests.support_grade_review_identity import _ensure_college_assignment
from tests.support_schedule_change_identity import seed_schedule_change_identity


def task_reader_headers():
    """查询回归使用真实数据库角色会话，不依赖演示登录开关。"""
    from app.db.session import get_engine, get_sessionmaker
    from app.core.security import create_access_token
    from app.services.auth_service_db import _claims, _role_contexts
    from tests.support_academic_review_identity import _ensure_review_account

    assert "test" in (get_engine().url.database or "").lower()
    with get_sessionmaker()() as db:
        user = _ensure_review_account(db, login_name="task_read_query", real_name="查询验证教务员",
            role_code="ACADEMIC_ADMIN", permissions=("academicAffairs.teachingTask.view",))
        db.commit()
        contexts = _role_contexts(db, user)
        context = next(item for item in contexts if item["roleCode"] == "ACADEMIC_ADMIN")
        token = create_access_token(_claims(db, user, context, contexts, "PC"))
    return {"Authorization": "Bearer " + token}


def ensure_task_review_identity(college_id):
    from app.db.session import get_sessionmaker
    from app.models import College, Role, RolePermission, StaffAssignment, User, UserRole

    with get_sessionmaker()() as db:
        seed_college_review_scope(db, college_ids=[college_id])
        # 复用既有学校/学院真实账号及排课所需 A101 字典，不种业务完成状态。
        users = seed_schedule_change_identity(db, college_ids=[college_id])
        college_user_id = users["college_admin01"]
        college = db.get(College, int(college_id))
        college.secretary_id = college_user_id
        _ensure_college_assignment(db, college_user_id, int(college_id))
        school_user_id = users["school_admin01"]
        appointment = db.query(StaffAssignment).filter(
            StaffAssignment.tenant_id == TID, StaffAssignment.user_id == school_user_id,
            StaffAssignment.org_type == "SCHOOL", StaffAssignment.org_node_id == TID,
            StaffAssignment.assignment_type == "ACADEMIC_REVIEWER",
            StaffAssignment.is_deleted.is_(False)).first()
        if appointment is None:
            db.add(StaffAssignment(tenant_id=TID, user_id=school_user_id, org_type="SCHOOL",
                org_node_id=TID, assignment_type="ACADEMIC_REVIEWER", is_primary=True,
                effective_at=datetime(2020, 1, 1), status="ACTIVE", source_type="MANUAL",
                reason="教学任务真库回归：学校终审岗位"))

        teacher_role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == "ACADEMIC_TEACHER").first()
        if teacher_role is None:
            teacher_role = Role(tenant_id=TID, role_code="ACADEMIC_TEACHER", role_name="任课教师", role_type="CUSTOM", status="ACTIVE")
            db.add(teacher_role); db.flush()
        for login, name in (("academic01", "赵敏"), ("academic02", "李老师")):
            teacher = db.query(User).filter(User.tenant_id == TID, User.login_name == login).first()
            if teacher is None:
                teacher = User(tenant_id=TID, login_name=login, real_name=name,
                               user_type="TEACHER", password_hash="x", status="ACTIVE")
                db.add(teacher); db.flush()
            if not db.query(UserRole).filter(UserRole.tenant_id == TID, UserRole.user_id == teacher.id,
                                            UserRole.role_id == teacher_role.id).first():
                db.add(UserRole(tenant_id=TID, user_id=teacher.id, role_id=teacher_role.id, status="ACTIVE"))

        for role_code, actions in (
            ("SCHOOL_ADMIN", ("confirm",)),
            ("COLLEGE_ADMIN", ("view", "manage", "confirm", "adjust", "merge")),
            ("ACADEMIC_TEACHER", ("view", "confirm")),
        ):
            role = db.query(Role).filter(Role.tenant_id == TID, Role.role_code == role_code).one()
            for action in actions:
                permission = _ensure_permission(db, "academicAffairs.teachingTask." + action)
                if not db.query(RolePermission).filter(RolePermission.tenant_id == TID,
                    RolePermission.role_id == role.id, RolePermission.permission_id == permission.id).first():
                    db.add(RolePermission(tenant_id=TID, role_id=role.id,
                                          permission_id=permission.id, status="ACTIVE"))
        db.commit()
