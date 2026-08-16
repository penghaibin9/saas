"""INT Program workbook specification for later Academic File Exchange wiring.

This module freezes the six-sheet workbook contract only. It deliberately does
not parse XLSX bytes, open sessions, create ImportJob/FileObject rows, or own the
shared dispatcher. The existing Academic File Exchange must consume this spec
when the shared owner is available.
"""
from __future__ import annotations

from .academic_affairs_school_setup_import_contract import (
    PROGRAM_GROUP_BINDING,
    PROGRAM_GROUP_COURSE,
    PROGRAM_GROUP_CREDIT_REQUIREMENT,
    PROGRAM_GROUP_GRADUATION,
    PROGRAM_GROUP_MAIN,
    PROGRAM_GROUP_PRACTICE,
    PROGRAM_REQUIRED_FIELDS_BY_GROUP,
    PROGRAM_TEMPLATE_VERSION,
)

PROGRAM_SHEET_MAIN = "培养方案"
PROGRAM_SHEET_COURSE = "方案课程"
PROGRAM_SHEET_CREDIT_REQUIREMENT = "学分要求"
PROGRAM_SHEET_PRACTICE = "实践环节"
PROGRAM_SHEET_GRADUATION = "毕业要求"
PROGRAM_SHEET_BINDING = "适用范围"

PROGRAM_SHEET_ORDER = (
    PROGRAM_SHEET_MAIN,
    PROGRAM_SHEET_COURSE,
    PROGRAM_SHEET_CREDIT_REQUIREMENT,
    PROGRAM_SHEET_PRACTICE,
    PROGRAM_SHEET_GRADUATION,
    PROGRAM_SHEET_BINDING,
)

PROGRAM_GROUP_BY_SHEET = {
    PROGRAM_SHEET_MAIN: PROGRAM_GROUP_MAIN,
    PROGRAM_SHEET_COURSE: PROGRAM_GROUP_COURSE,
    PROGRAM_SHEET_CREDIT_REQUIREMENT: PROGRAM_GROUP_CREDIT_REQUIREMENT,
    PROGRAM_SHEET_PRACTICE: PROGRAM_GROUP_PRACTICE,
    PROGRAM_SHEET_GRADUATION: PROGRAM_GROUP_GRADUATION,
    PROGRAM_SHEET_BINDING: PROGRAM_GROUP_BINDING,
}

PROGRAM_HEADER_MAP_BY_GROUP = {
    PROGRAM_GROUP_MAIN: {
        "培养方案系列键": "programSeriesKey",
        "版本": "programVersion",
        "方案名称": "programName",
        "专业ID": "majorId",
        "适用年级": "gradeYear",
        "毕业总学分": "totalCredits",
        "学制年限(断言)": "educationYears",
    },
    PROGRAM_GROUP_COURSE: {
        "培养方案系列键": "programSeriesKey",
        "版本": "programVersion",
        "课程代码": "courseCode",
        "课程版本": "courseVersion",
        "开课学期": "openTermNo",
        "课程模块": "module",
        "编班方式": "formationMode",
        "学分快照(断言)": "creditSnapshot",
    },
    PROGRAM_GROUP_CREDIT_REQUIREMENT: {
        "培养方案系列键": "programSeriesKey",
        "版本": "programVersion",
        "课程模块": "module",
        "目标学分": "creditTarget",
    },
    PROGRAM_GROUP_PRACTICE: {
        "培养方案系列键": "programSeriesKey",
        "版本": "programVersion",
        "实践环节名称": "segmentName",
        "实践环节类型": "segmentType",
        "开设学期": "openTermNo",
        "周数": "weeks",
        "学分": "credit",
        "组织方式": "orgMode",
        "考核方式": "assessmentMode",
        "地点/承担单位": "location",
        "排序": "sortOrder",
    },
    PROGRAM_GROUP_GRADUATION: {
        "培养方案系列键": "programSeriesKey",
        "版本": "programVersion",
        "毕业要求类别": "category",
        "毕业要求内容": "content",
        "排序": "sortOrder",
    },
    PROGRAM_GROUP_BINDING: {
        "培养方案系列键": "programSeriesKey",
        "版本": "programVersion",
        "专业ID": "majorId",
        "适用年级": "gradeYear",
        "绑定范围": "bindingScope",
        "班级ID": "classId",
    },
}

PROGRAM_FILLING_NOTES = (
    "programSeriesKey 是不可变业务系列键；不得由专业、年级、方案名称或绑定范围自动生成。",
    "普通导入 DEFINITION phase 只创建/复用 Program 定义；CREATE 必须落 DRAFT，不得同时激活适用范围。",
    "适用范围只在 Program 已正式发布/启用后，通过第二轮 BINDING phase 确认 ACTIVE binding。",
    "COURSE 必须引用 exact courseCode + courseVersion；课程名称不是匹配键。",
    "编班方式 formationMode 必须显式填写 ADMIN_FIXED / SELECTABLE / MERGED / RETAKE / LAYERED；禁止从课程性质或名称推断。",
    "课程模块 module 必填，并且必须在“学分要求”工作表中有对应目标学分。",
    "学制年限和学分快照都是断言字段：分别以 Major.education_years 和 exact Course version credit 为权威，不会反向覆盖主数据。",
    "历史 v3-only 当前快照不属于普通导入；没有可证明 v1/v2 链时必须走独立 baseline migration policy。",
)


def _required_headers(group: str) -> tuple[str, ...]:
    header_map = PROGRAM_HEADER_MAP_BY_GROUP[group]
    required_fields = PROGRAM_REQUIRED_FIELDS_BY_GROUP[group]
    return tuple(
        title for title, field in header_map.items() if field in required_fields
    )


def program_file_exchange_contract() -> dict:
    """Return a deterministic, JSON-safe description of the future workbook."""
    sheets = []
    for sheet_name in PROGRAM_SHEET_ORDER:
        group = PROGRAM_GROUP_BY_SHEET[sheet_name]
        header_map = PROGRAM_HEADER_MAP_BY_GROUP[group]
        sheets.append({
            "sheetName": sheet_name,
            "logicalGroup": group,
            "headers": list(header_map.keys()),
            "headerMap": dict(header_map),
            "requiredHeaders": list(_required_headers(group)),
        })
    return {
        "templateVersion": PROGRAM_TEMPLATE_VERSION,
        "workbookMode": "MULTI_SHEET_EXACT_NAMES",
        "sheetCount": len(sheets),
        "sheets": sheets,
        "confirmPhases": ["DEFINITION", "BINDING"],
        "publicImportEnabled": False,
        "confirmOwner": "INT_SHARED_DATA_EXCHANGE",
        "notes": list(PROGRAM_FILLING_NOTES),
    }
