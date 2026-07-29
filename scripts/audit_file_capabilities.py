#!/usr/bin/env python3
"""Audit repository file capabilities against the frozen inventory."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
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
DIRECT_SIGNALS = (
    ("python-upload", re.compile(r"\bUploadFile\b|file_service\.store_upload\(")),
    ("python-generated-file", re.compile(r"file_service\.store_bytes\(")),
    ("python-download", re.compile(r"\bFileResponse\(|\bStreamingResponse\(|file_service\.resolve_download\(")),
    ("python-meta", re.compile(r"file_service\.get_file_meta\(")),
    ("client-upload", re.compile(r"\buni\.uploadFile\(|\bchooseFile\(|\buploadFile\(\s*['\"`]/")),
    ("client-download", re.compile(r"\buni\.downloadFile\(|\bdownloadFile\(\s*['\"`]/|\brealDownload\(\s*['\"`]/")),
    ("spreadsheet-read-write", re.compile(r"\bopenpyxl\b|\bload_workbook\(|\bWorkbook\(")),
    ("zip-archive", re.compile(r"\bzipfile\b|\bZipFile\(")),
    ("attachment-response", re.compile(r"Content-Disposition|content_disposition_type\s*=")),
    ("whole-file-read", re.compile(r"\.read_bytes\(\)")),
)
EXPLICIT_SEGMENT = r"(?:files?|uploads?|downloads?|preview|imports?|exports?|archives?|attachments?)"
QUOTED_PATH = re.compile(
    rf'''(?P<q>["'`])(?P<p>/(?:api/v1/)?[^"'`\s]*(?:^|/){EXPLICIT_SEGMENT}(?:/|\?|$)[^"'`\s]*)(?P=q)''',
    re.I,
)
FASTAPI_ROUTE = re.compile(r'''@[\w.]+?\.(?:get|post|put|patch|delete)\(\s*["'](?P<p>[^"']+)["']''', re.I)
EXPLICIT_ROUTE = re.compile(rf"(?:^|/){EXPLICIT_SEGMENT}(?:/|\?|$)", re.I)


@dataclass(frozen=True)
class Candidate:
    source: str
    line: int
    capability: str
    token: str
    snippet: str
    confidence: str = "high"

    @property
    def key(self) -> str:
        return f"{self.source}:{self.capability}:{self.token}"


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
    fields = ("route", "page", "api", "backendService", "notes", "module", "action", "fileCategory")
    return "\n".join(str(entry.get(name, "")) for name in fields).lower()


def validate_schema(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        return ["inventory.entries must be a non-empty list"]
    seen: set[tuple[str, ...]] = set()
    for index, entry in enumerate(entries, 1):
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
            if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES and not any(part in SKIP_PARTS for part in path.parts):
                yield path


def discover(paths: Iterable[Path] | None = None) -> list[Candidate]:
    found: dict[str, Candidate] = {}
    for path in paths or iter_source_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        source = path.relative_to(ROOT).as_posix()
        for line_no, line in enumerate(text.splitlines(), 1):
            snippet = line.strip()
            if not snippet or snippet.startswith(("#", "//", "/*", "*")):
                continue
            for capability, pattern in DIRECT_SIGNALS:
                match = pattern.search(line)
                if match:
                    item = Candidate(source, line_no, capability, match.group(0), snippet[:240])
                    found.setdefault(item.key, item)
            for match in QUOTED_PATH.finditer(line):
                item = Candidate(source, line_no, "http-file-path", match.group("p"), snippet[:240])
                found.setdefault(item.key, item)
            route = FASTAPI_ROUTE.search(line)
            if route and EXPLICIT_ROUTE.search(route.group("p")):
                item = Candidate(source, line_no, "fastapi-file-route", route.group("p"), snippet[:240])
                found.setdefault(item.key, item)
    return sorted(found.values(), key=lambda c: (c.source, c.capability, c.token, c.line))


def is_covered(candidate: Candidate, entries: list[dict[str, Any]]) -> bool:
    source = candidate.source.lower()
    token = candidate.token.lower()
    normalized = token.replace("{", "").replace("}", "")
    for entry in entries:
        if str(entry.get("status")) == "removed":
            continue
        ref = entry_ref_text(entry)
        ref_normalized = ref.replace("{", "").replace("}", "")
        if source in ref or (token and (token in ref or normalized in ref_normalized)):
            return True
    return False


def git_changed_files(base_ref: str) -> list[Path]:
    command = ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base_ref}...HEAD"]
    try:
        output = subprocess.check_output(command, cwd=ROOT, text=True, stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        detail = getattr(exc, "output", "") or str(exc)
        raise RuntimeError(f"cannot calculate changed files against {base_ref}: {detail.strip()}") from exc
    result: list[Path] = []
    for item in output.splitlines():
        rel = item.strip()
        path = ROOT / rel
        if rel and path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES and any(rel.startswith(f"{root}/") for root in SCAN_ROOTS):
            result.append(path)
    return result


def print_candidates(title: str, candidates: list[Candidate]) -> None:
    print(title)
    for item in candidates:
        print(f"  - {item.source}:{item.line} [{item.capability}] {item.token}")
        print(f"      {item.snippet}")


def write_json_report(path: Path, all_candidates: list[Candidate], missing: list[Candidate], entries_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "file-capability-scan/v2",
        "entriesCount": entries_count,
        "candidateCount": len(all_candidates),
        "missingCount": len(missing),
        "candidates": [asdict(item) for item in all_candidates],
        "missing": [asdict(item) for item in missing],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"JSON report written: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--check-schema", action="store_true")
    parser.add_argument("--strict-baseline", action="store_true")
    parser.add_argument("--check-new", action="store_true")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args()
    if not any((args.check_schema, args.strict_baseline, args.check_new, args.report, args.json_report)):
        parser.error("choose at least one mode")
    try:
        data = load_inventory(args.inventory)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    errors = validate_schema(data)
    if errors:
        print("Inventory schema errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 2
    entries = data["entries"]
    if args.check_schema:
        print(f"Inventory schema OK: {len(entries)} entries")
    if args.report or args.strict_baseline or args.json_report:
        candidates = discover()
        missing = [item for item in candidates if not is_covered(item, entries)]
        print(f"Baseline candidates: {len(candidates)}; registered: {len(candidates) - len(missing)}; missing: {len(missing)}")
        if args.json_report:
            write_json_report(args.json_report, candidates, missing, len(entries))
        if args.report and missing:
            print_candidates("Unregistered baseline candidates:", missing)
        if args.strict_baseline and missing:
            print_candidates("ERROR: unregistered baseline candidates:", missing)
            return 1
    if args.check_new:
        try:
            changed = git_changed_files(args.base_ref)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        candidates = discover(changed)
        missing = [item for item in candidates if not is_covered(item, entries)]
        print(f"Changed source files: {len(changed)}; capability candidates: {len(candidates)}; unregistered: {len(missing)}")
        if missing:
            print_candidates("ERROR: changed file capability is not registered:", missing)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
