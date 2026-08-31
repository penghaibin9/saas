#!/usr/bin/env python3
"""Fail-close Internship S6 source closure from git-tracked production sources.

V2 fixes two blind spots found by the first final-RC run:
1. uni-app internship pages live in pages.json subPackages, not only top-level pages;
2. internship authority also has source outside app/modules/internship (models, mobile,
   student-portal facades, help/config assets and teacher mini pages).

The script still fails closed: every in-scope internship source must be classified,
all APIRouter sources must be reachable from the production registry, local imports must
resolve, internship migrations/schedulers must be mapped, and all six gap arrays must be empty.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = (ROOT / os.getenv(
    "INTERNSHIP_S6_JSON_OUT",
    "artifacts/internship/final-audit/source-manifest/source-closure.json",
)).resolve()

tracked = {
    line.strip()
    for line in subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    if line.strip()
}

gaps: dict[str, list[str]] = {
    "unclassifiedFiles": [],
    "unmappedRoutes": [],
    "unmappedApiAliases": [],
    "unmappedSchedulers": [],
    "unmappedMigrations": [],
    "unmappedSharedDependencies": [],
}
manifest: dict[str, list[str]] = {
    "staffPc": [],
    "studentPc": [],
    "mini": [],
    "backend": [],
    "enterprisePortal": [],
    "testsAndWorkflows": [],
    "migrations": [],
    "schedulers": [],
    "sharedDependencies": [],
    "routes": [],
    "apiAliases": [],
    "miniPages": [],
}


def add(category: str, values) -> None:
    manifest[category].extend(str(v) for v in values if v)


def norm() -> None:
    for key in manifest:
        manifest[key] = sorted(set(manifest[key]))
    for key in gaps:
        gaps[key] = sorted(set(gaps[key]))


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def read_text(path: str | Path) -> str:
    try:
        return (ROOT / path).read_text(encoding="utf-8") if isinstance(path, str) else path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


# ---- Explicit source surfaces -------------------------------------------------
staff = {
    p for p in tracked
    if p.startswith("frontend/src/modules/internship/")
    or p.startswith("frontend/public/help/internship-")
    or p.startswith("frontend/public/help/images/internship/")
    or (p.startswith("frontend/public/official-site/") and "internship" in Path(p).name.lower())
    or p in {
        "frontend/src/config/navPlan.js",
        "frontend/src/config/help/internshipRoleGuidance.js",
        "frontend/src/config/help/internshipV3SelfServiceGuidance.js",
        "frontend/src/stores/internshipDashboard.js",
    }
}
add("staffPc", staff)

student = {
    p for p in tracked
    if p.startswith("student-portal/src/views/internship/")
    or p.startswith("student-portal/src/modules/internship")
    or (p.startswith("student-portal/src/services/") and "internship" in Path(p).name.lower())
    or p in {
        "student-portal/src/router/index.js",
        "student-portal/src/platform/moduleRegistry.js",
        "student-portal/src/platform/permissionGuard.js",
        "student-portal/src/services/fileSdk.js",
        "student-portal/src/views/home/HomeView.vue",
        "student-portal/src/views/messages/MessagesView.vue",
    }
}
add("studentPc", student)

mini = {
    p for p in tracked
    if p.startswith("miniapp/src/") and (
        "internship" in p.lower()
        or p.startswith("miniapp/src/pages/student/weekly-report/")
        or p.startswith("miniapp/src/pages/teacher/student-eval/")
        or p.startswith("miniapp/src/pages/teacher/enterprise-eval/")
        or p.startswith("miniapp/src/pages/teacher/insurance-verify/")
        or p.startswith("miniapp/src/pages/teacher/agreement-confirm/")
        or p.startswith("miniapp/src/pages/teacher/process-report-review/")
        or p.startswith("miniapp/src/pages/teacher/plan-task-review/")
        or p.startswith("miniapp/src/pages/teacher/workbench/")
        or p.startswith("miniapp/src/pages/teacher/todos/")
    )
}
for required in ("miniapp/src/pages.json", "miniapp/src/config/roles.config.js"):
    if required in tracked:
        mini.add(required)
    else:
        gaps["unclassifiedFiles"].append(f"MISSING_REQUIRED:{required}")
add("mini", mini)

backend = {
    p for p in tracked
    if p.startswith("backend/app/") and "internship" in p.lower() and p.endswith(".py")
}
for required in (
    "backend/app/api/v1/route_registration.py",
    "backend/app/models/internship.py",
):
    if required in tracked:
        backend.add(required)
    else:
        gaps["unclassifiedFiles"].append(f"MISSING_REQUIRED:{required}")
add("backend", backend)

enterprise = {p for p in tracked if p.startswith("enterprise-portal/")}
if not enterprise:
    gaps["unclassifiedFiles"].append("MISSING_REQUIRED:enterprise-portal/**")
add("enterprisePortal", enterprise)

test_assets = {
    p for p in tracked
    if "internship" in p.lower() and (
        p.startswith("e2e/")
        or p.startswith("backend/tests/")
        or p.startswith("backend/scripts/")
        or p.startswith("frontend/tests/")
        or p.startswith("frontend/scripts/")
        or p.startswith("frontend/src/config/__tests__/")
        or p.startswith("frontend/src/mocks/")
        or p.startswith("student-portal/tests/")
        or p.startswith("miniapp/tests/")
        or p.startswith("scripts/check/")
        or p.startswith(".github/workflows/")
    )
}
add("testsAndWorkflows", test_assets)

# ---- uni-app pages.json, including subPackages --------------------------------
pages_file = ROOT / "miniapp/src/pages.json"
try:
    pages_payload = json.loads(pages_file.read_text(encoding="utf-8"))
except Exception as exc:  # noqa: BLE001
    pages_payload = {}
    gaps["unmappedRoutes"].append(f"miniapp/src/pages.json parse-error: {exc}")

page_paths: list[str] = []
for item in pages_payload.get("pages", []) or []:
    if isinstance(item, dict) and item.get("path"):
        page_paths.append(str(item["path"]).strip("/"))
for package in pages_payload.get("subPackages", []) or []:
    if not isinstance(package, dict):
        continue
    root = str(package.get("root") or "").strip("/")
    for item in package.get("pages", []) or []:
        if not isinstance(item, dict) or not item.get("path"):
            continue
        child = str(item["path"]).strip("/")
        page_paths.append("/".join(x for x in (root, child) if x))

internship_pages = sorted(p for p in page_paths if "internship" in p.lower())
if not internship_pages:
    gaps["unmappedRoutes"].append("no internship pages discovered in miniapp/src/pages.json/subPackages")
for page in internship_pages:
    source = f"miniapp/src/{page}.vue"
    if source not in tracked:
        gaps["unmappedRoutes"].append(f"mini page source missing: {page} -> {source}")
    else:
        mini.add(source)
add("miniPages", internship_pages)
add("mini", mini)

# ---- Backend production router reachability ----------------------------------
router_dir = ROOT / "backend/app/modules/internship/routers"
registry_path = ROOT / "backend/app/api/v1/route_registration.py"
try:
    registry_tree = ast.parse(registry_path.read_text(encoding="utf-8"))
except SyntaxError as exc:
    registry_tree = ast.Module(body=[], type_ignores=[])
    gaps["unmappedRoutes"].append(f"route_registration.py parse-error: {exc}")

reachable: set[str] = set()
for node in ast.walk(registry_tree):
    if not isinstance(node, ast.ImportFrom) or not node.module:
        continue
    if node.module == "app.modules.internship.routers":
        reachable.update(alias.name for alias in node.names if alias.name.startswith("internship"))
    elif node.module.startswith("app.modules.internship.routers."):
        reachable.add(node.module.rsplit(".", 1)[-1])

# Follow router-to-router imports so aggregation remains supported.
queue = deque(sorted(reachable))
while queue:
    name = queue.popleft()
    path = router_dir / f"{name}.py"
    if not path.is_file():
        continue
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        gaps["unmappedRoutes"].append(f"{rel(path)} parse-error: {exc}")
        continue
    children: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "app.modules.internship.routers":
                children.update(alias.name for alias in node.names)
            elif node.module.startswith("app.modules.internship.routers."):
                children.add(node.module.rsplit(".", 1)[-1])
    for child in children:
        if child.startswith("internship") and child not in reachable:
            reachable.add(child)
            queue.append(child)

route_entries: list[str] = []
for path in sorted(router_dir.glob("*.py")):
    if path.name == "__init__.py":
        continue
    text_value = read_text(path)
    if "APIRouter(" in text_value and path.stem not in reachable:
        gaps["unmappedRoutes"].append(f"unreachable internship APIRouter: {rel(path)}")
    if path.stem in reachable:
        for method, route_path in re.findall(
            r"@\w+\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]*)['\"]",
            text_value,
        ):
            route_entries.append(f"{path.stem}:{method.upper()}:{route_path}")
add("routes", route_entries)
if not route_entries:
    gaps["unmappedApiAliases"].append("no internship API decorators discovered from reachable routers")

# The two guardian-delivery endpoints are the product defect that caused S6 v1 to fail.
for required in (
    "internship_guardian_consent_delivery:POST:/deliver",
    "internship_guardian_consent_delivery:POST:/{consent_id}/redeliver",
):
    if required not in route_entries:
        gaps["unmappedRoutes"].append(f"missing required guardian route: {required}")

# ---- UI API aliases ------------------------------------------------------------
api_aliases: set[str] = set()
ui_sources = sorted(staff | student | mini | enterprise)
for source in ui_sources:
    if not source.endswith((".js", ".ts", ".vue", ".mjs")):
        continue
    text_value = read_text(source)
    for value in re.findall(r"['\"]([^'\"]*internship[^'\"]*)['\"]", text_value, flags=re.I):
        if value.startswith("/") and not any(ch in value for ch in (" ", "\n")):
            api_aliases.add(value)
add("apiAliases", api_aliases)
if not api_aliases:
    gaps["unmappedApiAliases"].append("no internship UI API aliases discovered")

# ---- Migrations ---------------------------------------------------------------
migration_files: list[str] = []
for path in sorted(p for p in tracked if p.startswith("backend/alembic/versions/") and p.endswith(".py")):
    name_hit = "internship" in Path(path).name.lower()
    content_hit = "internship" in read_text(path).lower()
    if name_hit or content_hit:
        migration_files.append(path)
add("migrations", migration_files)
if not migration_files:
    gaps["unmappedMigrations"].append("no internship Alembic migrations discovered")

# ---- Scheduled jobs -----------------------------------------------------------
scheduler_path = "backend/scripts/run_scheduled_jobs.py"
scheduler_text = read_text(scheduler_path) if scheduler_path in tracked else ""
for job in ("internship_audit_outbox", "internship_overdue"):
    if job in scheduler_text:
        manifest["schedulers"].append(job)
    else:
        gaps["unmappedSchedulers"].append(f"missing scheduled internship job: {job}")

# ---- Local dependency closure -------------------------------------------------
def resolve_js(source: Path, spec: str, surface_root: Path) -> Path | None:
    if spec.startswith("@/"):
        base = surface_root / "src" / spec[2:]
    elif spec.startswith("."):
        base = source.parent / spec
    else:
        return None
    candidates = [
        base,
        Path(str(base) + ".js"), Path(str(base) + ".ts"), Path(str(base) + ".vue"),
        base.with_suffix(".js"), base.with_suffix(".ts"), base.with_suffix(".vue"),
        base / "index.js", base / "index.ts", base / "index.vue",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return Path("/__UNRESOLVED__") / spec

shared: set[str] = set()
for category, surface_root in (
    (staff, ROOT / "frontend"),
    (student, ROOT / "student-portal"),
    (mini, ROOT / "miniapp"),
    (enterprise, ROOT / "enterprise-portal"),
):
    queue = deque(ROOT / p for p in category if p.endswith((".js", ".ts", ".vue", ".mjs")))
    seen: set[Path] = set()
    while queue:
        source = queue.popleft().resolve()
        if source in seen or not source.is_file():
            continue
        seen.add(source)
        text_value = read_text(source)
        specs = set(re.findall(r"(?:from\s+|import\s*\()\s*['\"]([^'\"]+)['\"]", text_value))
        for spec in specs:
            target = resolve_js(source, spec, surface_root)
            if target is None:
                continue
            if "__UNRESOLVED__" in target.parts:
                gaps["unmappedSharedDependencies"].append(f"{rel(source)} -> {spec}")
                continue
            target_rel = rel(target)
            if target_rel not in tracked:
                gaps["unmappedSharedDependencies"].append(f"{rel(source)} -> {spec} -> {target_rel}")
                continue
            if target_rel not in category:
                shared.add(target_rel)
            if target.suffix in {".js", ".ts", ".vue", ".mjs"} and target not in seen:
                queue.append(target)


def resolve_app_module(module: str) -> Path | None:
    if not module.startswith("app."):
        return None
    base = ROOT / "backend" / Path(*module.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate.resolve()
    return Path("/__UNRESOLVED__") / module

for source_rel in sorted(backend):
    source = ROOT / source_rel
    if not source_rel.endswith(".py"):
        continue
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as exc:
        gaps["unmappedSharedDependencies"].append(f"{source_rel} parse-error: {exc}")
        continue
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
        for module in modules:
            target = resolve_app_module(module)
            if target is None:
                continue
            if "__UNRESOLVED__" in target.parts:
                gaps["unmappedSharedDependencies"].append(f"{source_rel} -> {module}")
                continue
            target_rel = rel(target)
            if target_rel not in tracked:
                gaps["unmappedSharedDependencies"].append(f"{source_rel} -> {module} -> {target_rel}")
            elif target_rel not in backend:
                shared.add(target_rel)
add("sharedDependencies", shared)

# ---- Unclassified source audit ------------------------------------------------
classified = set().union(
    staff, student, mini, backend, enterprise, test_assets, set(migration_files), shared
)
source_prefixes = (
    "backend/app/", "backend/tests/", "backend/scripts/", "backend/alembic/versions/",
    "e2e/", "frontend/src/", "frontend/public/", "frontend/scripts/", "frontend/tests/",
    "miniapp/src/", "miniapp/tests/", "student-portal/src/", "student-portal/tests/",
    "enterprise-portal/", ".github/workflows/", "scripts/check/",
)
in_scope_candidates = {
    p for p in tracked
    if p.startswith(source_prefixes) and (
        "internship" in p.lower() or p.startswith("enterprise-portal/")
    )
}
for path in sorted(in_scope_candidates - classified):
    gaps["unclassifiedFiles"].append(path)

norm()
payload = {
    "module": "INTERNSHIP",
    "productExactSha": os.getenv("E2E_PRODUCT_EXACT_SHA") or "",
    "runnerExactSha": os.getenv("E2E_EXPECTED_SHA") or "",
    "enterprisePortalScope": "IN_SCOPE",
    "manifest": manifest,
    **gaps,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

summary = {
    "productExactSha": payload["productExactSha"],
    "runnerExactSha": payload["runnerExactSha"],
    "staffPcFiles": len(manifest["staffPc"]),
    "studentPcFiles": len(manifest["studentPc"]),
    "miniFiles": len(manifest["mini"]),
    "miniPages": len(manifest["miniPages"]),
    "backendFiles": len(manifest["backend"]),
    "enterprisePortalFiles": len(manifest["enterprisePortal"]),
    "migrationFiles": len(manifest["migrations"]),
    "routeEntries": len(manifest["routes"]),
    "apiAliases": len(manifest["apiAliases"]),
    "schedulers": len(manifest["schedulers"]),
    "sharedDependencies": len(manifest["sharedDependencies"]),
    "gaps": {key: len(value) for key, value in gaps.items()},
}
print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
if any(gaps.values()):
    print(json.dumps(gaps, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(1)
print("[internship-s6] SOURCE_CLOSURE_VERIFIED")
