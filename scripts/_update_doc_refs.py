#!/usr/bin/env python3
"""Bulk-update doc path references after modules/ split."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REPLACEMENTS = [
    ("docs/modules/13A-学工", "docs/学工中心/13A-学工"),
    ("docs/modules/13B-教务", "docs/教务中心/13B-教务"),
    ("docs/modules/02A-", "docs/学工中心/02A-"),
    ("docs/modules/13A-13B-", "docs/跨模块共享/13A-13B-"),
    ("docs/modules/00-", "docs/跨模块共享/00-"),
    ("docs/modules/_13-", "docs/跨模块共享/_13-"),
    ("docs/modules/系统三级", "docs/跨模块共享/系统三级"),
    ("docs/modules/README", "docs/跨模块共享/README"),
    ("docs/modules/", "docs/跨模块共享/"),
    ("../modules/13A-学工", "../学工中心/13A-学工"),
    ("../modules/13B-教务", "../教务中心/13B-教务"),
    ("../modules/02A-", "../学工中心/02A-"),
    ("../modules/13A-13B-", "../跨模块共享/13A-13B-"),
    ("../modules/00-", "../跨模块共享/00-"),
    ("../modules/_13-", "../跨模块共享/_13-"),
    ("../modules/系统三级", "../跨模块共享/系统三级"),
    ("../modules/README", "../跨模块共享/README"),
    ("../modules/", "../跨模块共享/"),
    ("modules/13A-学工", "学工中心/13A-学工"),
    ("modules/13B-教务", "教务中心/13B-教务"),
    ("modules/02A-", "学工中心/02A-"),
    ("modules/13A-13B-", "跨模块共享/13A-13B-"),
    ("modules/00-", "跨模块共享/00-"),
    ("`modules/13A-*`", "`学工中心/13A-*`"),
    ("`modules/13B-*`", "`教务中心/13B-*`"),
    ("`13A-*` `13B-*`", "`学工中心/13A-*` `教务中心/13B-*`"),
    ("modules/13A|13B|06", "学工中心/13A|教务中心/13B|岗位实习中心/06"),
    ("modules/13A|13B", "学工中心/13A|教务中心/13B"),
    ("服从 modules/00", "服从 跨模块共享/00"),
    ("以 modules 为准", "以各业务中心 README 为准"),
    ("`modules/`（见 [modules/README.md](./modules/README.md)）", "`跨模块共享/`（见 [跨模块共享/README.md](./跨模块共享/README.md)）"),
    ("| 模块设计 | `modules/`", "| 跨模块共享 | `跨模块共享/`"),
    ("docs/modules 下", "docs/各业务中心与跨模块共享 下"),
]

EXTENSIONS = {".md", ".js", ".vue", ".py"}


def patch_file(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="utf-16")
        except Exception:
            return False
    original = text
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = []
    scan_roots = [
        ROOT / "docs",
        ROOT / "CLAUDE.md",
        ROOT / "00-生产级全栈模块开发总提示词.md",
        ROOT / "AI执行状态.md",
        ROOT / "frontend" / "src" / "config",
    ]
    paths: list[Path] = []
    for base in scan_roots:
        if base.is_file():
            paths.append(base)
        elif base.is_dir():
            for path in base.rglob("*"):
                if path.is_file() and path.suffix.lower() in EXTENSIONS:
                    if "node_modules" in path.parts:
                        continue
                    paths.append(path)
    for path in paths:
        try:
            if patch_file(path):
                changed.append(path.relative_to(ROOT))
        except OSError:
            continue
    print(f"Updated {len(changed)} files")
    for p in changed:
        print(" ", p)


if __name__ == "__main__":
    main()
