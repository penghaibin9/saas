"""教师微信成绩闭环旧兼容入口。

批量保存、单生校验、质量报告和提交门禁已合并到 ``mobile_academic_affairs_facade``；
本模块仅保留无副作用兼容导出。
"""
from . import mobile_academic_affairs_facade as _service

_score = _service._score
normalize_mobile_grade_row = _service.normalize_mobile_grade_row
build_grade_quality_report = _service.build_grade_quality_report
teacher_grade_enter_score = _service.teacher_grade_enter_score
teacher_grade_batch_save = _service.teacher_grade_batch_save
teacher_grade_quality_report = _service.teacher_grade_quality_report
teacher_grade_submit_task = _service.teacher_grade_submit_task


def __getattr__(name):
    return getattr(_service, name)


__all__ = [
    "normalize_mobile_grade_row",
    "build_grade_quality_report",
    "teacher_grade_enter_score",
    "teacher_grade_batch_save",
    "teacher_grade_quality_report",
    "teacher_grade_submit_task",
]
