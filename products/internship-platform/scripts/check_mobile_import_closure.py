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

    forbidden_routes = {
        "/pages/student/home/index": "parent student home",
        "/pages/teacher/workbench/index": "parent teacher workbench",
    }
    route_escapes: list[tuple[str, str, str]] = []
    for source in files:
        text = source.read_text(encoding="utf-8")
        for route, label in forbidden_routes.items():
            if route in text:
                route_escapes.append((source.relative_to(ROOT).as_posix(), route, label))

    if missing:
        print("Standalone mobile import closure is incomplete:")
        for source, spec, target in missing:
            print(f"- {source}: {spec} -> missing {target}")
        print(f"TOTAL_MISSING={len(missing)}")
        return 1

    if route_escapes:
        print("Standalone mobile navigation escapes back into the parent product:")
        for source, route, label in route_escapes:
            print(f"- {source}: {route} ({label})")
        print(f"TOTAL_ROUTE_ESCAPES={len(route_escapes)}")
        return 1

    print(
        f"Standalone mobile import/navigation closure OK: "
        f"{len(files)} source files checked; no parent home routes found."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
