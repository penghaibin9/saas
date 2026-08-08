#!/usr/bin/env python3
"""Validate help-center governance files and runtime references without third-party packages."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELP_DOCS = ROOT / "docs" / "help"
CATALOG = HELP_DOCS / "catalog.yml"
ASSET_INVENTORY = HELP_DOCS / "assets" / "inventory.yml"
RUNTIME_HELP = ROOT / "frontend" / "src" / "config"

ERRORS: list[str] = []


def error(message: str) -> None:
    ERRORS.append(message)


def relative_links(markdown: str) -> list[str]:
    links = re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", markdown)
    return [link.split("#", 1)[0].strip() for link in links]


def validate_markdown_links() -> int:
    checked = 0
    for path in HELP_DOCS.rglob("*.md"):
        if "templates" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for target in relative_links(text):
            if not target or target.startswith(("http://", "https://", "mailto:", "/", "#")):
                continue
            checked += 1
            resolved = (path.parent / target).resolve()
            if ROOT not in resolved.parents and resolved != ROOT:
                error(f"{path.relative_to(ROOT)}: link escapes repository: {target}")
            elif not resolved.exists():
                error(f"{path.relative_to(ROOT)}: missing relative link target: {target}")
    return checked


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        error(f"{path.relative_to(ROOT)}: unclosed frontmatter")
        return {}
    data: dict[str, str] = {}
    for line in text[4:end].splitlines():
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if match:
            data[match.group(1)] = match.group(2).strip()
    return data


def validate_runbook_frontmatter() -> int:
    roots = [HELP_DOCS / "getting-started", HELP_DOCS / "modules", HELP_DOCS / "mobile"]
    required = {"id", "title", "roles", "platforms", "module", "keywords", "owner", "status", "reviewedAt"}
    ids: list[str] = []
    checked = 0
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            checked += 1
            data = parse_frontmatter(path)
            missing = sorted(required - data.keys())
            if missing:
                error(f"{path.relative_to(ROOT)}: missing frontmatter keys: {', '.join(missing)}")
            if data.get("id"):
                ids.append(data["id"])
            if data.get("status") not in {"draft", "reviewed", "published", "stale", "archived"}:
                error(f"{path.relative_to(ROOT)}: invalid status {data.get('status')!r}")
    for item_id, count in Counter(ids).items():
        if count > 1:
            error(f"duplicate governance runbook id: {item_id}")
    return checked


def extract_yaml_paths(path: Path) -> list[str]:
    pattern = r"^\s*(?:path|architectureDecision|view|model|auditReport|coverageMatrix|styleGuide|definitionOfDone|reviewChecklist|assetInventory|visualAssets):\s*([^#\n]+)"
    return re.findall(pattern, path.read_text(encoding="utf-8"), re.M)


def validate_catalog_paths() -> int:
    if not CATALOG.exists():
        error("docs/help/catalog.yml is missing")
        return 0
    paths = [value.strip().strip("'\"") for value in extract_yaml_paths(CATALOG)]
    for value in paths:
        if not (ROOT / value).exists():
            error(f"catalog.yml references missing path: {value}")
    return len(paths)


def validate_asset_inventory() -> int:
    if not ASSET_INVENTORY.exists():
        error("docs/help/assets/inventory.yml is missing")
        return 0
    text = ASSET_INVENTORY.read_text(encoding="utf-8")
    root_match = re.search(r"^root:\s*(.+)$", text, re.M)
    if not root_match:
        error("asset inventory has no root")
        return 0
    root = ROOT / root_match.group(1).strip().strip("'\"")
    assets_block = text.split("assets:", 1)[1] if "assets:" in text else ""
    names = re.findall(r"^\s{2}-\s+([^#\n]+)", assets_block, re.M)
    if not names:
        error("asset inventory contains no assets")
    inventoried = sorted(name.strip().strip("'\"") for name in names)
    for name in inventoried:
        asset = root / name
        if not asset.exists():
            error(f"asset inventory references missing file: {asset.relative_to(ROOT)}")
    existing = sorted(path.name for path in root.glob("*.html")) if root.exists() else []
    missing_from_inventory = sorted(set(existing) - set(inventoried))
    stale_inventory = sorted(set(inventoried) - set(existing))
    if missing_from_inventory:
        error(f"HTML help assets missing from inventory: {', '.join(missing_from_inventory)}")
    if stale_inventory:
        error(f"inventory contains nonexistent HTML assets: {', '.join(stale_inventory)}")
    return len(names)


def runtime_js_files() -> list[Path]:
    return [RUNTIME_HELP / "helpContent.js", *sorted((RUNTIME_HELP / "help").glob("*.js"))]


def validate_runtime_ids_and_embeds() -> tuple[int, int]:
    id_locations: dict[str, list[str]] = {}
    embeds: list[tuple[Path, str]] = []
    for path in runtime_js_files():
        if not path.exists():
            error(f"missing runtime help source: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for item_id in re.findall(r"\bid:\s*['\"]([^'\"]+)['\"]", text):
            id_locations.setdefault(item_id, []).append(str(path.relative_to(ROOT)))
        embeds.extend((path, value) for value in re.findall(r"\bembed:\s*['\"]([^'\"]+)['\"]", text))

    for item_id, paths in id_locations.items():
        if len(paths) > 1:
            error(f"duplicate runtime help id {item_id}: {', '.join(paths)}")

    for source, embed in embeds:
        if not embed.startswith("/help/"):
            error(f"{source.relative_to(ROOT)}: embed must use /help/: {embed}")
            continue
        target = ROOT / "frontend" / "public" / embed.lstrip("/")
        if not target.exists():
            error(f"{source.relative_to(ROOT)}: missing embedded asset: {embed}")
    return len(id_locations), len(embeds)


def main() -> int:
    if not HELP_DOCS.exists():
        error("docs/help directory is missing")
    links = validate_markdown_links()
    runbooks = validate_runbook_frontmatter()
    catalog_paths = validate_catalog_paths()
    assets = validate_asset_inventory()
    runtime_ids, embeds = validate_runtime_ids_and_embeds()

    print(
        "help-center validation: "
        f"{links} links, {runbooks} runbooks, {catalog_paths} catalog paths, "
        f"{assets} assets, {runtime_ids} runtime ids, {embeds} embeds"
    )
    for message in ERRORS:
        print(f"ERROR: {message}", file=sys.stderr)
    if ERRORS:
        print(f"FAILED with {len(ERRORS)} error(s)", file=sys.stderr)
        return 1
    print("OK: help-center governance and runtime references are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
