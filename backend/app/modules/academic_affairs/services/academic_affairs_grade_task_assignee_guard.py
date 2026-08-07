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
- ``ACADEMIC_REVIEW`` → ``academicAffairs.grade.publish``，属校级职责，排除绑在具体
  学院上的账号，避免学院教务既审初审又审终审。
"""
from __future__ import annotations

from app.modules.academic_affairs.services import academic_affairs_grade_core_service as _core
from app.modules.academic_affairs.services.academic_affairs_grade_correction_command import (
    _active_user,
    _college_bound_user_ids,
    _conflict,
    _permission_holder_ids,
    _task_college_id,
    _unique_assignee,
)

COLLEGE_NODE = "COLLEGE_REVIEW"
ACADEMIC_NODE = "ACADEMIC_REVIEW"
COLLEGE_PERM = "academicAffairs.grade.collegeReview"
ACADEMIC_PERM = "academicAffairs.grade.publish"

# 调停课走同名的两个节点，但有自己的一套权限码。
SCHEDULE_CHANGE_COLLEGE_PERM = "academicAffairs.scheduleChange.collegeReview"
SCHEDULE_CHANGE_ACADEMIC_PERM = "academicAffairs.scheduleChange.academicReview"


def resolve_grade_task_assignee(db, node: str, task, *, college_perm: str = COLLEGE_PERM,
                                academic_perm: str = ACADEMIC_PERM,
                                subject: str = "成绩任务") -> int:
    """审批节点 → 唯一真实受理人 userId；解析不到即 409。

    默认按成绩任务的权限码解析；调停课等同构流程传入自己的权限码复用同一套收敛规则
    （学院节点收敛到该院教学秘书/在岗负责人，校级节点排除院级账号）。
    """
    if node == ACADEMIC_NODE:
        candidates = _permission_holder_ids(db, academic_perm)
        college_bound = _college_bound_user_ids(db)
        return _unique_assignee([uid for uid in candidates if uid not in college_bound], node)

    from sqlalchemy import or_, select

    from app.models import College, StaffAssignment

    candidates = _permission_holder_ids(db, college_perm)
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
    return _unique_assignee(allowed, node)
