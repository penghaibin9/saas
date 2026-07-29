"""教务归档历史兼容入口。

正式归档能力已经收口到 ``academic_affairs_archive_service``；异动和毕业审核时间范围规则
来自纯策略模块。旧调用路径继续可用，但本文件不再复制批次状态机或修改任何模块函数。
"""
from __future__ import annotations

from . import academic_affairs_archive_service as _canonical
from . import academic_affairs_archive_domain_policy as _policy
from . import academic_affairs_archive_rule_evaluator as _semantic

_ACTIVE_RECHECK_STATUSES = {"SUBMITTED"}
_ACTIVE_STATUS_CHANGE_STATUSES = {"DRAFT", "SUBMITTED", "IN_REVIEW"}


def _evaluate_grade(db, term_code):
    result = _semantic.evaluate_grade(db, term_code, {})
    return _policy.apply_effective_grade_policy_debt(db, term_code, result)


def _evaluate_status_change(db, term_id, term_code):
    return _policy.evaluate_status_change(db, term_id, term_code)


def _evaluate_graduation(db, term_id):
    return _policy.evaluate_graduation(db, term_id)


_evaluate_domains = _canonical._evaluate_domains
run_check = _canonical.run_check
precheck = _canonical.precheck
get_batch = _canonical.get_batch


def __getattr__(name):
    return getattr(_canonical, name)
