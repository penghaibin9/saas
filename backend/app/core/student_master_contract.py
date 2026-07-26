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
    # 是否允许复活同学号的已作废主档。**默认 False**：所有普通创建与批量导入都不得
    # 复活作废档案；只有「受控恢复」这一个显式动作会传 True（单独权限 + 原因 + 审计）。
    allow_restore: bool = False
    # 正式建档必须归属完整且自洽的学院/专业/班级；缺任一层级即拒绝，不接受默认组织兜底。
    require_complete_org: bool = False

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


# ── 导入决策（两个正式入口共用；口径见补充审计 §7/§8）──────────────────────
ACTION_CREATE = "CREATE"      # 新建主档
ACTION_REUSE = "REUSE"        # 复用已有主档（可能补齐了空字段）
ACTION_SKIP = "SKIP"          # 已存在且信息完整一致，幂等跳过
ACTION_CONFLICT = "CONFLICT"  # 阻断，需人工处理

# 冲突原因码：前端按此归类统计与回执文案，不要靠中文串匹配
CONFLICT_IDENTITY = "IDENTITY_CONFLICT"    # 学号/姓名/身份证 三者关系异常
CONFLICT_ORG = "ORG_CONFLICT"              # 已有完整组织与本次不一致
CONFLICT_VOIDED = "VOIDED_PROFILE"         # 学号属于已作废档案
CONFLICT_ACCOUNT = "ACCOUNT_OCCUPIED"      # 登录名被非学生账号占用
CONFLICT_DUP_IN_FILE = "DUPLICATE_IN_FILE"  # 同一文件内重复


@dataclass
class StudentResolution:
    """一行导入数据对既有主档的判定结果。

    预检与最终落库使用同一函数，保证「预检说能导入、落库却失败」不再发生；
    但预检结果不做缓存复用——落库时必须重新判定（期间数据可能已变）。
    """
    action: str
    student_id: int | None = None
    student_no: str = ""
    reason_code: str = ""
    message: str = ""
    # 复用时本次可补齐的空字段（字段名 → 新值），仅限原值为空者
    fillable: dict = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return self.action == ACTION_CONFLICT
