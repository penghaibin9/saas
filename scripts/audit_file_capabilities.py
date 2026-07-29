#!/usr/bin/env python3
"""Audit repository file capabilities against the frozen inventory."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "docs/architecture/file-capability-inventory.yaml"

REQUIRED_FIELDS = (
    "module", "client", "route", "page", "action", "fileCategory", "api",
    "backendService", "storageMode", "authMode", "dataScope", "versioned",
    "scanGated", "preview", "download", "import", "export", "archive",
    "status", "risk", "targetPhase",
)
VALID_CLIENTS = {"backend", "admin-pc", "student-pc", "teacher-miniapp", "student-miniapp", "shared"}
VALID_STATUS = {"active", "legacy", "duplicate", "needs-verification", "planned", "removed"}
VALID_RISK = {"P0", "P1", "P2", "P3"}
VALID_TARGET_PHASE = {str(i) for i in range(8)} | {"none"}
SCAN_ROOTS = ("backend/app", "frontend/src", "student-portal/src", "miniapp/src")
SOURCE_SUFFIXES = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".json"}
SKIP_PARTS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__", "coverage", "public"}

SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("python-upload", re.compile(r"\bUploadFile\b|file_service\.store_upload\(")),
    ("python-generated-file", re.compile(r"file_service\.store_bytes\(")),
    ("python-download", re.compile(r"\bFileResponse\(|\bStreamingResponse\(|file_service\.resolve_download\(")),
    ("python-meta", re.compile(r"file_service\.get_file_meta\(")),
    ("client-upload", re.compile(r"\b(?:uni\.)?uploadFile\(|\bchooseFile\(")),
    ("client-download", re.compile(r"\b(?:uni\.)?downloadFile\(")),
    ("xlsx", re.compile(r"\bopenpyxl\b|\bload_workbook\(|\bWorkbook\(")),
    ("zip-archive", re.compile(r"\bzipfile\b|\bZipFile\(")),
    ("attachment-header", re.compile(r"Content-Disposition|content_disposition_type\s*=")),
    ("whole-file-read", re.compile(r"\.read_bytes\(\)")),
)
HTTP_PATH = re.compile(
    r'''(?P<quote>["'`])(?P<path>/(?:api/v1/)?[^"'`\s]*(?:files?|upload|download|preview|import|export|archive|attachment|material|template)[^"'`\s]*)(?P=quote)''',
    re.IGNORECASE,
)
FASTAPI_ROUTE = re.compile(r'''@[\w.]+?\.(?:get|post|put|patch|delete)\(\s*["'](?P<path>[^"']+)["']''', re.IGNORECASE)


@dataclass(frozen=True)
class Candidate:
    source: str
    line: int
    capability: str
    token: str
    snippet: str

    @property
    def key(self) -> str:
        return f"{self.source}:{self.line}:{self.capability}:{self.token}"


def load_inventory(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required: pip install pyyaml")
    if not path.exists():
        raise RuntimeError(f"inventory not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("inventory root must be a mapping")
    return data


def entry_ref_text(entry: dict[str, Any]) -> str:
    return "\n".join(str(entry.get(name, "")) for name in ("route", "page", "api", "backendService", "notes")).lower()


def validate_schema(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        return ["inventory.entries must be a non-empty list"]
    seen: set[tuple[str, ...]] = set()
    for index, entry in enumerate(entries, start=1):
        where = f"entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{where} must be a mapping")
            continue
        missing = [field for field in REQUIRED_FIELDS if field not in entry]
        if missing:
            errors.append(f"{where} missing fields: {', '.join(missing)}")
            continue
        for field in REQUIRED_FIELDS:
            value = entry[field]
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"{where}.{field} must not be empty")
        if str(entry["client"]) not in VALID_CLIENTS:
            errors.append(f"{where}.client invalid: {entry['client']}")
        if str(entry["status"]) not in VALID_STATUS:
            errors.append(f"{where}.status invalid: {entry['status']}")
        if str(entry["risk"]) not in VALID_RISK:
            errors.append(f"{where}.risk invalid: {entry['risk']}")
        if str(entry["targetPhase"]) not in VALID_TARGET_PHASE:
            errors.append(f"{where}.targetPhase invalid: {entry['targetPhase']}")
        identity = tuple(str(entry.get(k, "")) for k in ("module", "client", "route", "action", "api"))
        if identity in seen:
            errors.append(f"{where} duplicates module/client/route/action/api identity")
        seen.add(identity)
    return errors


def iter_source_files() -> Iterable[Path]:
    for root_name in SCAN_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            yield path


def discover(paths: Iterable[Path] | None = None) -> list[Candidate]:
    candidates: list[Candidate] = []
    for path in paths or iter_source_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//", "/*", "*")):
                continue
            for capability, pattern in SIGNALS:
                if pattern.search(line):
                    candidates.append(Candidate(rel, line_no, capability, pattern.pattern, stripped[:240]))
            for match in HTTP_PATH.finditer(line):
                candidates.append(Candidate(rel, line_no, "http-file-path", match.group("path"), stripped[:240]))
            route_match = FASTAPI_ROUTE.search(line)
            if route_match:
                token = route_match.group("path")
                if re.search(r"file|upload|download|preview|import|export|archive|attachment|material|template", token, re.I):
                    candidates.append(Candidate(rel, line_no, "fastapi-file-route", token, stripped[:240]))
    unique = {candidate.key: candidate for candidate in candidates}
    return sorted(unique.values(), key=lambda c: (c.source, c.line, c.capability, c.token))


def is_covered(candidate: Candidate, entries: list[dict[str, Any]]) -> bool:
    source = candidate.source.lower()
    token = candidate.token.lower()
    for entry in entries:
        if str(entry.get("status")) == "removed":
            continue
        ref = entry_ref_text(entry)
        if source in ref:
            return True
        if candidate.capability in {"http-file-path", "fastapi-file-route"}:
            normalized = token.replace("{", "").replace("}", "")
            ref_normalized = ref.replace("{", "").replace("}", "")
            if token in ref or normalized in ref_normalized:
                return True
    return False


def git_changed_files(base_ref: str) -> list[Path]:
    command = ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base_ref}...HEAD"]
    try:
        output = subprocess.check_output(command, cwd=ROOT, text=True, stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        detail = getattr(exc, "output", "") or str(exc)
        raise RuntimeError(f"cannot calculate changed files against {base_ref}: {detail.strip()}") from exc
    paths: list[Path] = []
    for item in output.splitlines():
        rel = item.strip()
        path = ROOT / rel
        if rel and path.exists() and path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES and any(rel.startswith(f"{root}/") for root in SCAN_ROOTS):
            paths.append(path)
    return paths


def print_candidates(title: str, candidates: list[Candidate]) -> None:
    print(title)
    for item in candidates:
        print(f"  - {item.source}:{item.line} [{item.capability}] {item.token}")
        print(f"      {item.snippet}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--check-schema", action="store_true")
    parser.add_argument("--strict-baseline", action="store_true")
    parser.add_argument("--check-new", action="store_true")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if not any((args.check_schema, args.strict_baseline, args.check_new, args.report)):
        parser.error("choose at least one mode")
    try:
        data = load_inventory(args.inventory)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    schema_errors = validate_schema(data)
    if schema_errors:
        print("Inventory schema errors:", file=sys.stderr)
        for error in schema_errors:
            print(f"  - {error}", file=sys.stderr)
        return 2
    if args.check_schema:
        print(f"Inventory schema OK: {len(data['entries'])} entries")
    entries = data["entries"]
    if args.report or args.strict_baseline:
        all_candidates = discover()
        missing = [item for item in all_candidates if not is_covered(item, entries)]
        print(f"Baseline candidates: {len(all_candidates)}; registered: {len(all_candidates) - len(missing)}; missing: {len(missing)}")
        if args.report and missing:
            print_candidates("Unregistered baseline candidates:", missing)
        if args.strict_baseline and missing:
            print_candidates("ERROR: unregistered baseline candidates:", missing)
            return 1
    if args.check_new:
        try:
            changed_paths = git_changed_files(args.base_ref)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        changed_candidates = discover(changed_paths)
        missing = [item for item in changed_candidates if not is_covered(item, entries)]
        print(f"Changed source files: {len(changed_paths)}; capability candidates: {len(changed_candidates)}; unregistered: {len(missing)}")
        if missing:
            print_candidates("ERROR: changed file capability is not registered:", missing)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
