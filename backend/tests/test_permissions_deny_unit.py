"""ROLE_PERMISSION_DENY 回归锁（纯单元，不建库不起 client，毫秒级）。

背景：2026-07-19 教务中心测试报告 Bug#3——ACADEMIC_TEACHER 持 academicAffairs.*
通配符，端点级 require_permission 对该角色形同虚设，教师可越权提交教学任务批次审核。
修复采用 deny-list 最小收窄（permissions.py ROLE_PERMISSION_DENY），本文件锁住三件事：

1. 被剔除的三个批次管理动作对 ACADEMIC_TEACHER 必须拒绝；
2. 未收窄的权限（教师真实需要的查看/录入/申请类）必须继续放行——防止收窄误伤重演
   Bug#4（教师被锁在核心职责外）；
3. 管理员角色（ACADEMIC_ADMIN/COLLEGE_ADMIN/SCHOOL_ADMIN/平台超管）不受 deny 影响。

若未来把 ACADEMIC_TEACHER 改为显式授权清单（152 权限点全量审计的独立任务），
本文件的用例仍应全部成立——届时 deny-list 可删，但行为断言不变。
"""
from __future__ import annotations

from app.core.permissions import ROLE_PERMISSION_DENY, has_permission

DENIED_CODES = (
    "academicAffairs.teachingTask.confirm",   # 批次提交/学院核对确认/教务终审
    "academicAffairs.teachingTask.merge",     # 合班/拆班
    "academicAffairs.teachingTask.adjust",    # 管理员更正教师/学时/周次/人数
)

# 教师真实职责必须保留的能力（收窄不得误伤——Bug#4 的反向保护）
TEACHER_KEPT_CODES = (
    "academicAffairs.teachingTask.view",
    "academicAffairs.teachingTask.stats",
    "academicAffairs.grade.view",
    "academicAffairs.grade.input",
    "academicAffairs.grade.submit",
    "academicAffairs.gradeChange.apply",
    "academicAffairs.scheduleChange.apply",
    "academicAffairs.scheduleChange.view",
    "academicAffairs.schedule.view",
)


def _user(role, user_type="TEACHER"):
    return {"currentRoleCode": role, "userType": user_type,
            "tenantId": "1", "activeContextId": f"legacy:{role}"}


def test_academic_teacher_denied_batch_admin_actions():
    u = _user("ACADEMIC_TEACHER")
    for code in DENIED_CODES:
        assert not has_permission(u, code), f"ACADEMIC_TEACHER 不应有 {code}"


def test_academic_teacher_keeps_daily_teaching_abilities():
    u = _user("ACADEMIC_TEACHER")
    for code in TEACHER_KEPT_CODES:
        assert has_permission(u, code), f"收窄误伤：ACADEMIC_TEACHER 应保留 {code}"


def test_admin_roles_unaffected_by_deny():
    for role in ("ACADEMIC_ADMIN", "COLLEGE_ADMIN", "SCHOOL_ADMIN"):
        u = _user(role, user_type="STAFF")
        for code in DENIED_CODES:
            assert has_permission(u, code), f"{role} 的 {code} 不应被 deny 波及"


def test_platform_super_admin_bypasses_deny():
    u = _user("PLATFORM_SUPER_ADMIN", user_type="PLATFORM_SUPER_ADMIN")
    for code in DENIED_CODES:
        assert has_permission(u, code)


def test_deny_table_only_covers_audited_roles():
    """deny-list 是"有真实越权证据才收窄"的最小机制：不允许悄悄扩到未审计角色。
    若本断言失败，说明有人往 ROLE_PERMISSION_DENY 加了新角色——请同步补充
    对应角色的保留能力断言（防误伤），并更新本文件。"""
    assert set(ROLE_PERMISSION_DENY) == {"ACADEMIC_TEACHER"}
    assert ROLE_PERMISSION_DENY["ACADEMIC_TEACHER"] == set(DENIED_CODES)
