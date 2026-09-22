"""ACADEMIC_TEACHER 显式权限清单回归锁（纯单元，不建库不起 client，毫秒级）。

演进史：
- 2026-07-19 教务中心测试报告 Bug#3：ACADEMIC_TEACHER 持 academicAffairs.* 通配，
  教师可越权提交教学任务批次审核。第一步用 ROLE_PERMISSION_DENY 剔除 3 个批次管理动作；
- 同日完成 156 个权限点全量审计（主 router 152 + 学业过程域 3 + roster.viewSensitive），
  ACADEMIC_TEACHER 改为显式授权清单，deny 表清空。本文件锁住三件事：

1. 教学职责必需能力（查看/录入/发起/教师审批节点）必须放行——防收窄误伤重演
   Bug#4（教师被锁在核心职责外）；
2. 管理/审批/发布/资产维护/敏感导出动作（含当初 Bug#3 的三个批次动作）必须拒绝；
3. 管理员角色不受影响；deny 表保持为空（应急机制，不允许悄悄复用）。

口径变化记录：teachingTask.stats（批次分配率/确认率统计）2026-07-19 审计判定为
管理视角能力，从教师保留清单移入拒绝清单。
"""
from __future__ import annotations

from app.core.permissions import ROLE_PERMISSION_DENY, ROLE_PERMISSIONS, has_permission

# ── 教师日常职责必须保留的能力（授予全集见 permissions.py ACADEMIC_TEACHER 块） ──
TEACHER_KEPT_CODES = (
    # 基础只读
    "academicAffairs.term.view", "academicAffairs.calendar.view",
    "academicAffairs.timeslot.view", "academicAffairs.classTimeBand.view",
    "academicAffairs.course.view", "academicAffairs.program.view",
    "academicAffairs.roster.view",
    # 教学任务/课表
    "academicAffairs.teachingTask.view",
    "academicAffairs.schedule.view", "academicAffairs.schedule.teacherConfirm",
    # 调停课/成绩
    "academicAffairs.scheduleChange.apply", "academicAffairs.scheduleChange.view",
    "academicAffairs.grade.view", "academicAffairs.grade.input",
    "academicAffairs.grade.submit", "academicAffairs.gradeChange.apply",
    # 考务参与/审批节点
    "academicAffairs.exam.view", "academicAffairs.exam.recordAbnormal",
    "academicAffairs.deferredExam.review", "academicAffairs.exemption.review",
    # 选课/教材
    "academicAffairs.selection.view", "academicAffairs.selection.rosterView",
    "academicAffairs.textbook.view", "academicAffairs.textbook.selection.manage",
    # 资源只读 + 学业过程域只读
    "academicAffairs.classroom.view", "academicAffairs.lab.view",
    "academicAffairs.resourceOccupancy.view", "academicAffairs.process.view",
)

# ── 必须拒绝的管理/审批/发布/资产/敏感动作（代表性样本，覆盖每个子域） ──
TEACHER_DENIED_CODES = (
    # Bug#3 原始三件套 + 批次统计
    "academicAffairs.teachingTask.confirm", "academicAffairs.teachingTask.merge",
    "academicAffairs.teachingTask.adjust", "academicAffairs.teachingTask.stats",
    # 学期/校历/作息管理
    "academicAffairs.term.manage", "academicAffairs.calendar.manage",
    "academicAffairs.calendarPublish.manage", "academicAffairs.timeslot.manage",
    # 课程/方案管理与审批
    "academicAffairs.course.manage", "academicAffairs.course.approve",
    "academicAffairs.program.manage", "academicAffairs.program.review",
    "academicAffairs.program.publish", "academicAffairs.program.changeStatus",
    # 成绩管理链高危
    "academicAffairs.grade.collegeReview", "academicAffairs.grade.publish",
    "academicAffairs.grade.return", "academicAffairs.grade.archive",
    "academicAffairs.grade.export", "academicAffairs.gradeChange.review",
    "academicAffairs.gradeRecognition.manage",
    # 排课/课表管理
    "academicAffairs.schedule.edit", "academicAffairs.schedule.import",
    "academicAffairs.schedule.export", "academicAffairs.schedule.archive",
    "academicAffairs.schedule.rule.manage", "academicAffairs.schedule.availability.manage",
    "academicAffairs.scheduleChange.collegeReview", "academicAffairs.scheduleChange.academicReview",
    # 考务/选课/补考重修管理
    "academicAffairs.exam.arrange", "academicAffairs.exam.manage", "academicAffairs.exam.publish",
    "academicAffairs.selection.manage", "academicAffairs.selection.lock",
    "academicAffairs.retake.review", "academicAffairs.makeup.manage",
    # 学籍/注册/异动/分流/组织
    "academicAffairs.roster.viewSensitive", "academicAffairs.roster.import",
    "academicAffairs.roster.correction.apply", "academicAffairs.registration.eligibility.verify",
    "academicAffairs.statusChange.officeReview", "academicAffairs.majorSplit.manage",
    "academicAffairs.org.manage",
    # 资源资产/维修/统计
    "academicAffairs.classroom.create", "academicAffairs.classroom.update",
    "academicAffairs.classroom.delete", "academicAffairs.lab.update",
    "academicAffairs.equipment.create", "academicAffairs.resourceRepair.manage",
    # 预警/等级考试/毕业/归档/质量/评价/统计
    "academicAffairs.warning.rule.manage", "academicAffairs.levelExam.manage",
    "academicAffairs.graduation.final", "academicAffairs.graduationCert.manage",
    "academicAffairs.archive.manage", "academicAffairs.quality.record.manage",
    "academicAffairs.evaluation.batch.manage", "academicAffairs.stats.view",
    # 学业过程域写/导出
    "academicAffairs.process.manage", "academicAffairs.process.export",
)


def _user(role, user_type="TEACHER"):
    return {"currentRoleCode": role, "userType": user_type,
            "tenantId": "1", "activeContextId": f"legacy:{role}"}


def test_academic_teacher_keeps_daily_teaching_abilities():
    u = _user("ACADEMIC_TEACHER")
    for code in TEACHER_KEPT_CODES:
        assert has_permission(u, code), f"收窄误伤：ACADEMIC_TEACHER 应保留 {code}"


def test_academic_teacher_denied_admin_actions():
    u = _user("ACADEMIC_TEACHER")
    for code in TEACHER_DENIED_CODES:
        assert not has_permission(u, code), f"ACADEMIC_TEACHER 不应有 {code}"


def test_academic_teacher_no_wildcard_left():
    """显式清单不得混入任何通配模式——防止将来图省事塞回 'academicAffairs.*'。
    工作台自助权限（*_WORKBENCH_SELF）与待办读权属于全角色底座，允许与教务清单并存。"""
    granted = ROLE_PERMISSIONS["ACADEMIC_TEACHER"]
    assert all("*" not in code for code in granted), f"清单混入通配: {[c for c in granted if '*' in c]}"
    allowed_prefixes = ("academicAffairs.", "workbench.", "approval.todo.")
    bad = [c for c in granted if not c.startswith(allowed_prefixes)]
    assert not bad, f"ACADEMIC_TEACHER 出现非教务/工作台自助权限: {bad}"


def test_admin_roles_unaffected():
    for role in ("ACADEMIC_ADMIN", "COLLEGE_ADMIN", "SCHOOL_ADMIN"):
        u = _user(role, user_type="STAFF")
        for code in ("academicAffairs.teachingTask.confirm", "academicAffairs.grade.publish",
                     "academicAffairs.exam.manage", "academicAffairs.term.manage"):
            assert has_permission(u, code), f"{role} 的 {code} 不应被收窄波及"


def test_platform_super_admin_bypasses():
    u = _user("PLATFORM_SUPER_ADMIN", user_type="PLATFORM_SUPER_ADMIN")
    for code in TEACHER_DENIED_CODES[:5]:
        assert has_permission(u, code)


def test_deny_table_stays_empty():
    """deny 表是应急机制：ACADEMIC_TEACHER 已清单化后必须为空。
    若本断言失败，说明有人往 ROLE_PERMISSION_DENY 加了新角色——正确做法是
    像 ACADEMIC_TEACHER 一样做全量审计改显式清单，deny 只允许作为临时过渡并
    同步在本文件补该角色的保留/拒绝断言。"""
    assert ROLE_PERMISSION_DENY == {}
