"""教务归档运营规则兼容入口。

课表、考务和成绩规则已经拆为纯策略并由正式归档 Service 显式调用。
本文件只保留历史测试/调用所需函数名，不再覆盖任何模块函数。
"""
from __future__ import annotations

from . import academic_affairs_archive_service as _canonical
from . import academic_affairs_archive_operational_policy as _operational
from . import academic_affairs_archive_rule_evaluator as _semantic
from . import academic_affairs_archive_domain_policy as _domain

_status = _operational._status
_schedule_gate_result = _operational.schedule_gate_result
_exam_gate_result = _operational.exam_gate_result
_evaluate_schedule = _operational.evaluate_schedule
_evaluate_exam = _operational.evaluate_exam


def _grade_gate_result(tasks, *, active_rechecks: int = 0, active_changes: int = 0):
    tasks = list(tasks or [])
    if not tasks:
        return _canonical._result(0, False, "本学期没有成绩任务")
    unfinished = [
        row for row in tasks
        if _status(getattr(row, "status", None)) not in {"PUBLISHED", "ARCHIVED"}
    ]
    blockers = []
    if unfinished:
        blockers.append(f"未发布/未归档成绩任务 {len(unfinished)} 个")
    if active_rechecks:
        blockers.append(f"本学期在途复查 {int(active_rechecks)} 条")
    if active_changes:
        blockers.append(f"本学期在途成绩更正 {int(active_changes)} 条")
    return _canonical._result(
        len(tasks),
        not blockers,
        "成绩任务均已发布且无在途复查/更正" if not blockers else "，".join(blockers),
    )


def _evaluate_grade(db, term_code):
    result = _semantic.evaluate_grade(db, term_code, {})
    return _domain.apply_effective_grade_policy_debt(db, term_code, result)


_evaluate_domains = _canonical._evaluate_domains
run_check = _canonical.run_check
precheck = _canonical.precheck


def __getattr__(name):
    return getattr(_canonical, name)
