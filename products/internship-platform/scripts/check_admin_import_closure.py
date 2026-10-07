"""Standalone internship admin-web import/dependency closure gate."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "admin-web" / "src"
IMPORT_RE = re.compile(r"""(?:import\s+(?:[^'"]+?\s+from\s+)?|require\(\s*)['"]([^'"]+)['"]""")
EXTENSIONS = ("", ".js", ".mjs", ".ts", ".json", ".vue")
INDEXES = ("/index.js", "/index.mjs", "/index.ts", "/index.vue")

# Standalone 可以复用成熟公共运行底座，但不能重新依赖其他 SaaS 业务域，
# 也不能为过闭包门禁把 mock 数据层搬回来。
FORBIDDEN_PREFIXES = (
    "@/modules/academicAffairs",
    "@/modules/studentAffairs",
    "@/modules/graduation",
    "@/modules/orientation",
    "@/modules/employment",
    "@/modules/platform",
    "@/services/mock",
)
FORBIDDEN_EXACT = ("../services/mock", "./services/mock")


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
    forbidden = []
    sources = sorted(
        p for p in SRC.rglob("*")
        if p.is_file() and p.suffix in {".js", ".mjs", ".ts", ".vue"}
    )
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for spec in IMPORT_RE.findall(text):
            rel = source.relative_to(ROOT).as_posix()
            if spec in FORBIDDEN_EXACT or any(spec.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
                forbidden.append((rel, spec))
                continue
            target = resolve(source, spec)
            if target is not None and not target.exists():
                missing.append((rel, spec, target.relative_to(ROOT).as_posix()))

    def unique(rows):
        out, seen = [], set()
        for row in rows:
            if row not in seen:
                seen.add(row)
                out.append(row)
        return out

    missing = unique(missing)
    forbidden = unique(forbidden)

    if forbidden:
        print("Standalone admin contains forbidden cross-domain/mock imports:")
        for source, spec in forbidden:
            print(f"- {source}: {spec}")
        print(f"TOTAL_FORBIDDEN={len(forbidden)}")

    if missing:
        print("Standalone admin import closure is incomplete:")
        for source, spec, target in missing:
            print(f"- {source}: {spec} -> missing {target}")
        print(f"TOTAL_MISSING={len(missing)}")

    if forbidden or missing:
        return 1

    print(f"Standalone admin import closure OK: {len(sources)} source files checked; no forbidden business/mock imports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
