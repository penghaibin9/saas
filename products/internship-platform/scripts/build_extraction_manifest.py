#!/usr/bin/env python3
"""Build the source-to-Standalone extraction manifest from the frozen SaaS tree.

This is intentionally read-only. It does not copy files; W1/W2 use the manifest as the
machine-checkable source of truth for extraction and dependency closure.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "artifacts" / "extraction-manifest.json"

tracked = {
    line.strip()
    for line in subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    if line.strip()
}


def selected(prefix: str, *, contains: str | None = None) -> list[str]:
    rows = [p for p in tracked if p.startswith(prefix)]
    if contains:
        rows = [p for p in rows if contains.lower() in p.lower()]
    return sorted(rows)


manifest = {
    "schemaVersion": 1,
    "sourceBaseline": "adea054e2fd59cc0b83bbdb22f10ec98a8e2fd8c",
    "surfaces": {
        "backendDomain": selected("backend/app/modules/internship/"),
        "backendExternalInternshipSources": sorted(
            p for p in tracked
            if p.startswith("backend/app/")
            and "internship" in p.lower()
            and not p.startswith("backend/app/modules/internship/")
            and p.endswith(".py")
        ),
        "staffPc": selected("frontend/src/modules/internship/"),
        "studentMiniapp": selected("miniapp/src/pages/student-internship/"),
        "teacherMiniapp": selected("miniapp/src/pages/teacher-internship/"),
        "studentPc": sorted(
            p for p in tracked
            if p.startswith("student-portal/") and "internship" in p.lower()
        ),
        "enterprisePortal": selected("enterprise-portal/"),
        "tests": sorted(
            p for p in tracked
            if "internship" in p.lower()
            and (p.startswith("backend/tests/") or p.startswith("miniapp/tests/")
                 or p.startswith("student-portal/tests/") or p.startswith("frontend/tests/"))
        ),
        "workflows": sorted(
            p for p in tracked
            if p.startswith(".github/") and "internship" in p.lower()
        ),
        "historicalMigrations": sorted(
            p for p in tracked
            if p.startswith("backend/alembic/versions/")
            and p.endswith(".py")
            and ("internship" in Path(p).name.lower()
                 or "internship" in (ROOT / p).read_text(encoding="utf-8", errors="ignore").lower())
        ),
    },
    "policy": {
        "historicalMigrationsInstallableInStandalone": False,
        "standaloneMigrationBaseline": "0001_internship_standalone_baseline",
        "forbiddenBusinessDomains": [
            "academic_affairs", "student_affairs", "graduation",
            "orientation", "campus_service", "employment", "platform",
        ],
    },
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: len(v) for k, v in manifest["surfaces"].items()}, ensure_ascii=False, sort_keys=True))
print(f"[manifest] {OUT}")
