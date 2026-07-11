#!/usr/bin/env python3
"""Migrate 学工/教务 docs from modules/ to business center folders."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MODULES = DOCS / "modules"
XUEGONG = DOCS / "学工中心"
JIAOWU = DOCS / "教务中心"
SHARED = DOCS / "跨模块共享"


def git_mv(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "mv", str(src), str(dst)], cwd=ROOT, check=True)


def main() -> None:
    XUEGONG.mkdir(parents=True, exist_ok=True)
    JIAOWU.mkdir(parents=True, exist_ok=True)

    for f in sorted(MODULES.iterdir()):
        if not f.is_file() or f.suffix.lower() != ".md":
            continue
        name = f.name
        if name.startswith("13A-") or name.startswith("02A-"):
            git_mv(f, XUEGONG / name)
        elif name.startswith("13B-"):
            git_mv(f, JIAOWU / name)

    # Rename modules -> 跨模块共享 (remaining shared docs + README)
    if MODULES.exists() and not SHARED.exists():
        git_mv(MODULES, SHARED)
    elif MODULES.exists():
        for f in MODULES.iterdir():
            git_mv(f, SHARED / f.name)
        MODULES.rmdir()

    print("Migration done.")
    print(f"学工中心: {len(list(XUEGONG.glob('*.md')))} md")
    print(f"教务中心: {len(list(JIAOWU.glob('*.md')))} md")
    print(f"跨模块共享: {len(list(SHARED.glob('*.md')))} md")


if __name__ == "__main__":
    main()
