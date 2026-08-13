"""20K 售前学校 · 导师账号池与角色/范围公共配置。"""
from __future__ import annotations

from sqlalchemy import select

from app.services.sandbox_school_blueprint import MAJOR_CLASS_COUNTS_PER_GRADE
from app.services.sandbox_school_master_seed import _bulk_insert
from app.services.sandbox_school_professional_reconcile import _major_specs

EXPECTED_INTERNSHIP_MENTORS = 224
EXPECTED_GRADUATION_MENTORS = 384
MAX_INTERNSHIP_STUDENTS_PER_MENTOR = 36
MAX_GRADUATION_STUDENTS_PER_MENTOR = 20


def internship_mentor_count_for_major(major_code: str) -> int:
    """每专业=该届行政班数+3；全校 128 班 → 224 名指导教师。"""
    return MAJOR_CLASS_COUNTS_PER_GRADE[major_code] + 3


def graduation_mentor_count_for_major(major_code: str) -> int:
    """每专业=该届行政班数*3；全校 128 班 → 384 名毕设导师。"""
    return MAJOR_CLASS_COUNTS_PER_GRADE[major_code] * 3


def _interleave(primary: list, secondary: list, total: int) -> list:
    out = []
    p = s = 0
    while len(out) < total:
        if p < len(primary):
            out.append(primary[p])
            p += 1
            if len(out) >= total:
                break
        if s < len(secondary):
            out.append(secondary[s])
            s += 1
        if p >= len(primary) and s >= len(secondary):
            break
    if len(out) != total:
        raise RuntimeError(f"导师账号池不足 expected={total} actual={len(out)}")
    return out


def _staff_pool(db, tenant_id: int, prefix: str) -> list:
    from app.models import User
    return list(db.execute(select(
        User.id, User.login_name, User.real_name,
    ).where(
        User.tenant_id == tenant_id,
        User.login_name.like(prefix),
        User.status == "ACTIVE",
        User.is_deleted.is_(False),
    ).order_by(User.login_name)).all())


def mentor_user_pools(db, tenant_id: int) -> tuple[list, list]:
    """只复用现有账号；专职背景账号与任课教师穿插，避免专业池单一化。"""
    teachers = _staff_pool(db, tenant_id, "sbx_t%")
    intern_primary = _staff_pool(db, tenant_id, "sbx_im%")
    grad_primary = _staff_pool(db, tenant_id, "sbx_gm%")
    if len(teachers) != 912 or len(intern_primary) != 96 or len(grad_primary) != 96:
        raise RuntimeError(
            "20K 导师账号池异常: "
            f"teachers={len(teachers)}, intern={len(intern_primary)}, graduation={len(grad_primary)}"
        )
    internship = _interleave(intern_primary, teachers[:128], EXPECTED_INTERNSHIP_MENTORS)
    graduation = _interleave(grad_primary, teachers[:288], EXPECTED_GRADUATION_MENTORS)
    if len({int(row.id) for row in internship}) != EXPECTED_INTERNSHIP_MENTORS:
        raise RuntimeError("实习导师账号池存在重复用户")
    if len({int(row.id) for row in graduation}) != EXPECTED_GRADUATION_MENTORS:
        raise RuntimeError("毕设导师账号池存在重复用户")
    return internship, graduation


def ensure_role_and_advisor_scope(db, tenant_id: int, role_code: str, users: list) -> dict:
    """给兼岗教师补既有正式角色与 ADVISOR 范围；已有绑定不重复写。"""
    from app.models import Role, TeacherStudentScope, UserRole

    role = db.scalars(select(Role).where(
        Role.tenant_id == tenant_id,
        Role.role_code == role_code,
        Role.status == "ACTIVE",
        Role.is_deleted.is_(False),
    )).first()
    if role is None:
        raise RuntimeError(f"导师角色不存在: {role_code}")

    user_ids = [int(row.id) for row in users]
    existing_role_users = set(db.scalars(select(UserRole.user_id).where(
        UserRole.tenant_id == tenant_id,
        UserRole.role_id == role.id,
        UserRole.status == "ACTIVE",
        UserRole.is_deleted.is_(False),
        UserRole.user_id.in_(user_ids),
    )).all())
    role_rows = [{
        "tenant_id": tenant_id,
        "user_id": int(user.id),
        "role_id": int(role.id),
        "status": "ACTIVE",
    } for user in users if int(user.id) not in existing_role_users]
    _bulk_insert(db, UserRole, role_rows, chunk_size=500)

    existing_scope_keys = set(db.scalars(select(TeacherStudentScope.teacher_key).where(
        TeacherStudentScope.tenant_id == tenant_id,
        TeacherStudentScope.role_code == role_code,
        TeacherStudentScope.scope_type == "ADVISOR",
        TeacherStudentScope.status == "ACTIVE",
        TeacherStudentScope.is_deleted.is_(False),
    )).all())
    scope_rows = [{
        "tenant_id": tenant_id,
        "teacher_key": user.login_name,
        "teacher_name": user.real_name,
        "role_code": role_code,
        "scope_type": "ADVISOR",
        "ref_value": None,
        "status": "ACTIVE",
    } for user in users if user.login_name not in existing_scope_keys]
    _bulk_insert(db, TeacherStudentScope, scope_rows, chunk_size=500)
    db.flush()
    return {
        "roleCode": role_code,
        "targetUsers": len(users),
        "newRoleBindings": len(role_rows),
        "newAdvisorScopes": len(scope_rows),
    }


def partition_users_by_major(users: list, *, graduation: bool) -> dict[str, list]:
    out: dict[str, list] = {}
    cursor = 0
    for major_code, _college_name, major_name in _major_specs():
        count = (
            graduation_mentor_count_for_major(major_code)
            if graduation
            else internship_mentor_count_for_major(major_code)
        )
        out[major_name] = users[cursor:cursor + count]
        if len(out[major_name]) != count:
            raise RuntimeError(f"{major_name} 导师分配不足 expected={count} actual={len(out[major_name])}")
        cursor += count
    if cursor != len(users):
        raise RuntimeError(f"导师专业分区未消费完 users={len(users)} cursor={cursor}")
    return out
