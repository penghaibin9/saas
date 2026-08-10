#!/usr/bin/env python3
"""Remove traceback/output payloads from pytest JUnit before uploading artifacts.

The audit needs testcase identity and pass/fail/error state, not exception text that
could accidentally contain provider credentials or other sensitive runtime data.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def sanitize(path: Path) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    for testcase in root.iter("testcase"):
        for tag in ("failure", "error"):
            for element in testcase.findall(tag):
                element.text = "[redacted: failure details intentionally omitted from artifact]"
                element.attrib.clear()
                element.set("message", "redacted")
        for tag in ("system-out", "system-err"):
            for element in testcase.findall(tag):
                element.text = "[redacted]"
                element.attrib.clear()
    tree.write(path, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("junit", type=Path)
    args = parser.parse_args()
    if not args.junit.is_file():
        print(f"JUnit report missing: {args.junit}", file=sys.stderr)
        return 2
    try:
        sanitize(args.junit)
    except (ET.ParseError, OSError) as exc:
        print(f"cannot sanitize JUnit report: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
