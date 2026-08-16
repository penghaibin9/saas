"""A-W4 Course Catalog specification consumed by Academic File Exchange.

This module does not own FileObject/ImportJob lifecycle and does not expose a
route.  It freezes the server-generated workbook and adapts the existing secure
XLSX reader to the fixed-query Course dry-run bridge.  The active Academic File
Exchange service can therefore add one small dispatch branch later without
copying parser or domain validation logic.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.services import xlsx_util

from .academic_affairs_school_setup_course_preflight_service import course_catalog_dry_run
from .academic_affairs_school_setup_import_contract import (
    COURSE_HEADER_MAP,
    COURSE_REQUIRED_FIELDS,
    COURSE_TEMPLATE_VERSION,
)

_COURSE_TEMPLATE_SAMPLE = {
    "课程代码": "CS101",
    "版本": 1,
    "课程名称": "Python程序设计",
    "课程类别": "MAJOR_CORE",
    "课程性质": "REQUIRED",
    "学分": 3.0,
    "总学时": 48,
    "理论学时": 32,
    "实践学时": 16,
    "实验学时": 0,
    "上机学时": 0,
    "考核方式": "EXAM",
    "开课单位ID": "",
    "课程负责人ID": "",
    "是否核心课": "是",
    "先修课代码": "MATH101,ENG101",
}

_COURSE_TEMPLATE_NOTES = (
    "课程稳定键为 courseCode + version；课程名称不是覆盖键。",
    "新课程代码必须从 v1 开始；已有课程只能导入当前 ENABLED 版本的直接后继版本。",
    "课程类别：PUBLIC_BASIC / DISCIPLINE_BASIC / MAJOR_CORE / MAJOR_ELECTIVE / PRACTICE。",
    "课程性质：REQUIRED / ELECTIVE / LIMITED_ELECTIVE / PUBLIC_ELECTIVE。",
    "考核方式：EXAM / CHECK。",
    "先修课仅填写课程代码，多个代码可用逗号分隔；当前 Course Authority 只校验代码格式。",
    "导入只进入服务端 FileObject + ImportJob；预检通过后仍需 expectedVersion 确认。",
)


def course_catalog_template_headers() -> list[str]:
    return list(COURSE_HEADER_MAP.keys())


def course_catalog_required_headers() -> list[str]:
    return [
        title
        for title, field in COURSE_HEADER_MAP.items()
        if field in COURSE_REQUIRED_FIELDS
    ]


def build_course_catalog_import_template() -> bytes:
    headers = course_catalog_template_headers()
    return xlsx_util.build_template_xlsx(
        headers,
        sample=[_COURSE_TEMPLATE_SAMPLE.get(title, "") for title in headers],
        notes=list(_COURSE_TEMPLATE_NOTES),
        required=course_catalog_required_headers(),
    )


def _empty_course_catalog_preview() -> dict:
    message = "课程导入文件没有数据行，请至少填写一门课程后重新预检"
    return {
        "totalRows": 0,
        "validRows": 0,
        "invalidRows": 1,
        "createRows": 0,
        "reuseRows": 0,
        "conflictRows": 0,
        "rejectRows": 1,
        "items": [{
            "row": 0,
            "businessKey": "",
            "action": "REJECT",
            "code": "COURSE_SOURCE_EMPTY",
            "message": message,
            "evidence": {"dataRows": 0},
            "howToResolve": "保留模板表头并至少填写一门课程后重新上传",
        }],
        "errors": [{
            "row": 0,
            "field": "file",
            "code": "COURSE_SOURCE_EMPTY",
            "message": message,
            "evidence": {"dataRows": 0},
            "howToResolve": "保留模板表头并至少填写一门课程后重新上传",
        }],
    }


def parse_and_validate_course_catalog(
    source_path: Path,
    *,
    user: dict,
    reader: Callable[[Path, dict[str, str]], list[dict]],
) -> tuple[list[dict], dict]:
    """Use the caller's already security-gated XLSX reader, then domain dry-run."""
    rows = reader(source_path, COURSE_HEADER_MAP)
    if not rows:
        return rows, _empty_course_catalog_preview()
    preview = course_catalog_dry_run(rows, user)
    return rows, preview


def course_catalog_file_exchange_contract() -> dict:
    return {
        "templateVersion": COURSE_TEMPLATE_VERSION,
        "headerMap": dict(COURSE_HEADER_MAP),
        "requiredFields": sorted(COURSE_REQUIRED_FIELDS),
        "publicImportEnabled": False,
        "confirmOwner": "INT_SHARED_DATA_EXCHANGE",
    }
