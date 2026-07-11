#!/usr/bin/env python3

"""Validate markdown links in 03-业务模块设计/学工中心/教务中心 docs."""

from __future__ import annotations



import re

from pathlib import Path



ROOT = Path(__file__).resolve().parents[1]

DOCS = ROOT / "docs"



LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

BACKTICK_PATH_RE = re.compile(r"`(docs/[^`]+)`")



ISSUES: list[str] = []





def resolve_link(source: Path, target: str) -> Path | None:

    target = target.split("#")[0].strip()

    if not target or target.startswith("http"):

        return None

    if target.startswith("docs/"):

        p = ROOT / target

    elif target.startswith("/"):

        return None

    else:

        p = (source.parent / target).resolve()

    return p





def check_file(path: Path) -> None:

    try:

        text = path.read_text(encoding="utf-8")

    except Exception as e:

        ISSUES.append(f"READ_FAIL {path}: {e}")

        return



    rel = path.relative_to(ROOT).as_posix()



    if "docs/modules" in text or "../modules/" in text:

        for i, line in enumerate(text.splitlines(), 1):

            if "docs/modules" in line or "../modules/" in line:

                ISSUES.append(f"OLD_MODULES {rel}:{i}: {line.strip()[:120]}")



    for m in LINK_RE.finditer(text):

        raw = m.group(2)

        if raw.startswith("http"):

            continue

        resolved = resolve_link(path, raw)

        if resolved and not resolved.exists():

            ISSUES.append(f"BROKEN_LINK {rel} -> {raw} (missing)")



    for m in BACKTICK_PATH_RE.finditer(text):

        p = ROOT / m.group(1)

        if not p.exists():

            ISSUES.append(f"BROKEN_PATH {rel} -> {m.group(1)}")





def main() -> None:

    for folder in ("学工中心", "教务中心"):

        d = DOCS / folder

        for f in sorted(d.glob("*.md")):

            check_file(f)

    print(f"Issues: {len(ISSUES)}")

    for item in ISSUES:

        print(item)





if __name__ == "__main__":

    main()

