#!/usr/bin/env python3
"""Extract secret-safe pytest failure fingerprints from a raw JUnit report.

Only testcase identity, failure/error kind, exception class names, and repository
Python file/line/function locations are retained. Exception messages, SQL,
parameters, stdout/stderr, and traceback source lines are intentionally omitted.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


_EXCEPTION_RE = re.compile(
    r"(?<![\w.])([A-Za-z_][\w.]*?(?:Error|Exception|AppException|HTTPException))(?=[:\s\"']|$)"
)
_FRAME_RE = re.compile(
    r"(?m)^(?:\s*>?\s*)?(?P<path>(?:app|tests|scripts)/[^:\n]+\.py|conftest\.py)"
    r":(?P<line>\d+)(?::\s+in\s+(?P<func>[A-Za-z_][A-Za-z0-9_<>]*))?"
)


def _normalize_nodeid(value: str) -> str:
    return value.strip().replace("\\", "/").removeprefix("backend/")


def _nodeid(testcase: ET.Element) -> str:
    name = str(testcase.get("name") or "").strip()
    classname = str(testcase.get("classname") or "").strip()
    if not name:
        return "<unknown-testcase>"
    if ".py" in name and ("/" in name or "\\" in name):
        return _normalize_nodeid(name)
    parts = [part for part in classname.split(".") if part]
    module_index = next((i for i, part in enumerate(parts) if part.startswith("test_")), None)
    if module_index is None:
        return name
    path = "/".join(parts[: module_index + 1]) + ".py"
    scopes = parts[module_index + 1 :]
    return _normalize_nodeid("::".join([path, *scopes, name]))


def _exception_classes(element: ET.Element) -> list[str]:
    sources = [str(element.get("type") or ""), str(element.get("message") or ""), element.text or ""]
    found: list[str] = []
    for source in sources:
        for match in _EXCEPTION_RE.finditer(source):
            value = match.group(1)
            if value not in found:
                found.append(value)
    return found[:4]


def _frames(element: ET.Element) -> list[str]:
    text = element.text or ""
    found: list[str] = []
    for match in _FRAME_RE.finditer(text):
        path = match.group("path").replace("\\", "/")
        line = match.group("line")
        func = match.group("func")
        value = f"{path}:{line}" + (f" in {func}" if func else "")
        if value not in found:
            found.append(value)
    return found[-8:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("junit", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.junit.is_file():
        print(f"JUnit report missing: {args.junit}", file=sys.stderr)
        return 2
    try:
        root = ET.parse(args.junit).getroot()
    except (ET.ParseError, OSError) as exc:
        print(f"cannot read JUnit report: {exc}", file=sys.stderr)
        return 2

    rows: list[tuple[str, str, list[str], list[str]]] = []
    for testcase in root.iter("testcase"):
        element = testcase.find("error")
        kind = "error"
        if element is None:
            element = testcase.find("failure")
            kind = "failure"
        if element is None:
            continue
        rows.append((_nodeid(testcase), kind, _exception_classes(element), _frames(element)))

    lines = ["# Secret-safe pytest diagnostics", "", f"Cases: **{len(rows)}**", ""]
    for nodeid, kind, classes, frames in rows:
        lines.append(f"## `{nodeid}`")
        lines.append(f"- kind: `{kind}`")
        lines.append("- exception classes: " + (", ".join(f"`{v}`" for v in classes) if classes else "`unknown`"))
        if frames:
            lines.append("- repository frames:")
            lines.extend(f"  - `{frame}`" for frame in frames)
        else:
            lines.append("- repository frames: none detected")
        lines.append("")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {len(rows)} secret-safe diagnostics to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
