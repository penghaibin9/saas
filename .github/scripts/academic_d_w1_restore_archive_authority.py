from __future__ import annotations

import ast
import subprocess
from pathlib import Path

PATH = Path("backend/app/modules/academic_affairs/services/academic_affairs_archive_domain_policy.py")
BASE_SHA = "414216c4a79ff035aee87d70b35572572f5c0535"
BASE_PATH = str(PATH)


def _function_span(source: str, name: str) -> tuple[int, int]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            lines = source.splitlines(keepends=True)
            start = sum(len(line) for line in lines[: node.lineno - 1])
            end = sum(len(line) for line in lines[: node.end_lineno])
            while end < len(source) and source[end] == "\n":
                end += 1
            return start, end
    raise SystemExit(f"function not found: {name}")


def _function_source(source: str, name: str) -> str:
    start, end = _function_span(source, name)
    return source[start:end].rstrip() + "\n\n"


def _replace_function(source: str, name: str, replacement: str) -> str:
    start, end = _function_span(source, name)
    return source[:start] + replacement.rstrip() + "\n\n" + source[end:]


current = PATH.read_text(encoding="utf-8")
base = subprocess.check_output(
    ["git", "show", f"{BASE_SHA}:{BASE_PATH}"],
    text=True,
    encoding="utf-8",
)

# Restore mature Evaluation authority, changing only the two W1 state boundaries.
evaluation = _function_source(base, "evaluate_evaluation")
evaluation = evaluation.replace(
    '    if not term_id:\n        return _legacy_result(0, False, "未指定学期，无法核验学生评教")\n',
    '    if not term_id:\n        return _state_result(\n            "EVALUATION", "UNKNOWN", "未指定学期，无法核验学生评教",\n            rule_code="EVALUATION_TERM_SCOPE_UNKNOWN",\n        )\n',
)
evaluation = evaluation.replace(
    '    if not batches:\n        return _legacy_result(0, True, "本学期未启用学生评教，不作为归档阻断")\n',
    '    if not batches:\n        return _state_result(\n            "EVALUATION", "NOT_APPLICABLE", "本学期未启用学生评教，不作为归档阻断",\n            rule_code="EVALUATION_NOT_APPLICABLE",\n        )\n',
)
if "AaEvaluationAppeal.result_id.in_(result_ids)" not in evaluation:
    raise SystemExit("restored evaluation authority lost result-scoped appeal gate")
current = _replace_function(current, "evaluate_evaluation", evaluation)

# Restore mature Textbook OrderBatch -> Distribution -> FeeLedger authority, with W1 UNKNOWN/N/A wrappers.
textbook = _function_source(base, "evaluate_textbook")
textbook = textbook.replace(
    '    if not term_id:\n        return _legacy_result(0, False, "未指定学期，无法核验教材业务")\n',
    '    if not term_id:\n        return _state_result(\n            "TEXTBOOK", "UNKNOWN", "未指定学期，无法核验教材业务",\n            rule_code="TEXTBOOK_TERM_SCOPE_UNKNOWN",\n        )\n',
)
textbook = textbook.replace(
    '    if not orders:\n        return _legacy_result(0, True, "本学期未启用教材征订，不作为归档阻断")\n',
    '    if not orders:\n        return _state_result(\n            "TEXTBOOK", "NOT_APPLICABLE", "本学期未启用教材征订，不作为归档阻断",\n            rule_code="TEXTBOOK_NOT_APPLICABLE",\n        )\n',
)
for token in (
    "AaTextbookOrderBatch",
    "AaTextbookDistributionBatch",
    "AaTextbookDistributionRecord",
    "AaTextbookFeeLedger",
    "missing_distribution",
    "unfinished_distributions",
    "missing_fees",
    "unsettled",
):
    if token not in textbook:
        raise SystemExit(f"restored textbook authority missing token: {token}")
current = _replace_function(current, "evaluate_textbook", textbook)

# StatusChange: unable to scope a row is UNKNOWN, not PASS. A known active blocker still wins.
status_change = '''def evaluate_status_change(db, term_id, term_code):
    """Only close a term when every status-change record can be scoped or proven terminal."""
    from app.models import AaStatusChange, AaTerm

    term = None
    if term_id:
        term = db.query(AaTerm).filter(
            AaTerm.id == int(term_id),
            AaTerm.tenant_id == _tid(),
            AaTerm.is_deleted.is_(False),
        ).first()
    start_at = _day_start(getattr(term, "start_date", None)) if term else None
    end_at = _day_end(getattr(term, "end_date", None)) if term else None

    rows = db.query(AaStatusChange).filter(
        AaStatusChange.tenant_id == _tid(),
        AaStatusChange.is_deleted.is_(False),
    ).all()
    scoped = []
    unresolved = []
    for row in rows:
        row_term = str(getattr(row, "term_code", None) or "").strip()
        if term_code and row_term:
            if row_term == term_code:
                scoped.append(row)
            continue
        occurred_at = (
            getattr(row, "effective_date", None)
            or getattr(row, "created_at", None)
            or getattr(row, "updated_at", None)
        )
        if start_at and end_at and occurred_at:
            if start_at <= occurred_at <= end_at:
                scoped.append(row)
        elif not row_term:
            unresolved.append(row)

    active = [
        row for row in scoped
        if str(getattr(row, "status", None) or "").upper() in _ACTIVE_STATUS_CHANGE
    ]
    if active:
        return _state_result(
            "STATUS_CHANGE",
            "BLOCKED",
            (
                f"本学期仍有 {len(active)} 条学籍异动处于草稿/审批中"
                + (f"；另有 {len(unresolved)} 条异动无法确定学期范围，待迁移补齐" if unresolved else "")
            ),
            count=len(scoped),
            blocking_count=len(active) + len(unresolved),
            rule_code="STATUS_CHANGE_ACTIVE",
            evidence=[{"type": "UNRESOLVED_SCOPE", "count": len(unresolved)}] if unresolved else [],
        )
    if unresolved:
        return _state_result(
            "STATUS_CHANGE",
            "UNKNOWN",
            f"有 {len(unresolved)} 条学籍异动缺少学期与可用日期，无法确定是否属于当前归档范围；待迁移补齐",
            count=len(scoped),
            blocking_count=len(unresolved),
            rule_code="STATUS_CHANGE_SCOPE_UNKNOWN",
            evidence=[{"type": "UNRESOLVED_SCOPE", "count": len(unresolved)}],
        )
    return _state_result(
        "STATUS_CHANGE",
        "PASS",
        "本学期无在途学籍异动",
        count=len(scoped),
        rule_code="STATUS_CHANGE_CLOSED",
    )

'''
current = _replace_function(current, "evaluate_status_change", status_change)

# Reinstall the effective-grade debt gate removed by the W1 rewrite.
grade_debt = _function_source(base, "apply_effective_grade_policy_debt")
if "def apply_effective_grade_policy_debt" not in current:
    marker = "def evaluate_domains(db, term_id, term_code, college_ids=None):"
    if marker not in current:
        raise SystemExit("evaluate_domains insertion point missing")
    current = current.replace(marker, grade_debt + marker, 1)
else:
    current = _replace_function(current, "apply_effective_grade_policy_debt", grade_debt)

# Restore the mature orchestration: core authority -> semantic first batch -> grade debt -> domain overlays.
orchestrator = _function_source(base, "evaluate_domains")
current = _replace_function(current, "evaluate_domains", orchestrator)

# Final structural invariants.
for token in (
    "base = _core._evaluate_domains(db, term_id, term_code, college_ids)",
    "results = _semantic.evaluate_first_batch(",
    "apply_effective_grade_policy_debt(db, term_code, results[\"GRADE\"])",
    "AaTextbookOrderBatch",
    "AaTextbookDistributionBatch",
    "AaTextbookFeeLedger",
    "STATUS_CHANGE_SCOPE_UNKNOWN",
):
    if token not in current:
        raise SystemExit(f"final W1 policy missing token: {token}")
for forbidden in (
    "_semantic.evaluate_student_status(",
    "_semantic.evaluate_registration(",
    "_semantic.evaluate_exam(",
    "_semantic.evaluate_schedule(db, term_id, college_ids)",
    "_semantic.evaluate_grade(db, term_code, college_ids)",
    "from app.models import AaTextbookFee, AaTextbookOrder",
):
    if forbidden in current:
        raise SystemExit(f"invalid W1 policy wiring remains: {forbidden}")

current = current.rstrip() + "\n"
ast.parse(current)
PATH.write_text(current, encoding="utf-8")
print("D-W1 mature archive authority restored with four-state wrappers")
