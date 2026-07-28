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
from app.models.academic_affairs_effective_grade import AaEffectiveGradePolicySnapshot


# 显式调用保持意图清晰；安装函数具备幂等保护，模块首次导入时已完成一次安装。
install_academic_grade_extensions()

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
    "AaEffectiveGradePolicySnapshot",
]
