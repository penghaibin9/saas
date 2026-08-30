#!/usr/bin/env python3
"""Generate the Internship V8 W0 live-truth audit artifacts.

This script is deliberately read-only with respect to product state.  It uses
only the Python standard library, Node.js, Git and the public GitHub API so W0
can run before application dependencies are installed.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "internship-v8" / "w0"
AUTHORITY = "岗位实习中心4+1端惊艳体验AI无人值守安全重构施工总控-V8.0-20260830.md"


def run(*args: str) -> str:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def write_json(name: str, payload: Any) -> None:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_existing_json(name: str) -> dict[str, Any]:
    """Read an existing artifact so later runtime evidence survives a static refresh."""
    path = OUT / name
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_menu() -> dict[str, Any]:
    script = """
const m = await import('./frontend/src/config/navPlan.js');
const group = m.NAV_PLAN.find((item) => item.key === 'internship');
process.stdout.write(JSON.stringify(group));
"""
    return json.loads(run("node", "--input-type=module", "-e", script))


def load_routes() -> dict[str, list[dict[str, Any]]]:
    script = r"""
import fs from 'node:fs';
import vm from 'node:vm';

function componentPath(value) {
  if (typeof value !== 'function') return null;
  const match = value.toString().match(/import\(['\"]([^'\"]+)['\"]\)/);
  return match ? match[1] : null;
}

function joinPath(base, value) {
  if (!value) return base || '/';
  if (value.startsWith('/')) return value;
  const prefix = !base || base === '/' ? '' : base.replace(/\/$/, '');
  return `${prefix}/${value}`.replace(/\/+/g, '/');
}

function flatten(definition) {
  const result = [];
  function visit(route, base = '') {
    const fullPath = joinPath(base, route.path || '');
    result.push({
      path: fullPath,
      localPath: route.path || '',
      name: route.name || null,
      component: componentPath(route.component),
      redirect: typeof route.redirect === 'function' ? route.redirect.toString() : (route.redirect || null),
      meta: route.meta || {},
    });
    for (const child of route.children || []) visit(child, fullPath);
  }
  for (const route of Array.isArray(definition) ? definition : [definition]) visit(route);
  return result;
}

function evaluateStaff() {
  let source = fs.readFileSync('frontend/src/modules/internship/routes.js', 'utf8');
  source = source.replace(/^import .*$/gm, '');
  source = source.replace(/export default internshipRoutes\s*;?/, 'globalThis.__routes = internshipRoutes;');
  const context = {};
  const proxy = `const INTERNSHIP_MODULE = new Proxy({}, {get: (_, key) => String(key)});\n` +
    `const INTERNSHIP_PAGE = new Proxy({}, {get: (_, key) => String(key)});\n`;
  vm.runInNewContext(proxy + source, context, { filename: 'internship-routes-audit.js' });
  return flatten(context.__routes);
}

function evaluateSimple(file) {
  let source = fs.readFileSync(file, 'utf8');
  source = source.replace(/^import .*$/gm, '');
  const routerIndex = source.indexOf('const router');
  if (routerIndex >= 0) source = source.slice(0, routerIndex);
  source += '\nglobalThis.__routes = routes;';
  const context = {};
  vm.runInNewContext(source, context, { filename: file });
  return flatten(context.__routes);
}

process.stdout.write(JSON.stringify({
  staffPc: evaluateStaff(),
  studentPc: evaluateSimple('student-portal/src/router/index.js').filter((item) => item.path.includes('internship')),
  enterprisePortal: evaluateSimple('enterprise-portal/src/router/index.js'),
}));
"""
    return json.loads(run("node", "--input-type=module", "-e", script))


def eval_static(node: ast.AST, env: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, (ast.List, ast.Tuple)):
        values: list[Any] = []
        for item in node.elts:
            if isinstance(item, ast.Starred):
                values.extend(eval_static(item.value, env))
            else:
                values.append(eval_static(item, env))
        return values if isinstance(node, ast.List) else tuple(values)
    if isinstance(node, ast.Set):
        values: set[Any] = set()
        for item in node.elts:
            if isinstance(item, ast.Starred):
                values.update(eval_static(item.value, env))
            else:
                values.add(eval_static(item, env))
        return values
    if isinstance(node, ast.Dict):
        return {eval_static(k, env): eval_static(v, env) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "set" and not node.args:
        return set()
    raise ValueError(type(node).__name__)


def load_role_permissions() -> dict[str, set[str]]:
    source = (ROOT / "backend/app/core/permissions.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    env: dict[str, Any] = {}
    for node in tree.body:
        name = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name, value = node.target.id, node.value
        if name and value is not None:
            try:
                env[name] = eval_static(value, env)
            except (KeyError, ValueError):
                continue
    roles = {str(k): set(v) for k, v in (env.get("ROLE_PERMISSIONS") or {}).items()}

    catalog = json.loads((ROOT / "shared/contracts/permission-catalog.json").read_text(encoding="utf-8"))
    school_admin = {
        str(item.get("permissionCode") or "")
        for item in catalog.get("entries") or []
        if str(item.get("lifecycle") or "").upper() == "ACTIVE"
        and str(item.get("plane") or "").upper() == "TENANT"
        and bool(item.get("tenantAssignable"))
    }
    for extension_name in (
        "permission-catalog-b8-concrete.json",
        "permission-catalog-b8-compatibility.json",
    ):
        extension = json.loads((ROOT / "shared/contracts" / extension_name).read_text(encoding="utf-8"))
        school_admin.update(str(code) for code in extension.get("entries") or [])
    roles["SCHOOL_ADMIN"] = {
        code for code in school_admin
        if code and not code.startswith("platform.") and not code.startswith("enterprise.")
    }
    return roles


def permission_matches(patterns: set[str], code: str | None) -> bool:
    if not code:
        return True
    if "*" in patterns or code in patterns:
        return True
    return any(pattern.endswith(".*") and code.startswith(pattern[:-1]) for pattern in patterns)


def flatten_menu(menu: dict[str, Any]) -> list[dict[str, Any]]:
    leaves: list[dict[str, Any]] = []
    for workspace in menu.get("children") or []:
        for index, leaf in enumerate(workspace.get("children") or []):
            leaves.append({
                "workspaceKey": workspace.get("key"),
                "workspaceLabel": workspace.get("label"),
                "leafIndex": index,
                **leaf,
            })
    return leaves


def dynamic_route_matches(route_pattern: str, target: str) -> bool:
    escaped = re.escape(route_pattern)
    escaped = re.sub(r"\\:[A-Za-z_][A-Za-z0-9_]*", r"[^/]+", escaped)
    return bool(re.fullmatch(escaped, target))


def extract_backend_endpoints() -> list[dict[str, Any]]:
    endpoints: list[dict[str, Any]] = []
    for path in sorted((ROOT / "backend/app/modules/internship/routers").glob("*.py")):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        constants: dict[str, str] = {}
        router_names: dict[str, str] = {}
        import_aliases: dict[str, str] = {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    import_aliases[alias.asname or alias.name] = f"{module}.{alias.name}".strip(".")
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    constants[name] = node.value.value
                if isinstance(node.value, ast.Call):
                    fn = node.value.func
                    fn_name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else "")
                    if fn_name == "APIRouter":
                        prefix = ""
                        for keyword in node.value.keywords:
                            if keyword.arg == "prefix" and isinstance(keyword.value, ast.Constant):
                                prefix = str(keyword.value.value)
                        router_names[name] = prefix

        def constant_string(node: ast.AST) -> str | None:
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return node.value
            if isinstance(node, ast.Name):
                return constants.get(node.id)
            return None

        for fn in (node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            for decorator in fn.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                owner = decorator.func.value
                if not isinstance(owner, ast.Name) or owner.id not in router_names:
                    continue
                method = decorator.func.attr.upper()
                if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                    continue
                local_path = constant_string(decorator.args[0]) if decorator.args else ""
                if local_path is None:
                    local_path = "<dynamic>"
                prefix = router_names[owner.id]
                full_path = f"/api/v1{prefix}{local_path}".replace("//", "/")
                permissions: set[str] = set()
                service_calls: set[str] = set()
                for child in ast.walk(fn):
                    if not isinstance(child, ast.Call):
                        continue
                    called = child.func
                    called_name = called.id if isinstance(called, ast.Name) else (called.attr if isinstance(called, ast.Attribute) else "")
                    if called_name in {"require_permission", "require_any_permission", "enforce_permission"}:
                        for arg in child.args:
                            value = constant_string(arg)
                            if value:
                                permissions.add(value)
                    if isinstance(called, ast.Attribute) and isinstance(called.value, ast.Name):
                        alias = called.value.id
                        imported = import_aliases.get(alias, "")
                        if alias.endswith(("svc", "service")) or "internship" in imported:
                            service_calls.add(f"{imported or alias}.{called.attr}")
                endpoints.append({
                    "method": method,
                    "path": full_path,
                    "routerFile": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "function": fn.name,
                    "permissions": sorted(permissions),
                    "serviceCalls": sorted(service_calls),
                    "line": fn.lineno,
                })
    return endpoints


def candidate_endpoints(endpoints: list[dict[str, Any]], patterns: list[str]) -> list[dict[str, Any]]:
    compiled = [re.compile(pattern, re.I) for pattern in patterns]
    ranked: list[tuple[int, dict[str, Any]]] = []
    for endpoint in endpoints:
        haystack = " ".join([
            endpoint["path"], endpoint["function"], endpoint["routerFile"],
            *endpoint["serviceCalls"],
        ])
        score = sum(1 for pattern in compiled if pattern.search(haystack))
        if score:
            ranked.append((score, endpoint))
    ranked.sort(key=lambda item: (-item[0], item[1]["path"], item[1]["method"]))
    return [item for _, item in ranked[:6]]


def source_metrics(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    return {
        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
        "lineCount": source.count("\n") + 1,
        "tabPaneTagCount": len(re.findall(r"<(?:el-)?tab-pane\b", source)),
        "buttonTagCount": len(re.findall(r"<(?:el-)?button\b|<button\b", source)),
        "toastHintCount": len(re.findall(r"(?:ElMessage|toast|showToast)", source)),
        "loadingHintCount": len(re.findall(r"loading", source, re.I)),
        "errorHintCount": len(re.findall(r"error", source, re.I)),
    }


def main() -> None:
    captured_at = now_utc()
    live_main_sha = run("git", "ls-remote", "origin", "refs/heads/main").split()[0]
    local_head = run("git", "rev-parse", "HEAD")
    branch = run("git", "branch", "--show-current")
    remote_url = run("git", "remote", "get-url", "origin")
    status_lines = [line for line in run("git", "status", "--porcelain").splitlines() if line]
    live_main = {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "authority": AUTHORITY,
        "repository": "penghaibin9/saas",
        "remoteUrl": remote_url,
        "liveMainSha": live_main_sha,
        "localHeadSha": local_head,
        "branch": branch,
        "startedFromLiveMain": local_head == live_main_sha,
        "worktreeCleanBeforeW0Artifacts": not status_lines,
        "historicalEvidenceAccepted": False,
    }
    write_json("live-main.json", live_main)

    request = urllib.request.Request(
        "https://api.github.com/repos/penghaibin9/saas/pulls?state=open&per_page=100",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Codex-Internship-V8-W0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw_prs = json.load(response)
    relevant_prs = []
    for item in raw_prs:
        searchable = f"{item.get('title', '')} {item.get('head', {}).get('ref', '')}"
        if re.search(r"internship|实习", searchable, re.I):
            relevant_prs.append({
                "number": item["number"],
                "title": item["title"],
                "headRefName": item["head"]["ref"],
                "baseRefName": item["base"]["ref"],
                "draft": bool(item.get("draft")),
                "updatedAt": item["updated_at"],
                "url": item["html_url"],
            })
    write_json("open-internship-prs.json", {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "source": "GitHub public REST API",
        "githubCliAuthenticated": False,
        "items": relevant_prs,
    })

    menu = load_menu()
    leaves = flatten_menu(menu)
    menu_payload = {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "source": "frontend/src/config/navPlan.js::NAV_PLAN[internship]",
        "summary": {
            "workspaceCount": len(menu.get("children") or []),
            "leafCount": len(leaves),
            "visibleLeafCount": sum(1 for leaf in leaves if not leaf.get("hidden")),
            "hiddenCompatibilityLeafCount": sum(1 for leaf in leaves if leaf.get("hidden")),
            "uniquePathCount": len({leaf.get("path") for leaf in leaves if leaf.get("path")}),
        },
        "group": menu,
    }
    write_json("menu-tree.json", menu_payload)

    role_permissions = load_role_permissions()
    role_scopes = {
        "SCHOOL_ADMIN": "TENANT/SCHOOL; published explicit RoleTemplate at runtime",
        "COLLEGE_ADMIN": "COLLEGE; service-layer scope",
        "INTERN_MENTOR": "STABLE_ADVISOR_RELATION; own assigned students",
        "COUNSELOR": "RESPONSIBLE_CLASS; read-only internship collaboration",
        "SECURITY_AUDITOR": "AUDIT_READ_SCOPE; no internship writes",
        "EMPLOYMENT_TEACHER": "EMPLOYMENT_HANDOFF/ARCHIVE_READ_SCOPE",
        "STUDENT": "SELF; no Staff PC navigation",
    }
    role_projection = []
    for role in role_scopes:
        patterns = role_permissions.get(role, set())
        visible = [
            {k: leaf.get(k) for k in ("workspaceKey", "workspaceLabel", "label", "path", "permissionKey", "entryType")}
            for leaf in leaves
            if not leaf.get("hidden")
            and leaf.get("status") in {"implemented", "partial"}
            and permission_matches(patterns, leaf.get("permissionKey"))
        ]
        role_projection.append({
            "roleCode": role,
            "dataScope": role_scopes[role],
            "permissionSource": "published Permission Catalog" if role == "SCHOOL_ADMIN" else "backend/app/core/permissions.py",
            "internshipPermissionPatterns": sorted(p for p in patterns if p.startswith("internship.") or p == "*"),
            "visibleLeafCount": len(visible),
            "visibleMenuLeaves": visible,
        })
    write_json("role-menu-visibility.json", {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "projectionType": "LIVE_CODE_STATIC_PROJECTION",
        "runtimeDbTemplateRecheckRequired": True,
        "roles": role_projection,
    })

    routes = load_routes()
    staff_routes = routes["staffPc"]
    route_landings = []
    for leaf in leaves:
        target = str(leaf.get("path") or "").split("?", 1)[0]
        matches = [route for route in staff_routes if dynamic_route_matches(route["path"], target)]
        route_landings.append({
            "workspaceKey": leaf["workspaceKey"],
            "label": leaf.get("label"),
            "path": leaf.get("path"),
            "targetPathname": target,
            "hidden": bool(leaf.get("hidden")),
            "registeredStaffMatches": matches,
            "status": "REGISTERED" if matches else ("CROSS_MODULE" if target.startswith("/admin/employment") else "UNRESOLVED"),
        })
    write_json("route-landing.json", {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "sources": [
            "frontend/src/modules/internship/routes.js",
            "student-portal/src/router/index.js",
            "enterprise-portal/src/router/index.js",
        ],
        "staffPcRoutes": staff_routes,
        "studentPcRoutes": routes["studentPc"],
        "enterprisePortalRoutes": routes["enterprisePortal"],
        "menuLandings": route_landings,
        "unresolvedCount": sum(1 for item in route_landings if item["status"] == "UNRESOLVED"),
    })

    page_files = [
        "frontend/src/modules/internship/views/InternshipDashboardView.vue",
        "frontend/src/modules/internship/views/InternshipStudentListView.vue",
        "frontend/src/modules/internship/views/InternshipEnterpriseListView.vue",
        "frontend/src/modules/internship/views/InternshipMatchListView.vue",
        "frontend/src/modules/internship/views/InternshipApplicationReviewView.vue",
        "frontend/src/modules/internship/views/AttendanceView.vue",
        "frontend/src/modules/internship/views/AttendanceExceptionDetailView.vue",
        "frontend/src/modules/internship/views/LeaveReviewView.vue",
        "frontend/src/modules/internship/views/WeeklyReportListView.vue",
        "frontend/src/modules/internship/views/WeeklyReportDetailView.vue",
        "frontend/src/modules/internship/views/GuidanceVisitView.vue",
        "frontend/src/modules/internship/views/RiskDisposalView.vue",
        "frontend/src/modules/internship/views/InternshipComplianceView.vue",
        "frontend/src/modules/internship/views/ScoreView.vue",
        "frontend/src/modules/internship/views/ArchiveView.vue",
        "frontend/src/modules/internship/views/InternshipMaterialCenterView.vue",
        "student-portal/src/views/internship/InternshipView.vue",
        "student-portal/src/views/internship/InternshipSelectionView.vue",
        "miniapp/src/pages/student/internship/index.vue",
        "miniapp/src/pages/teacher/workbench/index.vue",
        "miniapp/src/pages/teacher/internship-review/index.vue",
        "enterprise-portal/src/layouts/EnterprisePortalLayout.vue",
        "enterprise-portal/src/views/EnterpriseHomeView.vue",
        "enterprise-portal/src/views/PositionListView.vue",
        "enterprise-portal/src/views/ApplicantListView.vue",
        "enterprise-portal/src/views/ApplicantDetailView.vue",
    ]
    metrics = [source_metrics(ROOT / name) for name in page_files if (ROOT / name).exists()]
    surface_file_counts = {
        "staffPc": len(list((ROOT / "frontend/src/modules/internship").rglob("*"))),
        "studentPc": len(list((ROOT / "student-portal/src/views/internship").rglob("*"))),
        "studentMini": len(list((ROOT / "miniapp/src/pages/student/internship").rglob("*"))),
        "teacherMini": len(list((ROOT / "miniapp/src/pages/teacher").glob("internship-*/*"))),
        "enterprisePortal": len(list((ROOT / "enterprise-portal/src").rglob("*"))),
    }
    write_json("page-view-inventory.json", {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "surfaceFileCounts": surface_file_counts,
        "keyPageMetrics": metrics,
        "interpretation": "Counts are source facts only; Browser decides visual overload and first-screen quality.",
    })

    surface_rows = [
        {"roleCode": "SCHOOL_ADMIN", "surface": "Staff PC", "dataScope": "TENANT/SCHOOL", "entry": "/admin/internship", "todayWorkTypes": ["application", "placement", "risk", "score", "archive"], "primaryCommands": ["BATCH_CREATE", "SCHOOL_CONFIRM_PLACEMENT", "SCORE_PUBLISH", "ARCHIVE"]},
        {"roleCode": "COLLEGE_ADMIN", "surface": "Staff PC", "dataScope": "COLLEGE", "entry": "/admin/internship", "todayWorkTypes": ["qualification", "application", "risk", "score"], "primaryCommands": ["QUALIFICATION_REVIEW", "APPLICATION_REVIEW", "RISK_ACTION"]},
        {"roleCode": "INTERN_MENTOR", "surface": "Staff PC + Teacher Mini", "dataScope": "STABLE_ADVISOR_RELATION", "entry": "/workbench + /pages/teacher/workbench/index", "todayWorkTypes": ["weekly", "attendanceException", "leave", "visit", "risk"], "primaryCommands": ["ATTENDANCE_EXCEPTION_DECISION", "LEAVE_REVIEW", "WEEKLY_REVIEW", "GUIDANCE_CREATE", "VISIT_RECTIFY"]},
        {"roleCode": "STUDENT", "surface": "Student PC + Student Mini", "dataScope": "SELF", "entry": "/internship + /pages/student/internship/index", "todayWorkTypes": ["selection", "compliance", "checkin", "report", "change", "appeal"], "primaryCommands": ["APPLICATION_SUBMIT", "CHECKIN", "AGREEMENT_CONFIRM", "EVALUATION_SUBMIT"]},
        {"roleCode": "COMPANY_ADMIN", "surface": "Enterprise Portal", "dataScope": "ENTERPRISE_MEMBER_GRANT_CONTEXT", "entry": "/home", "todayWorkTypes": ["companyProfile", "position", "candidate", "evaluation"], "primaryCommands": ["POSITION_SUBMIT", "ENTERPRISE_DECISION", "EVALUATION_SUBMIT"]},
        {"roleCode": "HR", "surface": "Enterprise Portal", "dataScope": "ENTERPRISE_MEMBER_GRANT_CONTEXT", "entry": "/home", "todayWorkTypes": ["position", "candidate"], "primaryCommands": ["POSITION_SUBMIT", "ENTERPRISE_DECISION"]},
        {"roleCode": "MENTOR", "surface": "Enterprise Portal", "dataScope": "FORMAL_INTERNSHIP_STUDENTS_ONLY", "entry": "/home", "todayWorkTypes": ["internshipStudent", "evaluation"], "primaryCommands": ["EVALUATION_SUBMIT"], "deniedReasons": ["Applicant materials are forbidden to enterprise MENTOR"]},
    ]
    surface_payload = {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "authorityBoundaries": [
            "ACCEPT_INTENT is enterprise intent and never School Placement",
            "Client companyId/campaign/role is never data-scope authority",
            "Student contact is server-revealed only after ContactSharing authority allows it",
            "Unsupported mobile commands require explicit PC_ONLY_REASON and destination",
        ],
        "rows": surface_rows,
    }
    write_json("4plus1-role-surface.json", surface_payload)
    write_json("role-surface-coverage.json", surface_payload)

    endpoints = extract_backend_endpoints()
    command_specs = {
        "BATCH_CREATE": ([r"batch", r"create|post"], "InternshipBatchListView.vue"),
        "PARTICIPANT_IMPORT": ([r"participant", r"import|upload"], "BatchParticipantScope.vue"),
        "QUALIFICATION_REVIEW": ([r"participant|student", r"qualif|eligib|review"], "InternshipStudentListView.vue"),
        "ENTERPRISE_REVIEW": ([r"enterprise", r"review|qualification"], "InternshipEnterpriseListView.vue"),
        "POSITION_REVIEW_PUBLISH": ([r"position", r"review|publish"], "InternshipPositionListView.vue"),
        "APPLICATION_SUBMIT": ([r"application", r"submit|create|post"], "Student PC/Mini application"),
        "APPLICATION_REVIEW": ([r"application", r"review"], "InternshipApplicationReviewView.vue"),
        "ENTERPRISE_DECISION": ([r"application|candidate", r"decision|accept.intent"], "Enterprise ApplicantDetailView.vue"),
        "SCHOOL_CONFIRM_PLACEMENT": ([r"placement|assign", r"confirm|create|post"], "InternshipMatchListView.vue"),
        "AGREEMENT_CONFIRM": ([r"agreement", r"confirm|sign"], "AgreementView.vue"),
        "CHECKIN": ([r"checkin", r"create|post"], "Student Mini checkin"),
        "ATTENDANCE_EXCEPTION_DECISION": ([r"exception", r"handle|decision"], "AttendanceExceptionDetailView.vue"),
        "MAKEUP_REVIEW": ([r"makeup", r"review"], "AttendanceView.vue / Teacher Mini"),
        "LEAVE_REVIEW": ([r"leave", r"review"], "LeaveReviewView.vue"),
        "WEEKLY_REVIEW": ([r"report|weekly", r"review"], "WeeklyReportDetailView.vue"),
        "GUIDANCE_CREATE": ([r"guidance", r"create|post"], "GuidanceVisitView.vue"),
        "VISIT_RECTIFY": ([r"visit|rectif", r"create|review|handle|transition"], "GuidanceVisitView.vue"),
        "CHANGE_REVIEW": ([r"change", r"review"], "ChangeRequestListView.vue"),
        "RISK_ACTION": ([r"risk", r"handle|follow|close"], "RiskDisposalView.vue"),
        "INCIDENT_TRANSITION": ([r"incident", r"transition|handle|close"], "InternshipComplianceView.vue"),
        "EVALUATION_SUBMIT": ([r"eval", r"submit|create|post"], "4+1 evaluation surfaces"),
        "SCORE_CALCULATE_REVIEW_PUBLISH": ([r"score", r"compute|calculate|review|publish"], "ScoreView.vue"),
        "SCORE_APPEAL_REVIEW": ([r"score.appeal|appeal", r"review|accept"], "ScoreView.vue"),
        "ARCHIVE": ([r"archive", r"create|execute|prepare|post"], "ArchiveView.vue"),
        "PACKAGE_GENERATE": ([r"archive|package", r"package|generate"], "ArchiveView.vue"),
    }
    commands = []
    for command, (patterns, primary_surface) in command_specs.items():
        candidates = candidate_endpoints(endpoints, patterns)
        commands.append({
            "command": command,
            "primaryStaffSurface": primary_surface,
            "endpointCandidates": candidates,
            "traceStatus": "BASELINE_CANDIDATES" if candidates else "UNMAPPED",
            "sealRequirement": "Before L4, select one canonical endpoint/service and trace scope/version/audit/readback/next surface.",
        })
    write_json("command-ownership.json", {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "backendEndpointInventoryCount": len(endpoints),
        "commands": commands,
        "unmappedCommands": [item["command"] for item in commands if item["traceStatus"] == "UNMAPPED"],
    })

    capability_specs = [
        ("CP-IX-01", "Batch Context", ["backend/app/modules/internship/services/internship_batch_context.py", "frontend/tests/internship.batchContext.contract.test.mjs"]),
        ("CP-IX-02", "Student Scope", ["backend/app/modules/internship/services/internship_scope.py", "backend/tests/test_internship_scope.py"]),
        ("CP-IX-03", "Enterprise Scope", ["backend/app/modules/internship/services/internship_enterprise_auth_service.py", "backend/tests/test_internship_enterprise_auth_context.py"]),
        ("CP-IX-04", "Recruitment/Position", ["backend/app/modules/internship/services/internship_recruitment_campaign_service.py", "backend/tests/test_internship_position.py"]),
        ("CP-IX-05", "Application/Selection", ["backend/app/modules/internship/services/internship_student_selection_service.py", "backend/tests/test_internship_application_material_snapshot.py"]),
        ("CP-IX-06", "Enterprise Decision", ["backend/app/modules/internship/services/internship_enterprise_application_decision_service.py", "backend/tests/test_internship_enterprise_application_decision.py"]),
        ("CP-IX-07", "Placement", ["backend/app/modules/internship/services/internship_placement_snapshot_service.py", "backend/tests/test_internship_placement_snapshot.py"]),
        ("CP-IX-08", "Contact Privacy", ["backend/app/modules/internship/services/internship_enterprise_access_service.py", "backend/tests/test_internship_enterprise_access.py"]),
        ("CP-IX-09", "Consent/Safety/Insurance", ["backend/app/modules/internship/services/internship_consent_service.py", "backend/tests/test_internship_student_compliance.py"]),
        ("CP-IX-10", "Agreement", ["backend/app/modules/internship/services/internship_agreement_service.py", "backend/tests/test_internship_agreement.py"]),
        ("CP-IX-11", "Attendance", ["backend/app/modules/internship/services/internship_makeup_service.py", "backend/tests/test_internship_attendance.py"]),
        ("CP-IX-12", "Process Reports", ["backend/app/modules/internship/services/internship_process_report_service.py", "backend/tests/test_internship_weekly_guidance.py"]),
        ("CP-IX-13", "Guidance/Visit", ["backend/app/modules/internship/services/internship_visit_service.py", "backend/tests/test_internship_visit_plan.py"]),
        ("CP-IX-14", "Risk/Complaint/Incident", ["backend/app/modules/internship/services/internship_complaint_service.py", "backend/tests/test_internship_complaint.py"]),
        ("CP-IX-15", "Evaluation/Score", ["backend/app/modules/internship/services/internship_score_service.py", "backend/tests/test_internship_score.py"]),
        ("CP-IX-16", "File/Material", ["backend/app/modules/internship/services/internship_material_center_service.py", "backend/tests/test_internship_material_center.py"]),
        ("CP-IX-17", "Archive", ["backend/app/modules/internship/services/internship_archive_service.py", "backend/tests/test_internship_archive.py"]),
        ("CP-IX-18", "Todo/Message/Audit", ["backend/app/modules/internship/services/internship_todo_helper.py", "backend/app/modules/internship/services/internship_audit_service.py"]),
        ("CP-IX-19", "4+1 Surface Parity", ["enterprise-portal/src/layouts/EnterprisePortalLayout.vue", "miniapp/src/pages/teacher/internship-review/index.vue"]),
        ("CP-IX-20", "Release/Recovery", ["scripts/check/check-internship-production-contracts.py", "scripts/check/check-internship-source-closure-v2.py"]),
    ]
    capability_rows = []
    for code, name, evidence in capability_specs:
        existing = [path for path in evidence if (ROOT / path).exists()]
        capability_rows.append({
            "code": code,
            "name": name,
            "evidenceSources": evidence,
            "existingSourceCount": len(existing),
            "status": "BASELINE_SOURCE_PRESENT" if len(existing) == len(evidence) else "BASELINE_GAP",
            "finalStatus": "PENDING_EXACT_HEAD_VERIFICATION",
        })
    write_json("capability-preservation-before.json", {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "head": local_head,
        "groups": capability_rows,
        "warning": "Source presence is not PASS. Final PASS requires exact-head tests, Browser, Server Truth and MySQL where applicable.",
    })

    findings = [
        ("IX-DX-P1-01", "Staff PC 12×99 high-exposure navigation", "frontend/src/config/navPlan.js"),
        ("IX-DX-P1-02", "Dashboard todo remains category/count oriented", "frontend/src/modules/internship/views/InternshipDashboardView.vue"),
        ("IX-DX-P1-03", "Match sidebar duplicates local process panels", "frontend/src/modules/internship/views/InternshipMatchListView.vue"),
        ("IX-DX-P1-04", "Four application menu leaves share one review surface", "frontend/src/config/navPlan.js"),
        ("IX-DX-P1-05", "Attendance command ownership overlaps ledger and full detail", "frontend/src/modules/internship/views/AttendanceView.vue"),
        ("IX-DX-P1-06", "Process report menu duplicates local tabs", "frontend/src/config/navPlan.js"),
        ("IX-DX-P1-07", "Eleven risk leaves are primarily one workbench filters", "frontend/src/config/navPlan.js"),
        ("IX-DX-P1-08", "Score page mixes rules, ledger and commands", "frontend/src/modules/internship/views/ScoreView.vue"),
        ("IX-DX-P1-09", "Material/archive ownership is exposed through repeated entries", "frontend/src/config/navPlan.js"),
        ("IX-DX-P1-10", "Material technical evidence is too prominent", "frontend/src/modules/internship/views/InternshipMaterialCenterView.vue"),
        ("IX-DX-P1-11", "Compliance surface is dense and needs visual grouping", "frontend/src/modules/internship/views/InternshipComplianceView.vue"),
        ("IX-DX-P1-12", "Guidance/visit sidebar duplicates local views", "frontend/src/config/navPlan.js"),
        ("IX-DX-P1-13", "Leave status menu leaves duplicate one workbench", "frontend/src/config/navPlan.js"),
        ("IX-DX-P1-14", "Student PC presents fourteen parallel tabs", "student-portal/src/views/internship/InternshipView.vue"),
        ("IX-DX-P1-15", "Student PC local failures may collapse into empty data", "student-portal/src/views/internship/InternshipView.vue"),
        ("IX-DX-P1-16", "Student Mini presents sixteen equal self-service entries", "miniapp/src/pages/student/internship/index.vue"),
        ("IX-DX-P1-17", "Teacher Mini static quick actions compete with Today First", "miniapp/src/pages/teacher/workbench/index.vue"),
        ("IX-DX-P1-18", "Teacher Mini anomaly facts require PC parity audit", "miniapp/src/pages/teacher/internship-review/index.vue"),
        ("IX-DX-P1-19", "Enterprise Portal must be part of journey acceptance", "enterprise-portal/src/layouts/EnterprisePortalLayout.vue"),
        ("IX-DX-P1-20", "Critical writes need persistent action receipts", "frontend/src/modules/internship/views"),
        ("IX-DX-P1-21", "Weekly resubmit needs human before/after comparison", "frontend/src/modules/internship/views/WeeklyReportDetailView.vue"),
        ("IX-DX-P1-22", "Cross-page and cross-surface queue resume is not unified", "frontend/src/modules/internship/composables/reviewQueue.js"),
    ]
    friction_items = [
        {"id": item_id, "finding": finding, "source": source, "severity": "P1", "status": "OPEN_BASELINE"}
        for item_id, finding, source in findings
    ]
    existing_friction = {
        item.get("id"): item for item in read_existing_json("friction-ledger.json").get("items", [])
        if isinstance(item, dict) and item.get("id")
    }
    for item in friction_items:
        previous = existing_friction.get(item["id"], {})
        if previous.get("status") and previous.get("status") != "OPEN_BASELINE":
            item["status"] = previous["status"]
            if previous.get("resolutionEvidence"):
                item["resolutionEvidence"] = previous["resolutionEvidence"]
    friction_ids = {item["id"] for item in friction_items}
    for item in existing_friction.values():
        if isinstance(item, dict) and item.get("id") not in friction_ids:
            friction_items.append(item)
    write_json("friction-ledger.json", {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "items": friction_items,
    })

    dimensions = [
        ("找事效率", 0.55), ("导航 IA", 0.45), ("核心流程成熟度", 0.90),
        ("决策效率", 0.78), ("操作省力", 0.76), ("4+1连续", 0.86),
        ("Recovery", 0.88), ("性能", 0.84), ("信任/安全", 0.93), ("发布可靠", 0.90),
    ]
    existing_score = read_existing_json("baseline-score.json")
    write_json("baseline-score.json", {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "scoreType": existing_score.get("scoreType", "AUTHORITY_STATIC_BASELINE_ONLY"),
        "dimensions": [{"dimension": name, "score": score, "max": 1.0} for name, score in dimensions],
        "total": round(sum(score for _, score in dimensions), 2),
        "browserValidation": existing_score.get("browserValidation", "PENDING"),
        "claim10of10": False,
    })

    screenshot_names = [
        "01-admin-menu-wide-role", "02-dashboard-today", "03-batch-students", "04-enterprise-list",
        "05-match-workspace", "06-application-review", "07-attendance-ledger", "08-attendance-exception-detail",
        "09-leave-review", "10-weekly-list", "11-weekly-resubmit-diff", "12-guidance-visit",
        "13-risk-workspace", "14-compliance-overview", "15-compliance-error", "16-score-workspace",
        "17-score-appeal", "18-archive", "19-material-center-human", "20-material-evidence-expanded",
        "21-student-pc-first-screen", "22-student-current-action", "23-student-selection-board", "24-student-local-error",
        "25-student-process-group", "26-teacher-workbench-today-390", "27-teacher-weekly-sequential",
        "28-teacher-abnormal-decision", "29-teacher-leave", "30-teacher-change", "31-teacher-receipt",
        "32-student-mini-home-390", "33-student-mini-compliance-next", "34-student-mini-self-service-grouped",
        "35-student-mini-checkin", "36-student-mini-weekly", "37-student-mini-change-leave", "38-enterprise-home",
        "39-enterprise-position-list", "40-enterprise-applicant-workbench", "41-enterprise-applicant-detail",
        "42-enterprise-contact-policy", "43-enterprise-accept-intent-receipt", "44-enterprise-intern-students-evaluation",
    ]
    existing_manifest = read_existing_json("browser-baseline/manifest.json")
    existing_captures = {
        item.get("name"): item for item in existing_manifest.get("requiredCaptures", [])
        if isinstance(item, dict) and item.get("name")
    }
    capture_rows = []
    for name in screenshot_names:
        previous = existing_captures.get(name, {})
        capture_rows.append({"name": name, **({k: v for k, v in previous.items() if k != "name"} or {"status": "PENDING"})})
    write_json("browser-baseline/manifest.json", {
        "schemaVersion": 1,
        "capturedAt": captured_at,
        "head": local_head,
        "status": existing_manifest.get("status", "PENDING_RUNTIME_CAPTURE"),
        "browserRule": "Start from a real role home/menu/todo/message; do not type hidden final object URLs.",
        "requiredCaptures": capture_rows,
    })

    print(json.dumps({
        "outputDirectory": str(OUT),
        "head": local_head,
        "liveMain": live_main_sha,
        "menuSummary": menu_payload["summary"],
        "relevantOpenPrCount": len(relevant_prs),
        "backendEndpointCount": len(endpoints),
        "unresolvedMenuLandings": sum(1 for item in route_landings if item["status"] == "UNRESOLVED"),
        "unmappedCommands": [item["command"] for item in commands if item["traceStatus"] == "UNMAPPED"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
