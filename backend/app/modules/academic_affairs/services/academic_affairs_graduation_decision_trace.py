"""Stage D adapter from the shared graduation evaluator to DecisionTrace.

The evaluator remains the only authority. This module reads its already-computed
``overall`` and item results and explains the first blocking item deterministically;
it never recalculates credits, program bindings, internship, design or discipline.
"""
from __future__ import annotations

from datetime import datetime

from .academic_affairs_decision_trace import build_decision_trace, render_zh_cn


_ITEM_RULE = {
    "COURSE_REQUIRED": "REQUIRED_COURSE_FAILED",
    "COURSE_ELECTIVE": "ELECTIVE_CREDITS_INSUFFICIENT",
    "PRACTICE": "PRACTICE_CREDITS_INSUFFICIENT",
    "INTERNSHIP": "INTERNSHIP_INCOMPLETE",
    "GRADUATION_DESIGN": "GRADUATION_DESIGN_INCOMPLETE",
    "DISCIPLINE": "DISCIPLINE_BLOCK",
}

_RESOLUTIONS = {
    "PROGRAM_UNRESOLVED": [
        {"code": "RESOLVE_PROGRAM_BINDING", "label": "联系教务老师核对并确定适用培养方案"},
    ],
    "TOTAL_CREDITS_INSUFFICIENT": [
        {"code": "REVIEW_CREDIT_GAP", "label": "核对缺失学分并按培养方案完成修读"},
    ],
    "REQUIRED_COURSE_FAILED": [
        {"code": "COMPLETE_REQUIRED_COURSES", "label": "完成未通过的必修课程后重新核验"},
    ],
    "ELECTIVE_CREDITS_INSUFFICIENT": [
        {"code": "COMPLETE_ELECTIVE_CREDITS", "label": "补足培养方案要求的选修学分"},
    ],
    "PRACTICE_CREDITS_INSUFFICIENT": [
        {"code": "COMPLETE_PRACTICE_CREDITS", "label": "补足培养方案要求的实践环节学分"},
    ],
    "INTERNSHIP_INCOMPLETE": [
        {"code": "COMPLETE_INTERNSHIP", "label": "完成岗位实习正式流程后重新核验"},
    ],
    "GRADUATION_DESIGN_INCOMPLETE": [
        {"code": "COMPLETE_GRADUATION_DESIGN", "label": "完成毕业设计正式流程后重新核验"},
    ],
    "DISCIPLINE_BLOCK": [
        {"code": "RESOLVE_DISCIPLINE", "label": "按学校流程核对并处理未解除处分"},
    ],
    "ACADEMIC_DATA_UNKNOWN": [
        {"code": "COMPLETE_FORMAL_EVIDENCE", "label": "联系对应业务老师补齐或核对正式数据"},
    ],
    "GRADUATION_ALREADY_FINAL": [
        {"code": "VIEW_FINAL_DECISION", "label": "查看已经形成的正式毕业结论"},
    ],
}


def _masked_student_ref(student) -> str:
    value = str(getattr(student, "student_no", "") or "").strip()
    if len(value) <= 4:
        return "masked:student"
    return f"masked:{value[:4]}{'*' * max(2, len(value) - 6)}{value[-2:]}"


def _program_unresolved(item: dict) -> bool:
    status = str(item.get("programResolutionStatus") or "").upper()
    return status not in ("", "RESOLVED")


def _is_final_status(item: dict) -> bool:
    if str(item.get("item") or "").upper() != "STATUS":
        return False
    evidence = str(item.get("evidence") or "").upper()
    return any(value in evidence for value in ("GRADUATED", "COMPLETED"))


def _rule_for(item: dict) -> str:
    code = str(item.get("item") or "").upper()
    result = str(item.get("result") or "").upper()
    if _is_final_status(item):
        return "GRADUATION_ALREADY_FINAL"
    if _program_unresolved(item):
        return "PROGRAM_UNRESOLVED"
    if code == "CREDIT" and result == "FAIL":
        return "TOTAL_CREDITS_INSUFFICIENT"
    if result == "FAIL" and code in _ITEM_RULE:
        return _ITEM_RULE[code]
    # UNKNOWN and unsupported legacy/advisory items remain explicit UNKNOWN; Stage C3
    # already made them fail closed and this explanation layer must not reinterpret them.
    return "ACADEMIC_DATA_UNKNOWN"


def build_graduation_decision_trace(student, evaluated: dict) -> dict | None:
    """Explain an existing evaluator result; return None for an all-PASS decision."""
    if str(evaluated.get("overall") or "").upper() == "SYSTEM_PASSED":
        return None
    items = list(evaluated.get("items") or [])
    failed = [item for item in items if str(item.get("result") or "").upper() != "PASS"]
    blocker = failed[0] if failed else {"item": "UNKNOWN", "result": "UNKNOWN", "owner": "AA_STAFF"}
    rule_code = _rule_for(blocker)
    snapshot = evaluated.get("inputSnapshot") or {}
    at = snapshot.get("evaluatedAt") or datetime.utcnow().isoformat()
    evaluator_version = snapshot.get("evaluatorVersion") or "STAGE_C3_V1"

    safe_failed = [{
        "item": str(item.get("item") or "UNKNOWN"),
        "result": str(item.get("result") or "UNKNOWN"),
        "owner": str(item.get("owner") or ""),
        "evidence": str(item.get("evidence") or ""),
    } for item in failed]
    safe_passed = [{
        "item": str(item.get("item") or "UNKNOWN"),
        "result": "PASS",
    } for item in items if str(item.get("result") or "").upper() == "PASS"]

    return build_decision_trace(
        domain="GRADUATION",
        action="EVALUATE",
        decision="DENIED",
        rule_code=rule_code,
        rule_version=str(evaluator_version),
        subject={"studentId": _masked_student_ref(student)},
        target={"scope": "CURRENT_GRADUATION_EVALUATION"},
        failed_nodes=safe_failed,
        passed_nodes=safe_passed,
        available_resolutions=list(_RESOLUTIONS.get(rule_code, [])),
        evaluated_at=at,
    )


def build_graduation_student_explanation(student, evaluated: dict) -> tuple[dict | None, dict | None]:
    trace = build_graduation_decision_trace(student, evaluated)
    return trace, (render_zh_cn(trace, audience="student") if trace else None)
