"""NEW-P1-02 残留收口：成绩任务提交/学院审核也必须落真实受理人，禁止 assignee_id=0。

包 1 只把「成绩更正」链（change_request/change_college_review/change_academic_review）
换成了统一命令并解析真实受理人；成绩任务本身的提交与审核链
（submit_task → college_review → publish）没被触及，仍在写 ``assignee_id=0``。

后果与总表 NEW-P1-02 描述一致：
- 流程进了待审，但没有真实办理人，统一待办/移动端送不到具体的人；
- 任何持有该权限的账号都能从列表里抢办，职责分离形同虚设；
- 待办按 assignee_id 过滤时，0 号任务谁都查不到，只能靠人肉巡列表。

本模块不重写业务逻辑，只在两处任务落库前把 ``assignee_id`` 解析成唯一真实账号，
解析不到即 409 阻断——与包 1 的口径完全一致（宁可拒绝发起，也不留无人任务）。

节点与权限：
- ``COLLEGE_REVIEW`` → ``academicAffairs.grade.collegeReview``，按成绩任务的开课学院
  收敛到该院教学秘书 / 在岗负责人；
- ``ACADEMIC_REVIEW`` → ``academicAffairs.grade.publish``，属校级职责，优先唯一
  ``ACADEMIC_ADMIN``；仅当没有领域管理员时才允许其它校级显式持权账号兜底。

School IAM 权限真相：
- SYSTEM 角色消费已发布 TENANT RoleTemplate；
- CUSTOM/历史角色才消费 RolePermission。
审批受理人查询必须与登录鉴权使用同一权威，不能只 JOIN ``t_role_permission``，否则
COLLEGE_ADMIN / ACADEMIC_ADMIN 在真实 School IAM 下明明有权限，却会被候选查询当成 0 人。
"""
from __future__ import annotations

from app.modules.academic_affairs.services import academic_affairs_grade_core_service as _core
from app.modules.academic_affairs.services.academic_affairs_grade_correction_command import (
    _active_user,
    _college_bound_user_ids,
    _conflict,
    _task_college_id,
)

COLLEGE_NODE = "COLLEGE_REVIEW"
ACADEMIC_NODE = "ACADEMIC_REVIEW"
COLLEGE_PERM = "academicAffairs.grade.collegeReview"
ACADEMIC_PERM = "academicAffairs.grade.publish"

# 调停课走同名的两个节点，但有自己的一套权限码。
SCHEDULE_CHANGE_COLLEGE_PERM = "academicAffairs.scheduleChange.collegeReview"
SCHEDULE_CHANGE_ACADEMIC_PERM = "academicAffairs.scheduleChange.academicReview"


def _runtime_permission_holder_ids(db, permission_code: str) -> list[int]:
    """Return active users holding ``permission_code`` under canonical School IAM.

    SYSTEM roles no longer materialize their runtime authority into tenant
    ``RolePermission`` rows: the immutable published TENANT RoleTemplate is the
    authority.  CUSTOM (and legacy non-system) roles still use normalized
    ``RolePermission`` rows.  Resolve both planes explicitly and fail closed if a
    published SYSTEM template is missing or drifting.
    """
    from sqlalchemy import select

    from app.core.permissions import ROLE_PERMISSIONS
    from app.models import Permission, Role, RolePermission, User, UserRole
    from app.services.system_role_shadow_service import published_system_role_permissions

    pairs = list(db.execute(
        select(User.id, Role)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            User.tenant_id == _core._tid(),
            User.status == "ACTIVE",
            User.is_deleted.is_(False),
            UserRole.tenant_id == _core._tid(),
            UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False),
            Role.tenant_id == _core._tid(),
            Role.status == "ACTIVE",
            Role.is_deleted.is_(False),
        )
    ).all())

    legacy_role_ids = {
        int(role.id)
        for _user_id, role in pairs
        if str(role.role_type or "").upper() != "SYSTEM"
        and str(role.role_code or "").strip().upper() not in ROLE_PERMISSIONS
    }
    legacy_allowed: set[int] = set()
    if legacy_role_ids:
        legacy_allowed = {
            int(value)
            for value in db.scalars(
                select(RolePermission.role_id)
                .join(Permission, Permission.id == RolePermission.permission_id)
                .where(
                    RolePermission.tenant_id == _core._tid(),
                    RolePermission.role_id.in_(legacy_role_ids),
                    RolePermission.status == "ACTIVE",
                    RolePermission.is_deleted.is_(False),
                    Permission.permission_code == permission_code,
                )
            ).all()
        }

    system_cache: dict[str, bool] = {}
    users: set[int] = set()
    for user_id, role in pairs:
        role_code = str(role.role_code or "").strip().upper()
        role_type = str(role.role_type or "").upper()
        is_system = role_type == "SYSTEM" or role_code in ROLE_PERMISSIONS
        if is_system:
            allowed = system_cache.get(role_code)
            if allowed is None:
                allowed = permission_code in set(published_system_role_permissions(db, role_code))
                system_cache[role_code] = allowed
            if allowed:
                users.add(int(user_id))
        elif int(role.id) in legacy_allowed:
            users.add(int(user_id))
    return sorted(users)


def _preferred_role_candidates(db, candidates, role_code: str) -> list[int]:
    """Prefer the domain owner role without silently broadening authority.

    SCHOOL_ADMIN may legitimately hold the same high-risk permission, but its global
    authority must not make every normal domain workflow ambiguous when a concrete
    ACADEMIC_ADMIN exists.  Multiple domain admins still fail closed via the unique
    assignee check; fallback candidates are considered only when no domain owner is
    present.
    """
    from sqlalchemy import select

    from app.models import Role, UserRole

    candidate_ids = {int(value) for value in candidates if int(value) > 0}
    if not candidate_ids:
        return []
    preferred = {
        int(value)
        for value in db.scalars(
            select(UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                UserRole.tenant_id == _core._tid(),
                UserRole.user_id.in_(candidate_ids),
                UserRole.status == "ACTIVE",
                UserRole.is_deleted.is_(False),
                Role.tenant_id == _core._tid(),
                Role.role_code == str(role_code or "").strip().upper(),
                Role.status == "ACTIVE",
                Role.is_deleted.is_(False),
            )
        ).all()
    }
    return sorted(preferred or candidate_ids)


def _unique_subject_assignee(candidates, node: str, subject: str) -> int:
    """Resolve one concrete assignee without leaking correction-specific wording."""
    unique = sorted({int(value) for value in candidates if int(value) > 0})
    if len(unique) != 1:
        raise _conflict(
            f"{subject}审批节点没有唯一真实受理人，禁止生成无人或人人可抢的待审任务",
            node=node,
            subject=subject,
            candidateUserIds=[str(value) for value in unique],
        )
    return unique[0]


def resolve_grade_task_assignee(db, node: str, task, *, college_perm: str = COLLEGE_PERM,
                                academic_perm: str = ACADEMIC_PERM,
                                subject: str = "成绩任务") -> int:
    """审批节点 → 唯一真实受理人 userId；解析不到即 409。

    默认按成绩任务的权限码解析；调停课等同构流程传入自己的权限码复用同一套收敛规则
    （学院节点收敛到该院教学秘书/在岗负责人，校级节点优先 ACADEMIC_ADMIN）。
    """
    if node == ACADEMIC_NODE:
        from datetime import datetime

        from sqlalchemy import or_, select

        from app.models import StaffAssignment

        candidates = _runtime_permission_holder_ids(db, academic_perm)
        college_bound = _college_bound_user_ids(db)
        school_level = [uid for uid in candidates if uid not in college_bound]
        # 校级教务可能有多名持权账号；最终审批必须落到组织任职中明确指定的
        # ACADEMIC_REVIEWER，而不是让所有教务管理员都能抢办。没有配置该岗位的
        # 老租户继续走原有“领域角色天然唯一”兼容路径。
        now = datetime.utcnow()
        appointed = {
            int(value)
            for value in db.scalars(select(StaffAssignment.user_id).where(
                StaffAssignment.tenant_id == _core._tid(),
                StaffAssignment.org_type == "SCHOOL",
                StaffAssignment.org_node_id == _core._tid(),
                StaffAssignment.assignment_type == "ACADEMIC_REVIEWER",
                StaffAssignment.status == "ACTIVE",
                StaffAssignment.is_deleted.is_(False),
                StaffAssignment.effective_at <= now,
                or_(StaffAssignment.expires_at.is_(None), StaffAssignment.expires_at > now),
            )).all()
            if int(value) in school_level and _active_user(db, int(value))
        }
        if appointed:
            return _unique_subject_assignee(appointed, node, subject)
        return _unique_subject_assignee(
            _preferred_role_candidates(db, school_level, "ACADEMIC_ADMIN"),
            node,
            subject,
        )

    from sqlalchemy import or_, select

    from app.models import College, StaffAssignment

    candidates = _runtime_permission_holder_ids(db, college_perm)
    college_id = _task_college_id(db, task)
    if not college_id:
        raise _conflict(f"{subject}未绑定开课学院，无法解析学院审核受理人", node=node)
    college = db.get(College, int(college_id))
    if not college or college.tenant_id != _core._tid() or college.is_deleted:
        raise _conflict(f"{subject}的开课学院不存在或已停用", node=node)

    if college.secretary_id and int(college.secretary_id) in candidates:
        if _active_user(db, int(college.secretary_id)):
            return int(college.secretary_id)

    from datetime import datetime

    now = datetime.utcnow()
    assigned = db.scalars(select(StaffAssignment.user_id).where(
        StaffAssignment.tenant_id == _core._tid(),
        StaffAssignment.org_type == "COLLEGE",
        StaffAssignment.org_node_id == int(college_id),
        StaffAssignment.assignment_type.in_(("SECRETARY", "LEADER")),
        StaffAssignment.status == "ACTIVE",
        StaffAssignment.is_deleted.is_(False),
        StaffAssignment.effective_at <= now,
        or_(StaffAssignment.expires_at.is_(None), StaffAssignment.expires_at > now),
    ).order_by(StaffAssignment.is_primary.desc(), StaffAssignment.user_id)).all()
    allowed = [int(uid) for uid in assigned
               if int(uid) in candidates and _active_user(db, int(uid))]
    return _unique_subject_assignee(allowed, node, subject)
