#!/usr/bin/env python3
"""Audit repository file capabilities against the frozen inventory.

The original inventory remains the frozen baseline. Later construction phases register their
new capabilities in ``docs/architecture/file-capability-inventory.d/*.yaml``. Schema, strict
baseline and changed-file checks always validate the effective merged registry; no source or
capability is ignored.
"""
from __future__ import annotations

import argparse
import collections
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
SUPPLEMENT_DIR = ROOT / "docs/architecture/file-capability-inventory.d"
REQUIRED_FIELDS = (
    "module", "client", "route", "page", "action", "fileCategory", "api",
    "backendService", "storageMode", "authMode", "dataScope", "versioned",
    "scanGated", "preview", "download", "import", "export", "archive",
    "status", "risk", "targetPhase",
)
VALID_CLIENTS = {"backend", "admin-pc", "student-pc", "teacher-miniapp", "student-miniapp", "shared"}
VALID_STATUS = {"active", "legacy", "duplicate", "needs-verification", "planned", "removed"}
VALID_RISK = {"P0", "P1", "P2", "P3"}
# The frozen document defines stages 0-10. Supplements from later construction stages must be
# schema-valid without weakening the original baseline or using free-form phase labels.
VALID_TARGET_PHASE = {str(i) for i in range(11)} | {"none"}
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


def _read_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required: pip install pyyaml")
    if not path.exists():
        raise RuntimeError(f"inventory not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"inventory root must be a mapping: {path}")
    return data


def load_inventory(path: Path) -> dict[str, Any]:
    """Load only the requested inventory document (kept for sync/backward compatibility)."""
    return _read_yaml(path)


def load_supplement_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not SUPPLEMENT_DIR.exists():
        return entries
    for path in sorted(SUPPLEMENT_DIR.glob("*.yaml")):
        data = _read_yaml(path)
        value = data.get("entries")
        if not isinstance(value, list):
            raise RuntimeError(f"supplement entries must be a list: {path}")
        for entry in value:
            if not isinstance(entry, dict):
                raise RuntimeError(f"supplement entry must be a mapping: {path}")
            entries.append(entry)
    return entries


def load_effective_inventory(path: Path) -> dict[str, Any]:
    data = load_inventory(path)
    if path.resolve() == DEFAULT_INVENTORY.resolve():
        data = dict(data)
        data["entries"] = list(data.get("entries") or []) + load_supplement_entries()
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
        identity = tuple(str(entry.get(key, "")) for key in ("module", "client", "route", "action", "api"))
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
            if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES and not any(
                part in SKIP_PARTS for part in path.parts
            ):
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
            route = FASTAPI_ROUTE.search(line)
            if route and EXPLICIT_ROUTE.search(route.group("p")):
                item = Candidate(source, line_no, "fastapi-file-route", route.group("p"), snippet[:240])
                found.setdefault(item.key, item)
            elif not route:
                for match in QUOTED_PATH.finditer(line):
                    item = Candidate(source, line_no, "http-file-path", match.group("p"), snippet[:240])
                    found.setdefault(item.key, item)
    return sorted(found.values(), key=lambda item: (item.source, item.capability, item.token, item.line))


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


def infer_client(source: str) -> str:
    if source.startswith("backend/"):
        return "backend"
    if source.startswith("frontend/"):
        return "admin-pc"
    if source.startswith("student-portal/"):
        return "student-pc"
    if source.startswith("miniapp/"):
        name = Path(source).name.lower()
        if "/teacher/" in source or "teacher" in name:
            return "teacher-miniapp"
        if "/student/" in source or "student" in name:
            return "student-miniapp"
        return "shared"
    return "shared"


def infer_module(source: str) -> str:
    lower = source.lower()
    pairs = (
        ("academic_affairs", "academic-affairs"), ("academic-affairs", "academic-affairs"),
        ("graduation", "graduation"), ("internship", "internship"),
        ("student_affairs", "student-affairs"), ("studentaffairs", "student-affairs"),
        ("orientation", "orientation"), ("employment", "employment"),
        ("migration", "system-migration"), ("identity_import", "identity-import"),
        ("identity-import", "identity-import"), ("system", "system-management"),
        ("file", "file-center"), ("xlsx", "shared-xlsx"), ("excel", "shared-xlsx"),
        ("archive", "archive"), ("mobile", "mobile-shared"),
    )
    for needle, module in pairs:
        if needle in lower:
            return module
    return "shared-platform"


def generated_entry(module: str, client: str, items: list[Candidate]) -> dict[str, Any]:
    sources = sorted({item.source for item in items})
    text = " ".join(f"{item.token} {item.snippet}".lower() for item in items)
    capabilities = {item.capability for item in items}
    preview = "preview" in text or "python-meta" in capabilities
    download = any(word in text for word in ("download", "export", "content-disposition")) or bool(
        capabilities & {"python-download", "client-download", "attachment-response"}
    )
    import_flag = "import" in text or "spreadsheet-read-write" in capabilities
    export_flag = "export" in text or bool(capabilities & {"spreadsheet-read-write", "python-generated-file"})
    archive = "archive" in text or "zip-archive" in capabilities
    upload = "upload" in text or bool(capabilities & {"python-upload", "client-upload"})
    actions = [name for name, enabled in (
        ("upload", upload), ("preview", preview), ("download", download),
        ("import", import_flag), ("export", export_flag), ("archive", archive),
    ) if enabled]
    primary = items[0]
    return {
        "module": module,
        "client": client,
        "route": primary.token if primary.capability in {"fastapi-file-route", "http-file-path"} else primary.source,
        "page": ", ".join(sources),
        "action": "+".join(actions) or primary.capability,
        "fileCategory": "AUTO_DISCOVERED",
        "api": ", ".join(sorted({item.token for item in items if "route" in item.capability or "path" in item.capability})) or "not-explicit",
        "backendService": ", ".join(source for source in sources if source.startswith("backend/")) or "client-only",
        "storageMode": "unknown-requires-review",
        "authMode": "unknown-requires-review",
        "dataScope": "unknown-requires-review",
        "versioned": False,
        "scanGated": False,
        "preview": preview,
        "download": download,
        "import": import_flag,
        "export": export_flag,
        "archive": archive,
        "status": "needs-verification",
        "risk": "P1",
        "targetPhase": "0",
        "notes": "auto-discovered signals: " + "; ".join(
            f"{item.source}:{item.line} [{item.capability}] {item.snippet}" for item in items[:8]
        ),
    }


def relative_sources(candidates: Iterable[Candidate]) -> set[str]:
    return {item.source for item in candidates}


def inventory_entries(path: Path) -> list[dict[str, Any]]:
    return list(load_effective_inventory(path).get("entries") or [])


def git_changed_files(base_ref: str) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git diff failed")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def validate_changed_capabilities(base_ref: str, entries: list[dict[str, Any]]) -> list[str]:
    changed = [ROOT / item for item in git_changed_files(base_ref)]
    sources = [path for path in changed if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES]
    candidates = discover(sources)
    return [
        f"unregistered changed capability: {item.source}:{item.line} [{item.capability}] {item.token}"
        for item in candidates
        if not is_covered(item, entries)
    ]


def summarize(candidates: list[Candidate], entries: list[dict[str, Any]]) -> dict[str, Any]:
    uncovered = [item for item in candidates if not is_covered(item, entries)]
    by_module = collections.Counter(infer_module(item.source) for item in candidates)
    return {
        "candidates": len(candidates),
        "registered": len(candidates) - len(uncovered),
        "uncovered": len(uncovered),
        "byModule": dict(sorted(by_module.items())),
        "uncoveredItems": [asdict(item) for item in uncovered],
    }


def write_synced_inventory(path: Path) -> int:
    data = load_inventory(path)
    entries = list(data.get("entries") or [])
    candidates = discover()
    uncovered = [item for item in candidates if not is_covered(item, entries)]
    grouped: dict[tuple[str, str], list[Candidate]] = collections.defaultdict(list)
    for item in uncovered:
        grouped[(infer_module(item.source), infer_client(item.source))].append(item)
    for (module, client), items in sorted(grouped.items()):
        entries.append(generated_entry(module, client, items))
    data["entries"] = entries
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"sync complete: added {len(grouped)} grouped entries")
    return 0


def print_schema(path: Path) -> int:
    errors = validate_schema(load_effective_inventory(path))
    if errors:
        print("inventory schema invalid:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("inventory schema valid")
    return 0


def print_report(path: Path, json_path: Path | None) -> int:
    entries = inventory_entries(path)
    candidates = discover()
    report = summarize(candidates, entries)
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def print_strict(path: Path) -> int:
    entries = inventory_entries(path)
    uncovered = [item for item in discover() if not is_covered(item, entries)]
    if uncovered:
        print("unregistered file capabilities:", file=sys.stderr)
        for item in uncovered:
            print(f"- {item.source}:{item.line} [{item.capability}] {item.token}", file=sys.stderr)
        return 1
    print("all file capabilities registered")
    return 0


def print_changed(path: Path, base_ref: str) -> int:
    errors = validate_changed_capabilities(base_ref, inventory_entries(path))
    if errors:
        print("changed file capabilities must be registered:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("all changed file capabilities registered")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--check-schema", action="store_true")
    parser.add_argument("--strict-baseline", action="store_true")
    parser.add_argument("--check-new", action="store_true")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--json-report", type=Path)
    parser.add_argument("--sync-inventory", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.check_schema:
        return print_schema(args.inventory)
    if args.sync_inventory:
        return write_synced_inventory(args.inventory)
    if args.strict_baseline:
        return print_strict(args.inventory)
    if args.check_new:
        return print_changed(args.inventory, args.base_ref)
    if args.report or args.json_report:
        return print_report(args.inventory, args.json_report)
    return print_report(args.inventory, args.json_report)


if __name__ == "__main__":
    raise SystemExit(main())
