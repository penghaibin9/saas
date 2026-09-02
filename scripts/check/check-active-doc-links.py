from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "docs" / "00-项目入口与总控" / "document-catalog.json"
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
SCHEMES = ("http://", "https://", "mailto:", "tel:", "data:")


def target_path(source: Path, raw: str) -> Path | None:
    value = raw.strip().strip("<>").split("#", 1)[0].strip()
    if not value or value.lower().startswith(SCHEMES):
        return None
    # Markdown may append a quoted title after the target.
    value = re.split(r'\s+["\']', value, maxsplit=1)[0]
    value = unquote(value)
    if value.startswith("/"):
        return ROOT / value.lstrip("/")
    return (source.parent / value).resolve()


def main() -> int:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    issues: list[str] = []
    checked = 0
    for item in payload.get("documents", []):
        if item.get("status") != "active":
            continue
        relative = str(item.get("path") or "")
        if not relative.lower().endswith(".md"):
            continue
        source = ROOT / relative
        if not source.is_file():
            issues.append(f"missing active document: {relative}")
            continue
        checked += 1
        text = source.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK.finditer(text):
            destination = target_path(source, match.group(1))
            if destination is not None and not destination.exists():
                issues.append(f"{relative} -> {match.group(1)}")

    print(f"checked_active_markdown={checked} broken_links={len(issues)}")
    for issue in issues:
        print(f"BROKEN {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
