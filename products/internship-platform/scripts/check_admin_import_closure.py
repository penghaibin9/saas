"""Standalone internship admin-web import closure gate."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "admin-web" / "src"
IMPORT_RE = re.compile(r"""(?:import\s+(?:[^'"]+?\s+from\s+)?|require\(\s*)['"]([^'"]+)['"]""")
EXTENSIONS = ("", ".js", ".mjs", ".ts", ".json", ".vue")
INDEXES = ("/index.js", "/index.mjs", "/index.ts", "/index.vue")


def resolve(source: Path, spec: str):
    if spec.startswith("@/"):
        base = SRC / spec[2:]
    elif spec.startswith("."):
        base = (source.parent / spec).resolve()
    else:
        return None
    raw = str(base)
    for candidate in [*(Path(raw + ext) for ext in EXTENSIONS), *(Path(raw + suffix) for suffix in INDEXES)]:
        if candidate.is_file():
            return candidate
    return base


def main():
    missing = []
    sources = sorted(
        p for p in SRC.rglob("*")
        if p.is_file() and p.suffix in {".js", ".mjs", ".ts", ".vue"}
    )
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for spec in IMPORT_RE.findall(text):
            target = resolve(source, spec)
            if target is not None and not target.exists():
                missing.append((source.relative_to(ROOT).as_posix(), spec, target.relative_to(ROOT).as_posix()))
    unique = []
    seen = set()
    for row in missing:
        if row not in seen:
            seen.add(row); unique.append(row)
    if unique:
        print("Standalone admin import closure is incomplete:")
        for source, spec, target in unique:
            print(f"- {source}: {spec} -> missing {target}")
        print(f"TOTAL_MISSING={len(unique)}")
        return 1
    print(f"Standalone admin import closure OK: {len(sources)} source files checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
