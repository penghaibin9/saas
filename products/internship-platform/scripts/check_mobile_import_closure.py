"""Fail when standalone internship mobile sources import files outside their extracted closure."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mobile" / "src"

IMPORT_RE = re.compile(
    r"""(?:import\s+(?:[^'"]+?\s+from\s+)?|require\(\s*)['"]([^'"]+)['"]"""
)
EXTENSIONS = ("", ".js", ".mjs", ".ts", ".json", ".vue")
INDEXES = ("/index.js", "/index.mjs", "/index.ts", "/index.vue")


def resolve(source: Path, spec: str) -> Path | None:
    if spec.startswith("@/"):
        base = SRC / spec[2:]
    elif spec.startswith("."):
        base = (source.parent / spec).resolve()
    else:
        return None

    raw = str(base)
    candidates = [Path(raw + ext) for ext in EXTENSIONS]
    candidates.extend(Path(raw + suffix) for suffix in INDEXES)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return base


def main() -> int:
    missing: list[tuple[str, str, str]] = []
    files = sorted(
        p for p in SRC.rglob("*")
        if p.suffix in {".js", ".mjs", ".ts", ".vue"} and p.is_file()
    )
    for source in files:
        text = source.read_text(encoding="utf-8")
        for spec in IMPORT_RE.findall(text):
            target = resolve(source, spec)
            if target is not None and not target.exists():
                missing.append((
                    source.relative_to(ROOT).as_posix(),
                    spec,
                    target.relative_to(ROOT).as_posix() if ROOT in target.parents else str(target),
                ))

    if missing:
        print("Standalone mobile import closure is incomplete:")
        for source, spec, target in missing:
            print(f"- {source}: {spec} -> missing {target}")
        print(f"TOTAL_MISSING={len(missing)}")
        return 1

    print(f"Standalone mobile import closure OK: {len(files)} source files checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
