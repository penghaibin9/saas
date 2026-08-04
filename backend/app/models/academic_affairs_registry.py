"""教务增强模型注册表。

共享 ``app.models`` 只需一行导入本注册表；新增教务模型继续在本文件维护，
避免长期分支反复改动全系统模型聚合文件。
"""
from app.models.academic_grade_extensions import install_academic_grade_extensions
from app.models.academic_affairs_teaching_class import (
    AaTeachingClass,
    AaTeachingClassMember,
    AaTeachingClassRosterVersion,
    AaTeachingClassTeacher,
)
from app.models.academic_affairs_roster_consumer import AaRosterConsumerSnapshot
from app.models.academic_affairs_r10 import (
    AaGradeComponentScore,
    AaGradeSchemeSnapshot,
    AaStatsSnapshot,
)
from app.models.academic_affairs_r11 import (
    AaSemesterPilot,
    AaSemesterPilotCheckpoint,
)
from app.models.academic_affairs_effective_grade import (
    AaEffectiveGradePolicy,
    AaEffectiveGradePolicySnapshot,
    AaGradeCorrection,
)


# 显式调用保持意图清晰；安装函数具备幂等保护，模块首次导入时已完成一次安装。
install_academic_grade_extensions()

# 模型和成绩扩展完成后安装迁移前历史成绩兼容口径；新写入仍冻结租户版本化策略。
from app.modules.academic_affairs.services import academic_affairs_effective_grade_policy_compat as _grade_policy_compat  # noqa: E402,F401

__all__ = [
    "AaTeachingClass",
    "AaTeachingClassMember",
    "AaTeachingClassRosterVersion",
    "AaTeachingClassTeacher",
    "AaRosterConsumerSnapshot",
    "AaGradeComponentScore",
    "AaGradeSchemeSnapshot",
    "AaStatsSnapshot",
    "AaSemesterPilot",
    "AaSemesterPilotCheckpoint",
    "AaEffectiveGradePolicy",
    "AaEffectiveGradePolicySnapshot",
    "AaGradeCorrection",
]
