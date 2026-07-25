"""学生主档写入合同（学生主档统一整改 阶段 B）。

`StudentProfile` 是学生身份的唯一真相，只能经 `student_master_application_service`
写入。本模块定义各入口共用的命令对象与来源枚举，避免每个调用方各自拼 ORM 字段。

为什么用命令对象而不是直接传 Schema：主档有四个来源（手工建档 / 公共导入 /
统一身份导入 / 迎新晋级），各自的请求体字段名不同，若让应用服务去认四种 Schema，
统一入口就会退化成四个分支。命令对象把「入口差异」挡在服务之外。
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ── 写入来源：进 StudentStageEvent.source_module 与审计，用于事后追溯是谁建的档 ──
SOURCE_MANUAL = "student"                 # 管理端手工建档 POST /students
SOURCE_BULK_IMPORT = "student-import"     # 公共学生导入 /import/students/*
SOURCE_IDENTITY_IMPORT = "identity-import"  # 系统管理统一师生身份导入（正式批量入口）
SOURCE_ROSTER_IMPORT = "academic-affairs"   # 教务学籍导入（迁移期，最终并入身份导入）
SOURCE_ADMISSION = "orientation"            # 迎新录取候选人正式晋级（阶段 D）

VALID_SOURCES = frozenset({
    SOURCE_MANUAL, SOURCE_BULK_IMPORT, SOURCE_IDENTITY_IMPORT,
    SOURCE_ROSTER_IMPORT, SOURCE_ADMISSION,
})

# ── 错误码（沿用仓库既有 AppException code 口径，不新造一套） ──
ERR_STUDENT_NO_CONFLICT = "DATA_CONFLICT"   # 学号已被占用（含已作废档案）
ERR_VERSION_CONFLICT = "DATA_CONFLICT"      # expectedVersion 不匹配（并发覆盖）
ERR_VALIDATION = "VALIDATION_ERROR"
ERR_ORG_SCOPE = "NO_DATA_SCOPE"


@dataclass
class StudentCreateCommand:
    """建档命令。组织三件套允许缺省，由 student_org_validator 反推补齐与校验。"""
    student_no: str
    real_name: str
    source: str = SOURCE_MANUAL
    gender: str | None = None
    grade: str | None = None
    college_id: object = None
    major_id: object = None
    class_id: object = None
    phone: str | None = None
    id_card: str | None = None
    current_stage: str | None = None      # None → 由服务取 ADMITTED
    student_status: str = "NORMAL"
    enroll_date: object = None
    remark: str | None = None
    # 允许复活同学号的已作废主档（学号租户内永久唯一，作废后同号只能复活原 PK）
    allow_restore: bool = True

    def normalized_no(self) -> str:
        return str(self.student_no or "").strip()

    def normalized_name(self) -> str:
        return str(self.real_name or "").strip()


@dataclass
class StudentIdentityUpdateCommand:
    """身份字段更正。组织归属不在此列——那必须走学籍异动，见 §4.3 裁决。"""
    expected_version: int
    real_name: str | None = None
    gender: str | None = None
    grade: str | None = None
    phone: str | None = None
    remark: str | None = None
    source: str = SOURCE_MANUAL


@dataclass
class StudentCreateResult:
    """建档结果。restored=True 表示复活了原有作废档案而非新建，调用方需如实回显。"""
    student_id: int
    student_no: str
    restored: bool = False
    warnings: list[str] = field(default_factory=list)
