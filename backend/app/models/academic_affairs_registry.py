"""教务增强模型注册表。

共享 ``app.models`` 只需一行导入本注册表；新增教务模型继续在本文件维护，
避免长期分支反复改动全系统模型聚合文件。
"""
from sqlalchemy import DateTime, Text
from sqlalchemy.dialects import mysql

from app.models.academic_grade_extensions import install_academic_grade_extensions
from app.models.academic_affairs import AaGraduationAuditResult, AaStatusChange
from app.models.academic_affairs_program_extensions import install_academic_program_extensions
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
    AaEffectiveGradePolicyBypass,
    AaEffectiveGradePolicySnapshot,
    AaGradeChangeRequest,
    AaGradeCorrection,
    AaGradeIdentityHead,
)
from app.models.academic_affairs_gpa_policy import AaGpaPointPolicy
from app.models.academic_affairs_program_transition import ProgramTransitionAssessment
from app.models.academic_affairs_student_fact import StudentAcademicFact
from app.models.academic_affairs_stage_c3 import (
    ArchiveManifest,
    GraduationDecisionFact,
    GraduationEvaluationRun,
    PostArchiveCorrectionCase,
)


# Stage C1 temporal integrity: the migration already upgrades effective_date to
# DATETIME(6). Keep ORM metadata/create_all on the exact same precision too; otherwise
# fast-schema tests (and any metadata-created local DB) truncate the due time to whole
# seconds while StudentAcademicFact keeps microseconds, which can manufacture a false
# "effective time before current fact" conflict.
AaStatusChange.__table__.c.effective_date.type = DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")

# Graduation immutable evidence has grown beyond the legacy seven-item projection.
# Existing databases are upgraded by 20260810_grad_audit_text; keep metadata/create_all
# on the same TEXT contract so FAST_TEST_SCHEMA and fresh installs cannot recreate the
# historical VARCHAR(4000) capacity bug.
AaGraduationAuditResult.__table__.c.item_results_json.type = Text()


# 模型注册阶段只允许注册模型/ORM 元数据，不反向 import 业务 Service。
# Program expand 列与成绩增量列都通过正式 extension owner 安装；两者只镜像 migration
# 已声明的 schema，不在注册阶段猜历史值、做 backfill 或提前收紧约束。
# 有效成绩兼容、当前学期、ACTIVE-only、fail-closed 监听器统一由
# ``app.modules.academic_affairs.services`` 在基础模型与 db_service 初始化完成后安装。
# 这样保留原安全语义，同时避免：services -> db_service -> app.models -> registry -> services
# 的冷启动循环导入。
install_academic_program_extensions()
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
    "AaEffectiveGradePolicy",
    "AaEffectiveGradePolicyBypass",
    "AaEffectiveGradePolicySnapshot",
    "AaGradeChangeRequest",
    "AaGradeCorrection",
    "AaGradeIdentityHead",
    "AaGpaPointPolicy",
    "StudentAcademicFact",
    "ProgramTransitionAssessment",
    "GraduationEvaluationRun",
    "GraduationDecisionFact",
    "ArchiveManifest",
    "PostArchiveCorrectionCase",
]
