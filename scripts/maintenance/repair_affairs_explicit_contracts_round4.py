from __future__ import annotations

import ast
import re
from pathlib import Path


TEST_FILES = (
    "test_affairs_club.py",
    "test_affairs_counselor_eval.py",
    "test_affairs_credit_appeal.py",
    "test_affairs_discipline.py",
    "test_affairs_discipline_appeal.py",
    "test_affairs_dorm.py",
    "test_affairs_eval_weight.py",
    "test_affairs_family_contact_mobile.py",
    "test_affairs_funding.py",
    "test_affairs_funding_appeal.py",
    "test_affairs_funding_ext.py",
    "test_affairs_league.py",
    "test_affairs_mental.py",
    "test_affairs_mobile.py",
    "test_affairs_optimistic_lock_round1.py",
    "test_affairs_org.py",
    "test_affairs_phase2_bigdata.py",
    "test_affairs_profile.py",
    "test_affairs_risk.py",
    "test_affairs_round2_bigdata.py",
    "test_affairs_talk.py",
    "test_affairs_todo_drilldown.py",
)

VERSION_PATHS = re.compile(
    r"/(?:"
    r"activities/.+/(?:publish|transition|confirm|unconfirm|archive)|"
    r"volunteer/records/.+/(?:confirm|reject)|"
    r"second-class/appeals/.+/review|"
    r"aid/applications/.+/(?:review|publicity-confirm|resubmit|adjust|adjust-review)|"
    r"aid/objections/.+/review|"
    r"funding/applications/.+/(?:review|publicity-confirm|disburse|appeal)|"
    r"funding/appeals/.+/review|"
    r"clubs/.+/(?:review|disband)|"
    r"counselor-eval/evals/.+/(?:publish|appeal|appeal-review)|"
    r"counselor-assessment/assessments/.+/score|"
    r"counselor-assessment/periods/.+/publish|"
    r"discipline/cases/.+/(?:submit|review|deliver|remove|remove-review)|"
    r"discipline/appeals/.+/review|"
    r"dorm/transfers/.+/review|"
    r"dorm/exceptions/.+/handle|"
    r"dorm/beds/.+/checkout|"
    r"risk/records/.+/(?:assign|process|follow|transfer|escalate|takeover|close|reopen)|"
    r"talks/.+/(?:record|follow-up)|"
    r"party-league/dev/.+/(?:advance|terminate)|"
    r"organizations/.+/(?:review|disband)|"
    r"organizations/positions/.+/dismiss|"
    r"work-study/posts/.+/(?:publish|close)|"
    r"work-study/records/.+/action|"
    r"student-loans/.+/(?:review|confirm)|"
    r"loans/.+/(?:review|confirm)|"
    r"fee-reductions/.+/(?:issue|review|confirm)|"
    r"mental/referrals/.+/(?:follow|escalate|close)"
    r")(?:['\"]|$)"
)

MISSING_VERSION_MARKERS = ("missing_version", "version_required", "requires_version")
IMPORT_LINE = (
    "from affairs_contract_test_support import "
    "ensure_owner_scope, ensure_workflow_assignees, post_versioned\n"
)


def offsets(text: str) -> list[int]:
    rows = [0]
    total = 0
    for line in text.splitlines(keepends=True):
        total += len(line)
        rows.append(total)
    return rows


def absolute(rows: list[int], line: int, col: int) -> int:
    return rows[line - 1] + col


def json_has_version(call: ast.Call) -> bool:
    for keyword in call.keywords:
        if keyword.arg != "json" or not isinstance(keyword.value, ast.Dict):
            continue
        for key in keyword.value.keys:
            if isinstance(key, ast.Constant) and key.value == "version":
                return True
    return False


def explicit_version_calls(text: str) -> tuple[str, int]:
    tree = ast.parse(text)
    rows = offsets(text)
    replacements: list[tuple[int, int, str]] = []
    for function in [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        lower_name = function.name.lower()
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "post"
                and isinstance(func.value, ast.Name)
                and func.value.id == "client"
                and node.args
            ):
                continue
            url_source = ast.get_source_segment(text, node.args[0]) or ast.unparse(node.args[0])
            if not VERSION_PATHS.search(url_source):
                continue
            if json_has_version(node):
                continue
            if any(marker in lower_name for marker in MISSING_VERSION_MARKERS):
                continue
            start = absolute(rows, func.lineno, func.col_offset)
            end = absolute(rows, node.args[0].lineno, node.args[0].col_offset)
            replacements.append((start, end, "post_versioned(client, "))

    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, len(replacements)


def repair_existing_helper_calls(text: str) -> tuple[str, int]:
    return re.subn(r"\bpost_versioned\((?!\s*client\s*,)", "post_versioned(client, ", text)


def add_import(text: str) -> str:
    if "from affairs_contract_test_support import" in text:
        return text
    anchor = "from __future__ import annotations\n"
    if anchor not in text:
        raise RuntimeError("future import anchor missing")
    return text.replace(anchor, anchor + "\n" + IMPORT_LINE, 1)


def patch_publicity(text: str) -> str:
    return text.replace('"publicityDays": 0', '"publicityDays": 1').replace(
        "'publicityDays': 0", "'publicityDays': 1"
    )


def inject_before_return(text: str, function_name: str, statement: str) -> str:
    pattern = re.compile(rf"(^def {re.escape(function_name)}\(.*?)(?=^def |\Z)", re.M | re.S)
    match = pattern.search(text)
    if not match:
        raise RuntimeError(f"function not found: {function_name}")
    block = match.group(1)
    if statement.strip() in block:
        return text
    return_match = list(re.finditer(r"^(\s*)return\s+", block, re.M))
    if not return_match:
        raise RuntimeError(f"return anchor missing: {function_name}")
    last = return_match[-1]
    indent = last.group(1)
    insert = indent + statement.strip() + "\n"
    position = match.start(1) + last.start()
    return text[:position] + insert + text[position:]


def patch_test_file(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    text = patch_publicity(text)
    text, repaired = repair_existing_helper_calls(text)
    text, created = explicit_version_calls(text)
    if repaired or created:
        text = add_import(text)
    path.write_text(text, encoding="utf-8")
    return repaired + created


def patch_assignees() -> None:
    patches = {
        "test_affairs_funding.py": ("_seed", 'ensure_workflow_assignees([ids["sa"], ids["sb"]])'),
        "test_affairs_discipline.py": ("_seed", 'ensure_workflow_assignees([ids["sa"], ids["sb"]])'),
        "test_affairs_funding_appeal.py": ("_seed_app", 'ensure_workflow_assignees(sid, nodes=("SCHOOL_REVIEW",))'),
        "test_affairs_discipline_appeal.py": ("_seed_case", 'ensure_workflow_assignees(sid, nodes=("SA_OFFICE_REVIEW",))'),
    }
    root = Path("backend/tests")
    for name, (function_name, statement) in patches.items():
        path = root / name
        text = add_import(path.read_text(encoding="utf-8"))
        text = inject_before_return(text, function_name, statement)
        path.write_text(text, encoding="utf-8")

    risk = root / "test_affairs_risk.py"
    text = add_import(risk.read_text(encoding="utf-8"))
    text = inject_before_return(text, "_seed", 'ensure_owner_scope("risk_owner01", ids["sa"])')
    text = inject_before_return(text, "_seed", 'ensure_owner_scope("risk_owner01", ids["sb"])')
    risk.write_text(text, encoding="utf-8")


def patch_known_inputs() -> None:
    root = Path("backend/tests")
    family = root / "test_affairs_family_contact_mobile.py"
    text = family.read_text(encoding="utf-8")
    text = text.replace(
        'json={"contactType": "PHONE", "reason": "测试越权"}',
        'json={"contactType": "PHONE", "reason": "测试越权", "result": "已完成沟通"}',
    )
    text = text.replace(
        'json={"contactType": "WECHAT", "reason": "作业完成情况"}',
        'json={"contactType": "WECHAT", "reason": "作业完成情况", "result": "家长已知晓"}',
    )
    family.write_text(text, encoding="utf-8")

    fixture = root / "test_affairs_leave_real_fixture_contract.py"
    text = fixture.read_text(encoding="utf-8")
    text = text.replace('"role_code=\\"STUDENT_AFFAIRS_ADMIN\\""', '"STUDENT_AFFAIRS_ADMIN"')
    fixture.write_text(text, encoding="utf-8")


def audit() -> None:
    root = Path("backend/tests")
    unresolved = []
    for name in TEST_FILES:
        path = root / name
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for function in [node for node in tree.body if isinstance(node, ast.FunctionDef)]:
            for node in ast.walk(function):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                func = node.func
                if isinstance(func, ast.Name) and func.id == "post_versioned":
                    if not isinstance(node.args[0], ast.Name) or node.args[0].id != "client":
                        unresolved.append(f"{name}:{function.name}:post_versioned missing client")
                    continue
                if not (
                    isinstance(func, ast.Attribute)
                    and func.attr == "post"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "client"
                ):
                    continue
                url_source = ast.get_source_segment(text, node.args[0]) or ast.unparse(node.args[0])
                if VERSION_PATHS.search(url_source) and not json_has_version(node):
                    if not any(marker in function.name.lower() for marker in MISSING_VERSION_MARKERS):
                        unresolved.append(f"{name}:{function.name}:{url_source}")
        if '"publicityDays": 0' in text or "'publicityDays': 0" in text:
            unresolved.append(f"{name}:publicityDays=0")
    if unresolved:
        raise RuntimeError("explicit test contracts remain unresolved:\n" + "\n".join(unresolved[:200]))


def main() -> None:
    root = Path("backend/tests")
    total = 0
    for name in TEST_FILES:
        path = root / name
        if path.exists():
            total += patch_test_file(path)
    patch_assignees()
    patch_known_inputs()
    audit()
    print(f"explicit student-affairs test contracts repaired: {total} calls")


if __name__ == "__main__":
    main()
