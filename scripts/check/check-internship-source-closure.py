#!/usr/bin/env python3
"""Generate and fail-close the Internship S6 source-manifest closure.

The checker is intentionally source-driven. It starts from git ls-files, follows backend
router/import closure, resolves frontend/student/mini local imports, validates mini pages,
discovers internship migrations and scheduled jobs, and emits the six empty-gap arrays
required by the final audit contract.
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/internship/final-audit/source-manifest/source-closure.json"

tracked = {
    line.strip()
    for line in subprocess.check_output(
        ["git", "ls-files"], cwd=ROOT, text=True
    ).splitlines()
    if line.strip()
}

gaps = {
    "unclassifiedFiles": [],
    "unmappedRoutes": [],
    "unmappedApiAliases": [],
    "unmappedSchedulers": [],
    "unmappedMigrations": [],
    "unmappedSharedDependencies": [],
}
manifest: dict[str, list[str] | dict] = {
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
}


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def existing_glob(pattern: str) -> list[str]:
    return sorted(p for p in tracked if Path(p).match(pattern))


def require_match(label: str, predicate) -> list[str]:
    matches = sorted(p for p in tracked if predicate(p))
    if not matches:
        gaps["unclassifiedFiles"].append(f"MISSING_REQUIRED:{label}")
    return matches


def add_many(category: str, paths) -> None:
    values = manifest[category]
    assert isinstance(values, list)
    values.extend(sorted(set(paths)))


# R1/S6 surface roots.
add_many(
    "staffPc",
    require_match(
        "frontend/src/modules/internship/**",
        lambda p: p.startswith("frontend/src/modules/internship/"),
    ),
)
for required in (
    "frontend/src/config/navPlan.js",
):
    if required in tracked:
        add_many("staffPc", [required])
    else:
        gaps["unclassifiedFiles"].append(f"MISSING_REQUIRED:{required}")
add_many(
    "staffPc",
    require_match(
        "frontend/src/router/**",
        lambda p: p.startswith("frontend/src/router/") and p.endswith((".js", ".ts")),
    ),
)

add_many(
    "studentPc",
    require_match(
        "student-portal internship views",
        lambda p: p.startswith("student-portal/src/views/internship/"),
    ),
)
add_many(
    "studentPc",
    require_match(
        "student-portal internship services",
        lambda p: p.startswith("student-portal/src/services/") and "internship" in Path(p).name.lower(),
    ),
)
add_many(
    "studentPc",
    require_match(
        "student-portal router",
        lambda p: p.startswith("student-portal/src/router/") and p.endswith((".js", ".ts")),
    ),
)
for required in (
    "student-portal/src/platform/moduleRegistry.js",
):
    if required in tracked:
        add_many("studentPc", [required])
    else:
        gaps["unclassifiedFiles"].append(f"MISSING_REQUIRED:{required}")
add_many(
    "studentPc",
    [
        p
        for p in tracked
        if p.startswith("student-portal/src/platform/permissionGuard")
        or p.startswith("student-portal/src/services/file")
        or p.startswith("student-portal/src/views/messages/")
        or p.startswith("student-portal/src/views/home/")
    ],
)

mini_prefixes = (
    "miniapp/src/pages/student/internship/",
    "miniapp/src/pages/student/weekly-report/",
    "miniapp/src/pages/teacher/student-eval/",
    "miniapp/src/pages/teacher/enterprise-eval/",
    "miniapp/src/pages/teacher/insurance-verify/",
    "miniapp/src/pages/teacher/agreement-confirm/",
    "miniapp/src/pages/teacher/process-report-review/",
    "miniapp/src/pages/teacher/plan-task-review/",
    "miniapp/src/pages/teacher/workbench/",
    "miniapp/src/pages/teacher/todos/",
)
add_many(
    "mini",
    require_match(
        "mini internship pages",
        lambda p: p.startswith(mini_prefixes),
    ),
)
for required in (
    "miniapp/src/config/roles.config.js",
    "miniapp/src/pages.json",
):
    if required in tracked:
        add_many("mini", [required])
    else:
        gaps["unclassifiedFiles"].append(f"MISSING_REQUIRED:{required}")
add_many(
    "mini",
    [
        p
        for p in tracked
        if p.startswith("miniapp/src/services/")
        and ("internship" in Path(p).name.lower() or "teacherapi" in Path(p).name.lower())
    ],
)
add_many(
    "mini",
    [p for p in tracked if p.startswith("miniapp/src/stores/internshipContext")],
)

add_many(
    "backend",
    require_match(
        "backend/app/modules/internship/**",
        lambda p: p.startswith("backend/app/modules/internship/") and p.endswith(".py"),
    ),
)
for required in (
    "backend/app/models/internship.py",
    "backend/app/api/v1/route_registration.py",
):
    if required in tracked:
        add_many("backend", [required])
    else:
        gaps["unclassifiedFiles"].append(f"MISSING_REQUIRED:{required}")

add_many(
    "enterprisePortal",
    require_match(
        "enterprise-portal/**",
        lambda p: p.startswith("enterprise-portal/"),
    ),
)

add_many(
    "testsAndWorkflows",
    [
        p
        for p in tracked
        if (
            (p.startswith("e2e/") and "internship" in p.lower())
            or (p.startswith("frontend/tests/") and "internship" in p.lower())
            or (p.startswith("student-portal/tests/") and "internship" in p.lower())
            or (p.startswith("miniapp/") and "/test" in p.lower() and "internship" in p.lower())
            or (p.startswith("backend/tests/") and "internship" in p.lower())
            or (p.startswith("backend/scripts/") and "internship" in p.lower())
            or (p.startswith("scripts/check/") and "internship" in p.lower())
            or (p.startswith(".github/workflows/internship-") and p.endswith((".yml", ".yaml")))
        )
    ],
)


def resolve_js_import(source: Path, spec: str, surface_root: Path) -> Path | None:
    if spec.startswith("@/"):
        candidate = surface_root / "src" / spec[2:]
    elif spec.startswith("."):
        candidate = source.parent / spec
    else:
        return None
    candidates = [
        candidate,
        Path(str(candidate) + ".js"),
        Path(str(candidate) + ".ts"),
        Path(str(candidate) + ".vue"),
        candidate.with_suffix(".js"),
        candidate.with_suffix(".ts"),
        candidate.with_suffix(".vue"),
        candidate / "index.js",
        candidate / "index.ts",
        candidate / "index.vue",
    ]
    for item in candidates:
        if item.is_file():
            return item.resolve()
    return Path("__UNRESOLVED__") / spec


def js_local_imports(source: Path, surface_root: Path):
    try:
        text_value = source.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    specs = set(re.findall(r'''(?:from\s+|import\s*\()\s*['"]([^'"]+)['"]''', text_value))
    output = []
    for spec in specs:
        resolved = resolve_js_import(source, spec, surface_root)
        if resolved is not None:
            output.append((spec, resolved))
    return output


# Resolve local shared imports for the three UI surfaces.
surface_specs = (
    ("staffPc", ROOT / "frontend"),
    ("studentPc", ROOT / "student-portal"),
    ("mini", ROOT / "miniapp"),
)
shared = set()
for category, surface_root in surface_specs:
    queue = deque(
        ROOT / p
        for p in manifest[category]
        if isinstance(p, str) and p.endswith((".js", ".ts", ".vue"))
    )
    seen = set()
    while queue:
        source = queue.popleft().resolve()
        if source in seen or not source.is_file():
            continue
        seen.add(source)
        for spec, target in js_local_imports(source, surface_root):
            if "__UNRESOLVED__" in target.parts:
                gaps["unmappedSharedDependencies"].append(f"{rel(source)} -> {spec}")
                continue
            target_rel = rel(target)
            if target_rel not in tracked:
                gaps["unmappedSharedDependencies"].append(f"{rel(source)} -> {spec} -> {target_rel}")
                continue
            shared.add(target_rel)
            if target.suffix in {".js", ".ts", ".vue"} and target not in seen:
                queue.append(target)

# Backend import graph: every internal app.* dependency must resolve to tracked source.
backend_sources = [
    ROOT / p
    for p in manifest["backend"]
    if isinstance(p, str) and p.endswith(".py")
]
backend_shared = set()
router_graph: dict[str, set[str]] = defaultdict(set)
router_dir = ROOT / "backend/app/modules/internship/routers"


def resolve_app_module(module: str) -> Path | None:
    if not module.startswith("app."):
        return None
    base = ROOT / "backend" / Path(*module.split("."))
    candidates = [base.with_suffix(".py"), base / "__init__.py"]
    for item in candidates:
        if item.is_file():
            return item.resolve()
    return Path("__UNRESOLVED__") / module


for source in backend_sources:
    try:
        tree = ast.parse(source.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as exc:
        gaps["unmappedSharedDependencies"].append(f"{rel(source)} parse-error: {exc}")
        continue
    source_module = source.stem
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
            if node.module == "app.modules.internship.routers":
                for alias in node.names:
                    router_graph[source_module].add(alias.name)
            elif node.module.startswith("app.modules.internship.routers."):
                router_graph[source_module].add(node.module.rsplit(".", 1)[-1])
        for module in modules:
            target = resolve_app_module(module)
            if target is None:
                continue
            if "__UNRESOLVED__" in target.parts:
                gaps["unmappedSharedDependencies"].append(f"{rel(source)} -> {module}")
                continue
            target_rel = rel(target)
            if target_rel not in tracked:
                gaps["unmappedSharedDependencies"].append(f"{rel(source)} -> {module} -> {target_rel}")
            elif not target_rel.startswith("backend/app/modules/internship/"):
                backend_shared.add(target_rel)

shared.update(backend_shared)
add_many("sharedDependencies", shared)

# Backend router reachability from the production route registry, including transitive router imports.
registry = ROOT / "backend/app/api/v1/route_registration.py"
registry_text = registry.read_text(encoding="utf-8")
registered_router_names = set()
for block in re.findall(
    r"from\s+app\.modules\.internship\.routers\s+import\s*\((.*?)\)",
    registry_text,
    flags=re.S,
):
    registered_router_names.update(re.findall(r"\b(internship[a-zA-Z0-9_]*)\b", block))
registered_router_names.update(
    re.findall(
        r"from\s+app\.modules\.internship\.routers\s+import\s+(internship[a-zA-Z0-9_]*)",
        registry_text,
    )
)

reachable = set(registered_router_names)
queue = deque(registered_router_names)
while queue:
    name = queue.popleft()
    path = router_dir / f"{name}.py"
    if not path.is_file():
        gaps["unmappedRoutes"].append(f"registered router source missing: {name}")
        continue
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        gaps["unmappedRoutes"].append(f"{rel(path)} parse-error: {exc}")
        continue
    discovered = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "app.modules.internship.routers":
                discovered.update(alias.name for alias in node.names)
            elif node.module.startswith("app.modules.internship.routers."):
                discovered.add(node.module.rsplit(".", 1)[-1])
    for child in discovered:
        if child not in reachable:
            reachable.add(child)
            queue.append(child)

router_files = sorted(router_dir.glob("*.py"))
for path in router_files:
    if path.name == "__init__.py":
        continue
    text_value = path.read_text(encoding="utf-8")
    if "APIRouter(" in text_value and path.stem not in reachable:
        gaps["unmappedRoutes"].append(f"unreachable internship APIRouter: {rel(path)}")

# Explicit shared internship endpoints registered outside the domain router package.
for module_path in (
    "backend/app/student_portal/internship_router.py",
    "backend/app/api/v1/mobile_internship_context.py",
    "backend/app/api/v1/mobile_internship_leave_context.py",
    "backend/app/api/v1/mobile_internship_student.py",
):
    if module_path not in tracked:
        gaps["unmappedRoutes"].append(f"missing shared internship router: {module_path}")
    else:
        shared.add(module_path)
add_many("sharedDependencies", shared)

# Decorated route strings in reachable sources are all source-mapped API entries.
route_entries = []
for name in sorted(reachable):
    path = router_dir / f"{name}.py"
    if not path.is_file():
        continue
    text_value = path.read_text(encoding="utf-8")
    for method, route_path in re.findall(
        r"@\w+\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]*)['\"]",
        text_value,
    ):
        route_entries.append(f"{name}:{method.upper()}:{route_path}")
add_many("routes", route_entries)
if not route_entries:
    gaps["unmappedApiAliases"].append("no internship API decorators discovered from reachable routers")

# Mini pages.json must map documented native/H5 internship pages to real source files.
pages_json = ROOT / "miniapp/src/pages.json"
try:
    pages_payload = json.loads(pages_json.read_text(encoding="utf-8"))
except Exception as exc:
    gaps["unmappedRoutes"].append(f"miniapp/src/pages.json parse-error: {exc}")
    pages_payload = {}

mini_page_paths = []
for item in pages_payload.get("pages", []):
    page_path = item.get("path") if isinstance(item, dict) else None
    if not page_path:
        continue
    if (
        "internship" in page_path
        or "weekly-report" in page_path
        or any(
            token in page_path
            for token in (
                "student-eval",
                "enterprise-eval",
                "insurance-verify",
                "agreement-confirm",
                "process-report-review",
                "plan-task-review",
            )
        )
    ):
        mini_page_paths.append(page_path)
        source = ROOT / "miniapp/src" / f"{page_path}.vue"
        if not source.is_file():
            gaps["unmappedRoutes"].append(f"mini page source missing: {page_path}")
if not mini_page_paths:
    gaps["unmappedRoutes"].append("no internship pages discovered in miniapp/src/pages.json")

# Migrations: every tracked revision that mentions internship schema is explicitly inventoried.
migration_paths = []
for path_str in sorted(
    p
    for p in tracked
    if p.startswith("backend/alembic/versions/") and p.endswith(".py")
):
    path = ROOT / path_str
    text_value = path.read_text(encoding="utf-8")
    if "internship" not in text_value.lower() and "t_internship_" not in text_value:
        continue
    migration_paths.append(path_str)
    if not re.search(r"^\s*revision\s*=", text_value, flags=re.M):
        gaps["unmappedMigrations"].append(f"{path_str}: missing revision")
    if not re.search(r"^\s*down_revision\s*=", text_value, flags=re.M):
        gaps["unmappedMigrations"].append(f"{path_str}: missing down_revision")
if not migration_paths:
    gaps["unmappedMigrations"].append("no internship migrations discovered")
add_many("migrations", migration_paths)

# Scheduler closure: every internship job_* function in the production scheduler must be invoked.
scheduler_path = ROOT / "backend/scripts/run_scheduled_jobs.py"
if not scheduler_path.is_file():
    gaps["unmappedSchedulers"].append("backend/scripts/run_scheduled_jobs.py missing")
else:
    scheduler_text = scheduler_path.read_text(encoding="utf-8")
    scheduler_tree = ast.parse(scheduler_text)
    jobs = sorted(
        node.name
        for node in scheduler_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("job_internship")
    )
    for job in jobs:
        if scheduler_text.count(f"{job}(") < 2:
            gaps["unmappedSchedulers"].append(f"{job}: defined but no invocation found")
    literals = sorted(set(re.findall(r"['\"](internship_[a-zA-Z0-9_]+)['\"]", scheduler_text)))
    scheduler_items = jobs + literals
    if not scheduler_items:
        gaps["unmappedSchedulers"].append("no internship scheduler jobs discovered")
    add_many("schedulers", scheduler_items)

# Any internship-named production/test/workflow source outside the final declared categories is a closure gap.
production_roots = (
    "frontend/",
    "student-portal/",
    "miniapp/",
    "backend/app/",
    "backend/tests/",
    "backend/scripts/",
    "backend/alembic/",
    "e2e/",
    "enterprise-portal/",
    "scripts/check/",
    ".github/workflows/",
)
classified = {
    p
    for key, values in manifest.items()
    if isinstance(values, list)
    for p in values
}
for path in sorted(tracked):
    if path.startswith(production_roots) and "internship" in path.lower() and path not in classified:
        gaps["unclassifiedFiles"].append(path)

# Deduplicate all outputs deterministically.
for key, values in manifest.items():
    if isinstance(values, list):
        manifest[key] = sorted(set(values))
for key, values in gaps.items():
    gaps[key] = sorted(set(values))

payload = {
    "module": "INTERNSHIP",
    "productExactSha": os.getenv("E2E_PRODUCT_EXACT_SHA") or "",
    "runnerExactSha": os.getenv("E2E_EXPECTED_SHA") or subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip(),
    "enterprisePortalScope": "IN_SCOPE",
    "manifest": manifest,
    **gaps,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

print(json.dumps({
    "productExactSha": payload["productExactSha"],
    "runnerExactSha": payload["runnerExactSha"],
    "staffPcFiles": len(manifest["staffPc"]),
    "studentPcFiles": len(manifest["studentPc"]),
    "miniFiles": len(manifest["mini"]),
    "backendFiles": len(manifest["backend"]),
    "enterprisePortalFiles": len(manifest["enterprisePortal"]),
    "migrationFiles": len(manifest["migrations"]),
    "sharedDependencies": len(manifest["sharedDependencies"]),
    "routeEntries": len(manifest["routes"]),
    "schedulers": len(manifest["schedulers"]),
    "gaps": {key: len(value) for key, value in gaps.items()},
}, ensure_ascii=False, sort_keys=True))

failed = {key: value for key, value in gaps.items() if value}
if failed:
    raise SystemExit(json.dumps(failed, ensure_ascii=False, indent=2, sort_keys=True))
print("INTERNSHIP_S6_SOURCE_CLOSURE_PASS")
