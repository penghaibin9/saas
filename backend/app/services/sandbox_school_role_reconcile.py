"""20K 售前学校 · 真实学校角色拓扑与数据范围对账。

原则：
- 不为了“角色丰富”重复造教职工账号；复用现有 1,280 个背景账号做兼岗；
- 只使用 saas_role_templates 已冻结的正式角色码，不发明演示权限码；
- 学院/专业/导师类角色必须同时有 TeacherStudentScope，避免只有角色没有数据边界；
- SCHOOL_ADMIN / 任课教师 / 辅导员 / 教务 / 学工 / 实习导师 / 毕设导师等主角色由主种子生成，
  本文件只补真实学校常见的兼岗与组织责任角色。
"""
from __future__ import annotations

from collections import Counter

from sqlalchemy import select

from app.services.saas_role_templates import ROLE_TEMPLATE_BY_CODE
from app.services.sandbox_school_master_seed import _bulk_insert

SECONDARY_ROLE_ASSIGNMENT_COUNTS: dict[str, int] = {
    "LEADER": 9,
    "COLLEGE_ADMIN": 24,
    "STUDENT_AFFAIRS": 32,
    "PSYCHOLOGY_TEACHER": 16,
    "FUNDING_TEACHER": 16,
    "DORM_MANAGER": 12,
    "YOUTH_LEAGUE": 8,
    "ORG_PERSONNEL": 8,
    "GRADUATION_ADMIN": 4,
    "GD_COLLEGE_ADMIN": 16,
    "GD_MAJOR_ADMIN": 32,
    "GD_REVIEWER": 96,
    "GD_DEFENSE_SECRETARY": 32,
    "GD_DEFENSE_EXPERT": 160,
    "GD_GRADE_ADMIN": 4,
    "EMPLOYMENT_TEACHER": 32,
}

EXPECTED_ORG_SCOPES: dict[str, int] = {
    "COLLEGE_ADMIN": 24,
    "STUDENT_AFFAIRS": 32,
    "PSYCHOLOGY_TEACHER": 16,
    "FUNDING_TEACHER": 16,
    "YOUTH_LEAGUE": 8,
    "GD_COLLEGE_ADMIN": 16,
    "GD_MAJOR_ADMIN": 32,
    "EMPLOYMENT_TEACHER": 32,
    "GD_MENTOR": 96,
    "INTERN_MENTOR": 96,
}

REQUIRED_ROLE_CODES = tuple(sorted({
    "SCHOOL_ADMIN", "STUDENT", "ACADEMIC_TEACHER", "ACADEMIC_ADMIN",
    "STUDENT_AFFAIRS_ADMIN", "COUNSELOR", "INTERN_MENTOR", "GD_MENTOR",
    *SECONDARY_ROLE_ASSIGNMENT_COUNTS.keys(),
}))


def _staff_pools(db, tenant_id: int) -> dict[str, list]:
    from app.models import User

    prefixes = {
        "academic": "sbx_t%",
        "counselor": "sbx_c%",
        "academic_admin": "sbx_aa%",
        "student_affairs": "sbx_sa%",
        "intern_mentor": "sbx_im%",
        "graduation_mentor": "sbx_gm%",
    }
    pools = {}
    for key, pattern in prefixes.items():
        pools[key] = list(db.execute(select(
            User.id, User.login_name, User.real_name,
        ).where(
            User.tenant_id == tenant_id,
            User.login_name.like(pattern),
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
        ).order_by(User.login_name)).all())
    expected = {
        "academic": 912,
        "counselor": 96,
        "academic_admin": 48,
        "student_affairs": 32,
        "intern_mentor": 96,
        "graduation_mentor": 96,
    }
    bad = {key: {"expected": expected[key], "actual": len(rows)} for key, rows in pools.items()
           if len(rows) != expected[key]}
    if bad:
        raise RuntimeError(f"20K 角色拓扑账号池异常: {bad}")
    return pools


def _ensure_roles(db, tenant_id: int) -> dict[str, int]:
    from app.models import Role

    existing = {
        row.role_code: row
        for row in db.scalars(select(Role).where(
            Role.tenant_id == tenant_id,
            Role.role_code.in_(REQUIRED_ROLE_CODES),
            Role.is_deleted.is_(False),
        )).all()
    }
    for code in REQUIRED_ROLE_CODES:
        template = ROLE_TEMPLATE_BY_CODE.get(code)
        if template is None:
            raise RuntimeError(f"20K 角色拓扑引用了未冻结角色码: {code}")
        role = existing.get(code)
        if role is None:
            role = Role(
                tenant_id=tenant_id,
                role_code=code,
                role_name=template["roleName"],
                role_type="SYSTEM",
                status="ACTIVE",
                remark=f"内置角色模板 {template['category']} / {template['defaultScope']}",
            )
            db.add(role)
            db.flush()
            existing[code] = role
        else:
            role.role_name = template["roleName"]
            role.role_type = "SYSTEM"
            role.status = "ACTIVE"
            role.is_deleted = False
    db.flush()
    return {code: int(existing[code].id) for code in REQUIRED_ROLE_CODES}


def _assignment_plan(pools: dict[str, list]) -> dict[str, list]:
    aa = pools["academic_admin"]
    sa = pools["student_affairs"]
    teachers = pools["academic"]
    gd = pools["graduation_mentor"]

    plan = {
        "LEADER": aa[:9],                       # 1 个校级管理视角 + 8 个学院领导视角
        "COLLEGE_ADMIN": aa[:24],              # 每学院 3 名学院管理/教务责任人
        "STUDENT_AFFAIRS": sa[:32],            # 每学院 4 名学工老师
        "PSYCHOLOGY_TEACHER": sa[:16],         # 每学院 2 名心理工作责任人
        "FUNDING_TEACHER": sa[16:32],          # 每学院 2 名资助工作责任人
        "DORM_MANAGER": sa[:12],               # 12 栋宿舍各 1 个责任账号
        "YOUTH_LEAGUE": sa[:8],                # 每学院 1 名团学工作责任人
        "ORG_PERSONNEL": aa[40:48],            # 8 名人事组织工作责任人
        "GRADUATION_ADMIN": aa[:4],            # 校级毕设管理工作组
        "GD_COLLEGE_ADMIN": aa[:16],           # 每学院 2 名毕设管理员
        "GD_MAJOR_ADMIN": aa[:32],             # 32 专业各 1 名毕设专业负责人
        "GD_REVIEWER": gd[:96],                # 指导教师同时承担分配式评阅
        "GD_DEFENSE_SECRETARY": teachers[:32], # 32 专业各 1 名答辩秘书背景人选
        "GD_DEFENSE_EXPERT": gd[:96] + teachers[:64],
        "GD_GRADE_ADMIN": aa[:4],
        "EMPLOYMENT_TEACHER": sa[:32],         # 每学院 4 名就业工作责任人
    }
    bad = {
        code: {"expected": SECONDARY_ROLE_ASSIGNMENT_COUNTS[code], "actual": len(rows)}
        for code, rows in plan.items()
        if len(rows) != SECONDARY_ROLE_ASSIGNMENT_COUNTS[code]
    }
    if bad:
        raise RuntimeError(f"20K 兼岗角色分配异常: {bad}")
    return plan


def _insert_role_bindings(db, tenant_id: int, role_ids: dict[str, int], plan: dict[str, list]) -> int:
    from app.models import UserRole

    user_ids = {int(row.id) for rows in plan.values() for row in rows}
    target_role_ids = {role_ids[code] for code in plan}
    existing = {
        (int(uid), int(rid))
        for uid, rid in db.execute(select(UserRole.user_id, UserRole.role_id).where(
            UserRole.tenant_id == tenant_id,
            UserRole.user_id.in_(user_ids),
            UserRole.role_id.in_(target_role_ids),
            UserRole.is_deleted.is_(False),
        )).all()
    }
    rows = []
    for code, users in plan.items():
        rid = role_ids[code]
        for user in users:
            key = (int(user.id), rid)
            if key in existing:
                continue
            rows.append({
                "tenant_id": tenant_id,
                "user_id": int(user.id),
                "role_id": rid,
                "status": "ACTIVE",
            })
    _bulk_insert(db, UserRole, rows, chunk_size=500)
    db.flush()
    return len(rows)


def _distribute_scope_rows(users: list, refs: list[str], *, role_code: str, scope_type: str,
                           per_ref: int) -> list[dict]:
    expected = len(refs) * per_ref
    if len(users) < expected:
        raise RuntimeError(
            f"{role_code} 数据范围账号不足: expected={expected} actual={len(users)}"
        )
    rows = []
    cursor = 0
    for ref in refs:
        for _ in range(per_ref):
            user = users[cursor]
            cursor += 1
            rows.append({
                "teacher_key": user.login_name,
                "teacher_name": user.real_name,
                "role_code": role_code,
                "scope_type": scope_type,
                "ref_value": ref,
            })
    return rows


def _seed_org_scopes(db, tenant_id: int, pools: dict[str, list]) -> dict[str, int]:
    from app.models import College, Major, TeacherStudentScope

    colleges = [name for (name,) in db.execute(select(College.college_name).where(
        College.tenant_id == tenant_id,
        College.is_deleted.is_(False),
    ).order_by(College.code)).all()]
    majors = [name for (name,) in db.execute(select(Major.major_name).where(
        Major.tenant_id == tenant_id,
        Major.is_deleted.is_(False),
    ).order_by(Major.code)).all()]
    if len(colleges) != 8 or len(majors) != 32:
        raise RuntimeError(f"角色范围组织基数异常 colleges={len(colleges)} majors={len(majors)}")

    aa = pools["academic_admin"]
    sa = pools["student_affairs"]
    raw = []
    raw += _distribute_scope_rows(aa[:24], colleges, role_code="COLLEGE_ADMIN", scope_type="COLLEGE", per_ref=3)
    raw += _distribute_scope_rows(sa[:32], colleges, role_code="STUDENT_AFFAIRS", scope_type="COLLEGE", per_ref=4)
    raw += _distribute_scope_rows(sa[:16], colleges, role_code="PSYCHOLOGY_TEACHER", scope_type="COLLEGE", per_ref=2)
    raw += _distribute_scope_rows(sa[16:32], colleges, role_code="FUNDING_TEACHER", scope_type="COLLEGE", per_ref=2)
    raw += _distribute_scope_rows(sa[:8], colleges, role_code="YOUTH_LEAGUE", scope_type="COLLEGE", per_ref=1)
    raw += _distribute_scope_rows(aa[:16], colleges, role_code="GD_COLLEGE_ADMIN", scope_type="COLLEGE", per_ref=2)
    raw += _distribute_scope_rows(aa[:32], majors, role_code="GD_MAJOR_ADMIN", scope_type="MAJOR", per_ref=1)
    raw += _distribute_scope_rows(sa[:32], colleges, role_code="EMPLOYMENT_TEACHER", scope_type="COLLEGE", per_ref=4)

    for role_code, pool_name in (("GD_MENTOR", "graduation_mentor"), ("INTERN_MENTOR", "intern_mentor")):
        for user in pools[pool_name]:
            raw.append({
                "teacher_key": user.login_name,
                "teacher_name": user.real_name,
                "role_code": role_code,
                "scope_type": "ADVISOR",
                "ref_value": None,
            })

    rows = [{"tenant_id": tenant_id, "status": "ACTIVE", **item} for item in raw]
    _bulk_insert(db, TeacherStudentScope, rows, chunk_size=500)
    db.commit()
    counts = Counter(item["role_code"] for item in raw)
    bad = {
        code: {"expected": expected, "actual": counts.get(code, 0)}
        for code, expected in EXPECTED_ORG_SCOPES.items()
        if counts.get(code, 0) != expected
    }
    if bad:
        raise RuntimeError(f"20K 角色数据范围生成异常: {bad}")
    return dict(counts)


def validate_school_roles_20k(db, tenant_id: int) -> dict:
    from app.models import Role, TeacherStudentScope, User, UserRole

    role_id_by_code = {
        code: int(rid)
        for rid, code in db.execute(select(Role.id, Role.role_code).where(
            Role.tenant_id == tenant_id,
            Role.role_code.in_(REQUIRED_ROLE_CODES),
            Role.status == "ACTIVE",
            Role.is_deleted.is_(False),
        )).all()
    }
    missing_roles = sorted(set(REQUIRED_ROLE_CODES) - set(role_id_by_code))

    assignment_counts: dict[str, int] = {}
    for code in SECONDARY_ROLE_ASSIGNMENT_COUNTS:
        rid = role_id_by_code.get(code)
        assignment_counts[code] = 0 if rid is None else int(db.scalar(
            select(__import__("sqlalchemy").func.count()).select_from(UserRole).where(
                UserRole.tenant_id == tenant_id,
                UserRole.role_id == rid,
                UserRole.status == "ACTIVE",
                UserRole.is_deleted.is_(False),
            )
        ) or 0)

    scope_counts = {
        role_code: int(count)
        for role_code, count in db.execute(select(
            TeacherStudentScope.role_code,
            __import__("sqlalchemy").func.count(),
        ).where(
            TeacherStudentScope.tenant_id == tenant_id,
            TeacherStudentScope.role_code.in_(tuple(EXPECTED_ORG_SCOPES)),
            TeacherStudentScope.status == "ACTIVE",
            TeacherStudentScope.is_deleted.is_(False),
        ).group_by(TeacherStudentScope.role_code)).all()
    }
    background_accounts = int(db.scalar(
        select(__import__("sqlalchemy").func.count()).select_from(User).where(
            User.tenant_id == tenant_id,
            User.login_name.like("sbx_%"),
            User.is_deleted.is_(False),
        )
    ) or 0)

    role_mismatches = {
        code: {"expected": expected, "actual": assignment_counts.get(code, 0)}
        for code, expected in SECONDARY_ROLE_ASSIGNMENT_COUNTS.items()
        if assignment_counts.get(code, 0) != expected
    }
    scope_mismatches = {
        code: {"expected": expected, "actual": scope_counts.get(code, 0)}
        for code, expected in EXPECTED_ORG_SCOPES.items()
        if scope_counts.get(code, 0) != expected
    }
    if missing_roles or role_mismatches or scope_mismatches or background_accounts != 1280:
        raise RuntimeError(
            "20K 角色拓扑验收失败: "
            f"missingRoles={missing_roles}, roleMismatches={role_mismatches}, "
            f"scopeMismatches={scope_mismatches}, backgroundAccounts={background_accounts}"
        )
    return {
        "requiredRoles": len(REQUIRED_ROLE_CODES),
        "secondaryRoleBindings": sum(assignment_counts.values()),
        "roleAssignments": assignment_counts,
        "orgScopes": scope_counts,
        "backgroundStaffAccounts": background_accounts,
        "passed": True,
    }


def reconcile_school_roles_20k(db, tenant_id: int) -> dict:
    pools = _staff_pools(db, tenant_id)
    role_ids = _ensure_roles(db, tenant_id)
    plan = _assignment_plan(pools)
    inserted = _insert_role_bindings(db, tenant_id, role_ids, plan)
    scope_counts = _seed_org_scopes(db, tenant_id, pools)
    validation = validate_school_roles_20k(db, tenant_id)
    return {
        "insertedSecondaryBindings": inserted,
        "scopeCounts": scope_counts,
        "validation": validation,
    }
