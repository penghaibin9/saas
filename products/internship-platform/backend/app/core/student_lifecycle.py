"""学生跨域生命周期的统一读口径。

正式存储值来自《数据库设计冻结总册》§5.1。生命周期只负责门户、待办和跨域导航，
不参与教师数据权限判定；各业务模块曾写入的简称只在读取时兼容，不迁移数据库。
"""
from __future__ import annotations


ADMITTED = "ADMITTED"
PRE_STUDENT_VERIFIED = "PRE_STUDENT_VERIFIED"
REGISTERED_PENDING_ENROLLMENT = "REGISTERED_PENDING_ENROLLMENT"
ENROLLED = "ENROLLED"
GRADUATING = "GRADUATING"
INTERN = "INTERN"
GRADUATED = "GRADUATED"
ALUMNI = "ALUMNI"

STUDENT_LIFECYCLE_STAGES = (
    ADMITTED,
    PRE_STUDENT_VERIFIED,
    REGISTERED_PENDING_ENROLLMENT,
    ENROLLED,
    GRADUATING,
    INTERN,
    GRADUATED,
    ALUMNI,
)

_ALIASES = {
    "ORIENTATION": ADMITTED,
    "ON_CAMPUS": ENROLLED,
    "STUDYING": ENROLLED,
    "INTERNSHIP": INTERN,
    "GRADUATION_DESIGN": GRADUATING,
    "EMPLOYMENT": GRADUATING,
}

_LABELS = {
    ADMITTED: "新生阶段·已录取",
    PRE_STUDENT_VERIFIED: "新生阶段·预报到已核验",
    REGISTERED_PENDING_ENROLLMENT: "新生阶段·已报到待注册",
    ENROLLED: "在读阶段",
    GRADUATING: "毕业阶段",
    INTERN: "岗位实习阶段",
    GRADUATED: "已毕业",
    ALUMNI: "校友",
}

_PHASES = {
    ADMITTED: "ORIENTATION",
    PRE_STUDENT_VERIFIED: "ORIENTATION",
    REGISTERED_PENDING_ENROLLMENT: "ORIENTATION",
    ENROLLED: "ON_CAMPUS",
    INTERN: "INTERNSHIP",
    GRADUATING: "GRADUATION",
    GRADUATED: "GRADUATED",
    ALUMNI: "ALUMNI",
}


def normalize_student_stage(stage: str | None) -> str:
    """返回当前可识别的存储口径；未知值原样保留，便于发现历史脏数据。"""
    value = (stage or ADMITTED).strip().upper()
    return _ALIASES.get(value, value)


def student_stage_label(stage: str | None) -> str:
    """返回四阶段用户文案，未知值不静默伪装成合法阶段。"""
    normalized = normalize_student_stage(stage)
    return _LABELS.get(normalized, normalized)


def student_lifecycle_phase(stage: str | None) -> str:
    """折叠为四个主要门户阶段，并保留已毕业/校友两个终态。"""
    normalized = normalize_student_stage(stage)
    return _PHASES.get(normalized, normalized)
