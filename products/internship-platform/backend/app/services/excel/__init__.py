"""公共 Excel 导入导出底座（V1.1）。

对外统一入口：业务模块 `from app.services.excel import ...`。
- spec：ColumnSpec / ImportSpec / ExportSpec 接入契约
- pipeline：build_template / read_upload / pre_validate / build_error_rows / confirm_import / build_export
- validators：可复用字段校验器（手机号/身份证/统一社会信用代码/日期/枚举/长度…）
- job_service：通用导入记录（t_excel_import_job）

底层 xlsx 读写复用 app.services.xlsx_util（保持四模块既有兼容，不重复造）。
"""
from __future__ import annotations

from . import job_service, validators
from .pipeline import (build_error_rows, build_export, build_template, confirm_import,
                       pre_validate, read_upload)
from .spec import ColumnSpec, ExportSpec, ImportSpec

__all__ = [
    "ColumnSpec", "ImportSpec", "ExportSpec",
    "build_template", "read_upload", "pre_validate", "build_error_rows",
    "confirm_import", "build_export",
    "validators", "job_service",
]
