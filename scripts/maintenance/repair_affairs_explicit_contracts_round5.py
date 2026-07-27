from __future__ import annotations

import ast
import re
from pathlib import Path


TEST_FILES = (
    "test_affairs_club.py", "test_affairs_counselor_eval.py", "test_affairs_credit_appeal.py",
    "test_affairs_discipline.py", "test_affairs_discipline_appeal.py", "test_affairs_dorm.py",
    "test_affairs_eval_weight.py", "test_affairs_family_contact_mobile.py", "test_affairs_funding.py",
    "test_affairs_funding_appeal.py", "test_affairs_funding_ext.py", "test_affairs_league.py",
    "test_affairs_mental.py", "test_affairs_mobile.py", "test_affairs_optimistic_lock_round1.py",
    "test_affairs_org.py", "test_affairs_phase2_bigdata.py", "test_affairs_profile.py",
    "test_affairs_risk.py", "test_affairs_round2_bigdata.py", "test_affairs_talk.py",
    "test_affairs_todo_drilldown.py",
)


def repair(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(r"\bpost_versioned\((?!\s*client\s*,)", "post_versioned(client, ", text)
    if count:
        path.write_text(updated, encoding="utf-8")
    return count


def audit(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "post_versioned":
            continue
        if not node.args or not isinstance(node.args[0], ast.Name) or node.args[0].id != "client":
            bad.append(node.lineno)
    if bad:
        raise RuntimeError(f"{path}: post_versioned missing client at lines {bad}")


def main() -> None:
    root = Path("backend/tests")
    total = 0
    for name in TEST_FILES:
        path = root / name
        if path.exists():
            total += repair(path)
            audit(path)
    print(f"explicit helper client arguments repaired: {total}")


if __name__ == "__main__":
    main()
