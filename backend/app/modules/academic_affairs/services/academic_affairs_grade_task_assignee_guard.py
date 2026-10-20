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


def _active_role_pairs_statement(tenant_id):
    """Batch equivalent of login's live role/membership decision; never await expiry jobs."""
    from sqlalchemy import and_, or_, select
    from app.models import Role, RoleAssignmentValidity, User, UserRole
    from app.services.role_assignment_service import _now as assignment_now

    moment = assignment_now()
    return (select(User.id, Role)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .outerjoin(RoleAssignmentValidity, and_(
            RoleAssignmentValidity.tenant_id == UserRole.tenant_id,
            RoleAssignmentValidity.user_role_id == UserRole.id))
        .where(User.tenant_id == tenant_id, User.status == "ACTIVE", User.is_deleted.is_(False),
            UserRole.tenant_id == tenant_id, UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False),
            Role.tenant_id == tenant_id, Role.role_code != "PLATFORM_SUPER_ADMIN",
            Role.status.in_(("ACTIVE", "ENABLED")), Role.is_deleted.is_(False),
            or_(RoleAssignmentValidity.id.is_(None), and_(
                RoleAssignmentValidity.user_id == User.id,
                RoleAssignmentValidity.role_code == Role.role_code,
                RoleAssignmentValidity.status == "ACTIVE", RoleAssignmentValidity.is_deleted.is_(False),
                RoleAssignmentValidity.effective_at <= moment,
                or_(RoleAssignmentValidity.expires_at.is_(None),
                    RoleAssignmentValidity.expires_at > moment)))))


def _runtime_permission_holder_ids(db, permission_code: str, *, cache=None) -> list[int]:
    """学校发布模板与自定义角色共用当前权限真值；缓存仅由只读请求显式传入。"""
    from sqlalchemy import select
    from app.core.permissions import ROLE_PERMISSIONS, _match
    from app.models import Permission, Role, RolePermission, User, UserRole
    from app.services.system_role_shadow_service import published_system_role_permissions

    current = cache if cache is not None else {}
    tenant_id = _core._tid()
    holder_key = ("permission_holder_ids", tenant_id, permission_code)
    if holder_key in current:
        return list(current[holder_key])
    pair_key = ("active_role_pairs", tenant_id)
    if pair_key not in current:
        current[pair_key] = list(db.execute(_active_role_pairs_statement(tenant_id)).all())
    pairs = current[pair_key]
    legacy_ids = {int(role.id) for _, role in pairs
        if str(role.role_type or "").upper() != "SYSTEM"
        and str(role.role_code or "").strip().upper() not in ROLE_PERMISSIONS}
    legacy_key = ("custom_role_permissions", tenant_id)
    if legacy_key not in current:
        permissions = {}
        if legacy_ids:
            for role_id, code in db.execute(select(RolePermission.role_id, Permission.permission_code)
                .join(Permission, Permission.id == RolePermission.permission_id).where(
                    RolePermission.tenant_id == tenant_id, RolePermission.role_id.in_(legacy_ids),
                    RolePermission.status == "ACTIVE", RolePermission.is_deleted.is_(False))):
                permissions.setdefault(int(role_id), set()).add(code)
        current[legacy_key] = permissions
    users = set()
    role_matches = {}
    for user_id, role in pairs:
        role_code = str(role.role_code or "").strip().upper()
        match_key = (int(role.id), role_code)
        if match_key in role_matches:
            if role_matches[match_key]:
                users.add(int(user_id))
            continue
        if str(role.role_type or "").upper() == "SYSTEM" or role_code in ROLE_PERMISSIONS:
            role_key = ("published_role_permissions", tenant_id, role_code)
            if role_key not in current:
                current[role_key] = set(published_system_role_permissions(db, role_code))
            patterns = current[role_key]
        else:
            patterns = current[legacy_key].get(int(role.id), set())
        role_matches[match_key] = _match(permission_code, patterns)
        if role_matches[match_key]:
            users.add(int(user_id))
    # The caller owns this one-read-request cache; command callers omit it.
    current[holder_key] = tuple(sorted(users))
    return list(current[holder_key])


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
    from app.models import User
    preferred = {int(value) for value in db.scalars(
        _active_role_pairs_statement(_core._tid()).with_only_columns(User.id).where(
            User.id.in_(candidate_ids),
            Role.role_code == str(role_code or "").strip().upper(),
        )).all()}
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
    from .academic_affairs_responsibility_service import resolve_organization, resolve_school

    if node == ACADEMIC_NODE:
        owner = resolve_school(db, permission_code=academic_perm)
    else:
        college_id = _task_college_id(db, task)
        if not college_id:
            raise _conflict(f"{subject}未绑定开课学院，无法解析学院审核受理人", node=node)
        owner = resolve_organization(db, "COLLEGE", college_id, permission_code=college_perm)
    return _unique_subject_assignee(owner["assigneeUserIds"], node, subject)
