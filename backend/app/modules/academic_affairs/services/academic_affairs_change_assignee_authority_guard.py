"""AA-003：学籍异动审批受理人与当前 School IAM Authority 对齐。

包 5 的状态机、任务唯一性和学院业务锚点保持不变；这里只修复候选人的权限真相来源：
- SYSTEM 角色消费已发布 TENANT RoleTemplate；
- CUSTOM/历史角色继续消费规范化 RolePermission；
- 教务终审优先唯一 ACADEMIC_ADMIN，避免 SCHOOL_ADMIN 的全局授权制造伪歧义。

这与已经封过成绩/调停课受理人的 canonical resolver 使用同一算法。解析不到或不唯一仍
fail-closed 409，绝不回落 assignee_id=0，也不扩大任何角色权限。
"""
from __future__ import annotations

from . import academic_affairs_change_safety_guard as safety
from . import academic_affairs_change_service as change_service
from .academic_affairs_grade_task_assignee_guard import (
    _runtime_permission_holder_ids,
    resolve_grade_task_assignee,
)

_OFFICE_PERMISSION = "academicAffairs.statusChange.officeReview"
_ORIGINAL_STRICT_ASSIGNEE_FOR = safety.strict_assignee_for


def strict_assignee_for(db, node, student_id):
    """Keep package-5 routing, except use the canonical school-level owner for final review."""
    if node == "AA_OFFICE_FINAL":
        # Reuse the already hardened school-level resolver. Supplying the status-change
        # permission keeps the role preference/uniqueness semantics while changing no
        # grade business state.
        return resolve_grade_task_assignee(
            db,
            "ACADEMIC_REVIEW",
            None,
            academic_perm=_OFFICE_PERMISSION,
            subject="学籍异动",
        )
    return _ORIGINAL_STRICT_ASSIGNEE_FOR(db, node, student_id)


# Preserve package-5's idempotent-install contract if safety.install() is called again later.
strict_assignee_for._status_change_safety_guard = True
strict_assignee_for._status_change_authority_guard = True


def install() -> None:
    # Reuse the exact School IAM permission-holder resolver already owned by the grade/schedule
    # assignee module; do not keep a one-line local proxy that can drift from that canonical source.
    safety._permission_candidate_ids = _runtime_permission_holder_ids

    # Package-5 routes both direct task creation (change_service._assignee_for) and claim-time repair
    # through its resolver. Replace both live references so every status-change node keeps the same
    # fail-closed authority semantics.
    safety.strict_assignee_for = strict_assignee_for
    change_service._assignee_for = strict_assignee_for
