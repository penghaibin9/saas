"""学生 PC 教务页面引用的 CSS 变量必须已定义或提供显式回退。"""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "student-portal/src"


def test_academic_pages_do_not_use_unresolved_css_variables():
    defined = set()
    for path in SRC.rglob("*"):
        if path.suffix not in {".vue", ".css", ".scss"}:
            continue
        source = path.read_text(encoding="utf-8")
        defined.update(re.findall(r"(--[A-Za-z0-9_-]+)\s*:", source))

    unresolved = []
    for path in (SRC / "views/academic").glob("Student*.vue"):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"var\((--[A-Za-z0-9_-]+)([^)]*)\)", source):
            variable, tail = match.group(1), match.group(2)
            has_fallback = "," in tail
            if variable not in defined and not has_fallback:
                unresolved.append(f"{path.name}:{variable}")

    assert not unresolved, "未定义且无回退的 CSS 变量：" + ", ".join(unresolved)
