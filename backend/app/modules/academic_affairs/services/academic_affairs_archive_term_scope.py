"""教务归档 · 入学年级与历史学期范围纯策略。

只回答某个 cohort 在指定学期是否处于培养方案 1..12 学期范围：
- IN_SCOPE: 可参与该学期 PROGRAM/TEACHING_TASK 归档核验；
- OUT_OF_SCOPE: 合法的未来届或已超学制届，不应阻断该历史学期；
- INVALID: 年级/学年格式脏数据，必须由调用方 fail-closed。
"""
from __future__ import annotations


def cohort_term_scope(year_code, term_no, grade_year) -> dict:
    try:
        start_year = int(str(year_code or "").split("-")[0])
        grade = int(str(grade_year or "").strip())
        term = int(term_no or 0)
    except (TypeError, ValueError):
        return {"state": "INVALID", "planTerm": None, "rawPlanTerm": None}
    if term not in {1, 2} or start_year < 2000 or grade < 2000:
        return {"state": "INVALID", "planTerm": None, "rawPlanTerm": None}
    raw = (start_year - grade) * 2 + term
    if not 1 <= raw <= 12:
        return {"state": "OUT_OF_SCOPE", "planTerm": None, "rawPlanTerm": raw}
    return {"state": "IN_SCOPE", "planTerm": raw, "rawPlanTerm": raw}
