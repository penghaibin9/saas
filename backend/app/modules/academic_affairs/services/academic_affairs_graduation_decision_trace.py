"""Stage D adapter from the shared graduation evaluator to DecisionTrace.

The evaluator remains the only authority. This module reads its already-computed
``overall`` and item results and explains the first blocking item deterministically;
it never recalculates credits, program bindings, internship, design or discipline.
"""
from __future__ import annotations

from app.core.exceptions import AppException

from . import academic_affairs_graduation_service as graduation_service
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


def _is_blocking_item(item: dict) -> bool:
    """Mirror the evaluator's blocking boundary without recalculating business truth."""
    code = str(item.get("item") or "").upper()
    result = str(item.get("result") or "").upper()
    if result == "PASS":
        return False
    if result == "FAIL":
        return True
    if result == "UNKNOWN":
        required_unknown = set(getattr(graduation_service, "_BLOCKING_UNKNOWN_ITEMS", ()) or ())
        required_unknown.add("ARCHIVE")
        return code in required_unknown
    # The immutable evaluator fails closed on malformed/unknown result states; the trace
    # must not hide that denial merely because the value is outside the known tri-state.
    return True


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
    # UNKNOWN and unsupported legacy items remain explicit UNKNOWN; this explanation layer
    # only chooses an actual evaluator blocker and never reclassifies advisory UNKNOWN rows.
    return "ACADEMIC_DATA_UNKNOWN"


def _evaluator_identity(evaluated: dict) -> tuple[str, str]:
    """Read the exact evaluator time/version; never fabricate missing audit identity."""
    snapshot = evaluated.get("inputSnapshot")
    if not isinstance(snapshot, dict):
        raise AppException(
            "DATA_CONFLICT",
            "毕业核验结果缺少 evaluator 输入快照，无法生成可审计 DecisionTrace",
            http_status=409,
        )
    evaluated_at = str(snapshot.get("evaluatedAt") or "").strip()
    evaluator_version = str(snapshot.get("evaluatorVersion") or "").strip()
    if not evaluated_at or not evaluator_version:
        raise AppException(
            "DATA_CONFLICT",
            "毕业核验结果缺少 evaluator 时间或版本，无法生成可审计 DecisionTrace",
            http_status=409,
        )
    return evaluated_at, evaluator_version


def build_graduation_decision_trace(student, evaluated: dict) -> dict | None:
    """Explain an existing evaluator result; return None for an all-PASS decision.

    The evaluator's raw evidence may contain model IDs, internal enum values or provider
    exception names. Student-facing DecisionTrace therefore carries only the already-made
    node item/result classification; the deterministic rule text supplies the explanation.
    Administrative preview APIs still receive the full evaluator ``items`` separately.

    ``evaluatedAt`` and ``evaluatorVersion`` are part of the decision evidence. Missing
    values are rejected instead of being replaced with the current clock/default version,
    because a fabricated identity would make an incomplete evaluator result appear audited.
    """
    if str(evaluated.get("overall") or "").upper() == "SYSTEM_PASSED":
        return None
    items = list(evaluated.get("items") or [])
    blockers = [item for item in items if _is_blocking_item(item)]
    blocker = blockers[0] if blockers else {"item": "UNKNOWN", "result": "UNKNOWN"}
    rule_code = _rule_for(blocker)
    evaluated_at, evaluator_version = _evaluator_identity(evaluated)

    safe_failed = [{
        "item": str(item.get("item") or "UNKNOWN"),
        "result": str(item.get("result") or "UNKNOWN"),
    } for item in blockers]
    safe_passed = [{
        "item": str(item.get("item") or "UNKNOWN"),
        "result": "PASS",
    } for item in items if str(item.get("result") or "").upper() == "PASS"]

    return build_decision_trace(
        domain="GRADUATION",
        action="EVALUATE",
        decision="DENIED",
        rule_code=rule_code,
        rule_version=evaluator_version,
        subject={"studentId": _masked_student_ref(student)},
        target={"scope": "CURRENT_GRADUATION_EVALUATION"},
        failed_nodes=safe_failed,
        passed_nodes=safe_passed,
        available_resolutions=list(_RESOLUTIONS.get(rule_code, [])),
        evaluated_at=evaluated_at,
    )


def build_graduation_student_explanation(student, evaluated: dict) -> tuple[dict | None, dict | None]:
    trace = build_graduation_decision_trace(student, evaluated)
    return trace, (render_zh_cn(trace, audience="student") if trace else None)
