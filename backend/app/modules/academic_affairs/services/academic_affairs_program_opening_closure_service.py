"""培养方案应开与教学任务实开差异兼容入口。

正式实现已经收口到 ``academic_affairs_program_governance_service``；本文件仅兼容历史导入路径。
不建立教学执行计划第二主表，也不再维护重复的数据范围、差异摘要和任务核对逻辑。
"""
from __future__ import annotations

from . import academic_affairs_program_governance_service as _canonical
from . import academic_affairs_program_quality_service as _validator

opening_differences = _canonical.opening_differences
validate_program_db = _canonical.validate_program_db
validate_program = _canonical.validate_program
program_governance_summary = _canonical.program_governance_summary


def _plan_term_no(year_code, term_no, grade_year):
    """兼容归档规则评估器的历史调用，唯一算法来自正式方案校验器。"""
    return _validator._plan_term_no(year_code, term_no, grade_year)


def __getattr__(name):
    return getattr(_canonical, name)
