"""学工施工基线：仅用标准库读取源码，不导入应用、不连接数据库。

在仓库根目录运行 python docs/06-开发施工与质量验收/产品化改造-20261023/附件/affairs_role_baseline.py。
唯一写入是同目录 affairs_role_baseline.json；静态权限不冒充发布模板的实际授权。
"""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).with_suffix(".json")
ROLES = (
    "SECURITY_AUDITOR", "COLLEGE_ADMIN", "STUDENT_AFFAIRS", "STUDENT_AFFAIRS_ADMIN",
    "PSYCHOLOGY_TEACHER", "FUNDING_TEACHER", "YOUTH_LEAGUE", "ORG_PERSONNEL",
    "DORM_MANAGER", "COUNSELOR", "LEADER", "SCHOOL_ADMIN",
)
PREFIXES = ("studentAffairs.", "campusService.")
SERVICE_PREFIXES = ("affairs_", "campus_service", "dorm_", "mental", "funding",
                    "discipline", "orientation", "counselor", "student_affairs")
METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
SCOPE_RE = re.compile(r"scope|allowed_class|allowed_building|assert_student|assert_visible|require_student|resolve_student|self_student|tenant_get", re.I)
SENSITIVE_RE = re.compile(r"sensitive|mask|reveal|decrypt|psy|id_card|phone|guardian|family|audit|export", re.I)


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def ref(path, node):
    return f"{path}:{node.lineno}"


def literal(node, env):
    """白名单求值；不执行源码，也不求值函数调用（空集合除外）。"""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        values = []
        for item in node.elts:
            values.extend(literal(item.value, env) if isinstance(item, ast.Starred) else [literal(item, env)])
        return set(values) if isinstance(node, ast.Set) else values
    if isinstance(node, ast.Dict):
        return {literal(k, env): literal(v, env) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "set" and not node.args:
        return set()
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return literal(node.left, env) | literal(node.right, env)
    raise ValueError(ast.dump(node))


def constants(tree):
    env = {}
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        for target in targets:
            if isinstance(target, ast.Name) and node.value is not None:
                try:
                    env[target.id] = literal(node.value, env)
                except (ValueError, KeyError, TypeError):
                    pass
    return env


def match(code, patterns):
    return any(p == "*" or code == p or
               (p.endswith(".*") and (code == p[:-2] or code.startswith(p[:-1]))) or
               (p.startswith("*.") and code.endswith(p[1:])) for p in patterns)


def imports(tree):
    found = {}
    for node in (tree.body if isinstance(tree, ast.Module) else ast.walk(tree)):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app"):
            for alias in node.names:
                found[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found[alias.asname or alias.name] = alias.name
    return found


def qualified(node, aliases):
    name = ast.unparse(node)
    head, dot, tail = name.partition(".")
    return aliases.get(head, head) + (dot + tail if dot else "")


def calls(node, aliases):
    return sorted({qualified(n.func, aliases) for n in ast.walk(node) if isinstance(n, ast.Call)})


def permission_calls(node):
    found = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and re.search(r"permission|require_staff|get_current_user|require_student|^Depends$", ast.unparse(n.func)):
            found.append(ast.unparse(n))
    return sorted(set(found))


def string_values(node):
    return {n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def action_group(code):
    action = code.rsplit(".", 1)[-1]
    if any(x in code for x in ("sensitive", "Sensitive", "psyDetail")):
        return "敏感查看"
    if "export" in action.lower():
        return "导出"
    if action in {"view", "stat"}:
        return "查看"
    if any(x in action.lower() for x in ("review", "approve", "confirm")):
        return "审批或确认"
    return "办理"


def visible(row, patterns):
    if row.get("permissionKey") and not match(row["permissionKey"], patterns):
        return False
    if row.get("permissionAny") and not any(match(c, patterns) for c in row["permissionAny"]):
        return False
    # navPlan.getVisibleNavPlan 的学工叶子没有 permissionAll；防止未来静默误算。
    assert not row.get("permissionAll"), "菜单出现 permissionAll，先复核真实渲染器再扩展脚本"
    return True


def mobile_gate(path, method, direct):
    """对照四端契约156行、复核门75行、终审门112行的静态映射；不加载应用。"""
    for template, codes in direct.items():
        pattern = re.sub(r"\{[^}]+\}", "[^/]+", template)
        if re.fullmatch(pattern, path):
            return list(codes)
    write = method not in {"GET", "HEAD", "OPTIONS"}
    if path == "/api/v1/mobile/teacher/mental-stats":
        return ["studentAffairs.stats.view"]
    if path.startswith("/api/v1/mobile/teacher/mental"):
        return ["studentAffairs.mental.manage" if write else "studentAffairs.risk.psyDetail.view"]
    if path.startswith("/api/v1/mobile/teacher/talk"):
        return ["studentAffairs.talk.create" if write else "studentAffairs.talk.view"]
    prefix = "/api/v1/mobile/teacher/affairs"
    if not path.startswith(prefix):
        return []
    tail = path[len(prefix):]
    if tail in {"", "/"}:
        return ["studentAffairs.dashboard.view"]
    if tail.startswith("/leaves"):
        action = "view" if not write else "approve"
        for suffix, code in {"cancel-confirm": "cancelLeaveConfirm", "proxy-cancel": "cancelLeaveConfirm",
                             "overdue-handle": "overdue.handle", "extension-approve": "extension.approve"}.items():
            if write and tail.endswith("/" + suffix):
                action = code
        return ["studentAffairs.leave." + action]
    if tail.startswith("/risk"):
        action = "view" if not write else "handle"
        codes = ["studentAffairs.risk." + action, "studentAffairs.dorm.inspection.manage"]
        if write and tail.endswith("/close"):
            codes.insert(0, "studentAffairs.risk.close")
        return codes
    if tail.startswith("/dorm"):
        action = "view" if not write else "allocation.manage"
        if write and "/transfers/" in tail:
            action = "transfer.approve"
        elif write and "/exceptions/" in tail:
            action = "exception.handle"
        return ["studentAffairs.dorm." + action]
    if tail.startswith("/classes"):
        return ["studentAffairs.class." + ("view" if not write else "cadre.manage" if "/cadres" in tail else "create")]
    for domain, read_code, write_codes in (
        ("family-contacts", "homeSchool.view", ["homeSchool.record.create"]),
        ("aid", "aid.view", ["aid.approve", "aid.counselorReview"]),
        ("funding", "funding.view", ["funding.approve"]),
        ("discipline", "discipline.view", ["discipline.approve"]),
    ):
        if tail.startswith("/" + domain):
            return ["studentAffairs." + code for code in (write_codes if write else [read_code])]
    return ["__AFFAIRS_MOBILE_PERMISSION_NOT_REGISTERED__"]


def collect_sources():
    sources, trees, aliases = {}, {}, {}
    for path in sorted((ROOT / "backend/app").rglob("*.py")):
        name = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8-sig")
        sources[name] = source
        selected = (path.name.startswith(SERVICE_PREFIXES) or
                    path.name in {"affairs.py", "student.py", "teacher_scope.py", "permissions.py",
                                  "student_affairs_permission_registry.py", "mobile.py", "mobile_orientation_teacher.py"} or
                    "affairs" in path.name or "affairs" in name and "/student_portal/" in name or
                    "install" in source and "affairs_" in source)
        if selected:
            trees[name] = ast.parse(source, filename=name)
            aliases[name] = imports(trees[name])
    return sources, trees, aliases


def extract_endpoints(sources, trees, alias_map):
    rows = []
    selected = {"student_affairs.py", "campus_service.py", "orientation.py", "mobile_orientation_teacher.py", "mobile.py"}
    for path, tree in trees.items():
        if not (("/api/v1/" in path and (Path(path).name in selected or Path(path).name.startswith("affairs_"))) or
                "/modules/student_affairs/routers/" in path or ("/services/" in path and Path(path).name.startswith(SERVICE_PREFIXES))):
            continue
        local_functions = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        local_constants = constants(tree)
        router_prefix, router_deps = {}, {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and ast.unparse(n.value.func).endswith("APIRouter"):
                for target in n.targets:
                    kw = {k.arg: k.value for k in n.value.keywords}
                    router_prefix[ast.unparse(target)] = ast.literal_eval(kw["prefix"]) if "prefix" in kw else ""
                    router_deps[ast.unparse(target)] = ast.unparse(kw["dependencies"]) if "dependencies" in kw else ""
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            alias = {**alias_map[path], **imports(node)}
            for dec in node.decorator_list:
                if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in METHODS and dec.args):
                    continue
                route = ast.literal_eval(dec.args[0]) if isinstance(dec.args[0], ast.Constant) else ast.unparse(dec.args[0])
                prefix = router_prefix.get(ast.unparse(dec.func.value))
                route_path = (prefix or "") + route
                text = "\n".join(sources[path].splitlines()[node.lineno - 1:node.end_lineno])
                if Path(path).name == "mobile.py" and not re.search(
                        r"^/(?:mobile/)?(?:affairs|campus-service|orientation)(?:/|$)|"
                        r"^/mobile/teacher/(?:affairs|campus-service|orientation|mental|mental-stats|talk|talk-stats|my-classes|my-students|risk-students|risk-students-page|student)(?:/|$)|"
                        r"^/mobile/(?:home|me/portal-config|student/(?:agenda|cases|search|services))$", route_path):
                    continue
                dependencies = sorted(set(permission_calls(node.args) + permission_calls(dec)))
                inline = permission_calls(ast.Module(body=node.body, type_ignores=[]))
                codes = sorted({s for n in (node.args, dec, ast.Module(body=node.body, type_ignores=[]))
                                for s in string_values(n) if re.fullmatch(r"(?:studentAffairs|campusService)\.[A-Za-z.]+", s)})
                helper_authorization = []
                pending = [c.func.id for c in ast.walk(node) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)]
                visited = {node.name}
                while pending:
                    name = pending.pop()
                    if name in visited or name not in local_functions:
                        continue
                    visited.add(name)
                    helper = local_functions[name]
                    values = set(string_values(helper))
                    for child in ast.walk(helper):
                        if isinstance(child, ast.Name):
                            value = local_constants.get(child.id)
                            if isinstance(value, (list, tuple, set)):
                                values.update(v for v in value if isinstance(v, str))
                        elif isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
                            pending.append(child.func.id)
                    helper_codes = sorted(s for s in values if s.startswith(PREFIXES))
                    if helper_codes or permission_calls(helper):
                        helper_authorization.append({"function": name, "source": ref(path, helper),
                                                     "codes": helper_codes, "checks": permission_calls(helper)})
                        codes = sorted(set(codes) | set(helper_codes))
                rows.append({
                    "method": dec.func.attr.upper(), "path": "/api/v1" + route_path,
                    "source": ref(path, dec), "handler": node.name,
                    "handler_source": ref(path, node), "summary": next((ast.literal_eval(k.value) for k in dec.keywords if k.arg == "summary" and isinstance(k.value, ast.Constant)), ""),
                    "router_dependency": router_deps.get(ast.unparse(dec.func.value), ""),
                    "dependencies": dependencies, "inline_authorization": inline, "permission_codes": codes,
                    "authorization_helpers": helper_authorization,
                    "role_literals": sorted(s for s in string_values(node) if s in ROLES or s in {"STUDENT", "STAFF"}),
                    "calls": calls(node, alias), "scope_calls": [c for c in calls(node, alias) if SCOPE_RE.search(c)],
                    "write": dec.func.attr not in {"get", "head", "options"},
                    "sensitivity_signals": sorted(set(SENSITIVE_RE.findall(route + " " + text))),
                    "runtime_patch": "/services/" in path, "prefix_unresolved": prefix is None,
                    "final_handler_status": "静态声明；运行时覆盖及服务替换见文档S7/S9，未启动应用",
                })
    return sorted(rows, key=lambda r: (r["path"], r["method"], r["source"]))


def collect_services(sources, trees, alias_map):
    records, installers, models = [], [], []
    all_calls = []
    for path, tree in trees.items():
        alias = dict(alias_map[path])
        for imported in ast.walk(tree):
            if isinstance(imported, ast.ImportFrom) and (imported.module or "").startswith("app"):
                alias.update({a.asname or a.name: f"{imported.module}.{a.name}"
                              for a in imported.names if a.name.startswith("install")})
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = qualified(node.func, alias)
                if name == "install" and any(isinstance(n, ast.FunctionDef) and n.name == "install" for n in tree.body):
                    name = path.removeprefix("backend/").removesuffix(".py").replace("/", ".") + ".install"
                all_calls.append((name, ref(path, node), ast.unparse(node)))
        if "/models/" in path and (Path(path).name.startswith(SERVICE_PREFIXES) or Path(path).name in {"affairs.py", "student.py", "teacher_scope.py"}):
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    for n in node.body:
                        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in n.targets):
                            models.append({"class": node.name, "table": ast.literal_eval(n.value), "source": ref(path, node)})
        if not ("/services/" in path and Path(path).name.startswith(SERVICE_PREFIXES)):
            continue
        functions = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_alias = {**alias, **imports(node)}
                functions.append({"name": node.name, "source": ref(path, node), "end_line": node.end_lineno,
                                  "scope_calls": [c for c in calls(node, function_alias) if SCOPE_RE.search(c)],
                                  "sensitive_audit_calls": [c for c in calls(node, function_alias) if SENSITIVE_RE.search(c)],
                                  "calls": calls(node, function_alias),
                                  "states": sorted(s for s in string_values(node) if re.fullmatch(r"[A-Z][A-Z_]{2,40}", s))})
        model_imports = sorted({f"{n.module}.{a.name}" for n in ast.walk(tree)
                                if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("app.models")
                                for a in n.names})
        records.append({"path": path, "functions": functions, "model_imports": model_imports})
        install = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "install"), None)
        if install:
            alias = {**alias, **imports(install)}
            mutations = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, (ast.Attribute, ast.Subscript)):
                            mutations.append({"target": qualified(target, alias), "replacement": ast.unparse(node.value), "source": ref(path, node)})
                elif isinstance(node, ast.Call) and (ast.unparse(node.func) == "setattr" or ast.unparse(node.func).endswith(("add_api_route", "include_router")) or
                                                    qualified(node.func, alias).startswith("app.") and ast.unparse(node.func).endswith(".update")):
                    mutations.append({"target": qualified(node.func, alias), "replacement": ast.unparse(node), "source": ref(path, node)})
            module = path.removeprefix("backend/").removesuffix(".py").replace("/", ".")
            installers.append({"module": module, "source": ref(path, install), "calls": calls(install, alias), "mutation_candidates": mutations,
                    "dynamic_imports": [{"source": ref(path, n), "expression": ast.unparse(n)} for n in ast.walk(tree)
                                                   if isinstance(n, ast.Call) and any(v in ast.unparse(n.func) for v in ("import_module", "__import__"))]})
    for row in installers:
        row["callers"] = [{"source": loc, "expression": expr} for name, loc, expr in all_calls if name == row["module"] + ".install"]
    return records, installers, models


def self_check():
    assert match("studentAffairs.risk.psyDetail.view", {"*.view"})
    assert match("studentAffairs.leave.view", {"studentAffairs.*"})
    assert not match("studentAffairsX.leave.view", {"studentAffairs.*"})
    assert not match("studentAffairs.leave.approve", {"*.view"})
    assert literal(ast.parse("{'a', *X}", mode="eval").body, {"X": {"b"}}) == {"a", "b"}
    try:
        literal(ast.parse("__import__('os')", mode="eval").body, {})
    except ValueError:
        pass
    else:
        raise AssertionError("求值器不应允许导入")
    assert visible({"permissionAny": ["x", "y"]}, {"y"})
    assert not visible({"permissionKey": "x"}, {"y"})
    assert mobile_gate("/api/v1/mobile/teacher/mental", "GET", {}) == ["studentAffairs.risk.psyDetail.view"]
    assert mobile_gate("/api/v1/mobile/teacher/affairs/new-write", "POST", {}) == ["__AFFAIRS_MOBILE_PERMISSION_NOT_REGISTERED__"]
    fixture = '''
router = APIRouter(prefix="/student-affairs")
_REQUIRED = ("studentAffairs.aid.approve",)
def gate(user):
    return all(has_permission(user, code) for code in _REQUIRED)
@router.get("/one")
def one(user=Depends(require_staff)):
    from app.services import affairs_aid_service as svc
    gate(user)
    return svc.list_batches(user)
@router.get("/two")
def two(user=Depends(get_current_user)):
    from app.services import affairs_funding_service as svc
    return svc.list_projects(user)
'''
    name = "backend/app/api/v1/affairs_fixture.py"
    tree = ast.parse(fixture)
    rows = extract_endpoints({name: fixture}, {name: tree}, {name: imports(tree)})
    assert rows[0]["path"] == "/api/v1/student-affairs/one"
    assert "Depends(require_staff)" in rows[0]["dependencies"]
    assert "studentAffairs.aid.approve" in rows[0]["permission_codes"]
    assert "app.services.affairs_aid_service.list_batches" in rows[0]["calls"]
    assert "app.services.affairs_funding_service.list_projects" in rows[1]["calls"]
    assert "app.services.affairs_funding_service.list_batches" not in rows[0]["calls"]
    parent = "backend/app/services/affairs_parent.py"
    child = "backend/app/services/affairs_child.py"
    fixture_sources = {parent: "def install():\n    from app.services.affairs_child import install as install_child\n    install_child()\n",
                       child: "def install():\n    return None\n"}
    fixture_trees = {p: ast.parse(s) for p, s in fixture_sources.items()}
    _, installers, _ = collect_services(fixture_sources, fixture_trees, {p: imports(t) for p, t in fixture_trees.items()})
    child_record = next(i for i in installers if i["module"].endswith("affairs_child"))
    assert child_record["callers"] == [{"source": parent + ":3", "expression": "install_child()"}]


def main():
    self_check()
    assert Path.cwd().resolve() == ROOT, "请在本工作树仓库根目录运行"
    sources, trees, alias_map = collect_sources()
    permissions = constants(trees["backend/app/core/permissions.py"])["ROLE_PERMISSIONS"]
    registry = constants(trees["backend/app/core/student_affairs_permission_registry.py"])
    canonical = set(registry["_PERMISSION_CODES"])
    used = {s for source in sources.values() for s in re.findall(r'["\x27]((?:studentAffairs|campusService)\.[A-Za-z]+(?:\.[A-Za-z]+)+)["\x27]', source)}
    # 通用导出授权确实使用两段权限码；orientation 和 talk 两段串仅是域前缀/工作台入口键。
    used.add("studentAffairs.export")
    universe = canonical | used
    nav = json.loads(read("shared/contracts/navigation-surface-contract.json"))
    surfaces = [s for s in nav["surfaces"] if s["groupKey"] == "student-affairs" and not s["hidden"]]
    roles = {}
    for role in ROLES:
        patterns = permissions[role]
        codes = sorted(c for c in universe if match(c, patterns))
        grouped = defaultdict(lambda: defaultdict(list))
        for code in codes:
            grouped[".".join(code.split(".")[:2])][action_group(code)].append(code)
        menus = defaultdict(list)
        for row in surfaces:
            if visible(row, patterns):
                menus[row["workspaceLabel"]].append(row)
        roles[role] = {
            "static_patterns": sorted(patterns), "static_affairs_permissions": codes,
            "permissions_by_domain_action": grouped,
            "static_menus": {label: {"count": len(items), "items": items} for label, items in menus.items()},
            "static_menu_count": sum(map(len, menus.values())),
            "runtime_status": "需模板数据，未计算",
            "runtime_permissions": None, "runtime_menus": None,
            "runtime_reason": "SCHOOL_ADMIN 恒读发布模板" if role == "SCHOOL_ADMIN" else
                "activeContextId 为 role:数字 且数据库启用时优先读取 SYSTEM 发布模板或 CUSTOM 权限表；仅无该上下文时适用静态基线。临时授权也未计算。",
        }
    endpoints = extract_endpoints(sources, trees, alias_map)
    for row in endpoints:
        extra = mobile_gate(row["path"], row["method"], registry.get("STUDENT_AFFAIRS_MOBILE_DIRECT_PERMISSIONS", {}))
        if "/orientation.py:" in row["source"]:
            extra = ["studentAffairs.orientation." + ("view" if not row["write"] else "export" if "/export" in row["path"] else "manage")]
        row["inferred_shared_gate_codes"] = extra
        row["effective_permission_codes"] = sorted(set(row["permission_codes"] + extra))
    services, installers, models = collect_services(sources, trees, alias_map)
    consumers = []
    for directory in ("frontend/src", "miniapp/src", "student-portal/src", "backend/app", "backend/tests", "frontend/tests", "scripts", ".github"):
        for path in sorted((ROOT / directory).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".js", ".mjs", ".ts", ".vue", ".json", ".yml", ".yaml"}:
                for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
                    if re.search(r"campus-service|campusService|campus_service", line):
                        excerpt = line.strip()[:500]
                        if re.search(r"password|secret|mysql[+:]|login_name|loginName|counselor0[0-9]|student0[0-9]|sa_admin0[0-9]|school_admin0[0-9]", excerpt, re.I):
                            excerpt = "在校服务引用；账号或凭据相关文字已省略，原文见定位"
                        consumers.append({"source": f"{path.relative_to(ROOT).as_posix()}:{line_no}", "line": excerpt})
    input_paths = {"backend/app/core/permissions.py", "backend/app/core/affairs_security.py", "backend/app/core/student_affairs_permission_registry.py",
                   "shared/contracts/navigation-surface-contract.json", "frontend/src/config/navPlan.js"}
    input_paths.update(s["path"] for s in services)
    input_paths.update(e["source"].rsplit(":", 1)[0] for e in endpoints)
    data = {
        "schema_version": 1,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "evidence_level": "仅源码静态基线；未加载应用、未连接数据库、未运行测试或真实请求",
        "scope_notes": ["权限全集为后端注册表加应用源码实际引用的学工及旧在校服务权限；工作台共享权限只参加菜单计算。",
                        "静态菜单数量未叠加商业模块许可、角色模板、自定义角色、临时授权、前端权限别名与登录上下文。",
                        "补丁赋值表为静态候选，含对象属性写入；最终生效及安装顺序须结合文档S9。",
                        "移动总路由按路径和端点正文筛入学工相关声明，跨域邻接项明确保留。"],
        "registered_affairs_permissions": sorted(canonical), "permission_universe": sorted(universe),
        "used_unregistered_affairs_permissions": sorted(c for c in used - canonical if c.startswith("studentAffairs.")),
        "roles": roles, "menu_count": len(surfaces), "menu_groups": dict(Counter(r["workspaceLabel"] for r in surfaces)),
        "menus": surfaces, "endpoints": endpoints,
        "mobile_direct_permissions": registry.get("STUDENT_AFFAIRS_MOBILE_DIRECT_PERMISSIONS", {}),
        "services": services, "installers": installers, "models": models, "legacy_consumers": consumers,
        "source_hashes": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(input_paths)},
    }
    assert len(surfaces) == len({s["surfaceKey"] for s in surfaces}), "菜单键重复"
    assert canonical <= universe
    assert all(r["runtime_permissions"] is None for r in roles.values())
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"源码提交：{data['source_commit']}")
    print(f"学工登记权限 {len(canonical)} 项；菜单 {len(surfaces)} 项、{len(data['menu_groups'])} 组；接口声明 {len(endpoints)} 项；安装器 {len(installers)} 个。")
    for role, row in roles.items():
        print(f"{role}：静态权限 {len(row['static_affairs_permissions'])}，静态菜单 {row['static_menu_count']}；运行时需模板数据，未计算。")
    print(f"已生成：{OUTPUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
