"""只读源码基线；不导入后端、不连库。唯一写入为同目录 JSON。

仓库根目录运行：python docs/06-开发施工与质量验收/产品化改造-20261023/附件/role_menu_baseline.py
需要 Python 3.10+ 和 Node.js（复用仓库真实纯配置导航函数）。
发布模板权限一律未知；staticBaseline 仅表示代码默认值，不能作为实际授权结论。
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).with_suffix('.json')
AA = 'backend/app/modules/academic_affairs'


def read(path):
    return (ROOT / path).read_text(encoding='utf-8-sig')


def literal(node, env):
    """仅解释权限表使用的字面量、集合展开和已解析常量，不执行源码。"""
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
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'set' and not node.args:
        return set()
    raise ValueError(ast.dump(node))


def constants(tree):
    env = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    try:
                        env[target.id] = literal(node.value, env)
                    except (ValueError, KeyError, TypeError):
                        pass
    return env


def match(patterns, code):
    return any(p == '*' or p == code or
               (p.endswith('.*') and (code == p[:-2] or code.startswith(p[:-1]))) or
               (p.startswith('*.') and code.endswith(p[1:])) for p in patterns)


@lru_cache(maxsize=None)
def syntax(path):
    return ast.parse(read(path))


@lru_cache(maxsize=None)
def imports(tree, path):
    result = {}
    package = path.removeprefix('backend/').removesuffix('.py').split('/')[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = '.'.join(package[:len(package)-node.level+1]) if node.level else ''
            module = '.'.join(x for x in [base, node.module] if x)
            for item in node.names:
                result[item.asname or item.name] = (module, item.name)
    return result


def module_file(module):
    path = 'backend/' + module.replace('.', '/')
    for candidate in [path + '.py', path + '/__init__.py']:
        if (ROOT / candidate).is_file():
            return candidate
    return None


def resolve(node, path, seen=frozenset()):
    """只替换源码常量/导入别名，保留无法证明的表达式，不执行调用。"""
    key = (path, ast.unparse(node))
    if key in seen:
        return ast.unparse(node)
    seen = seen | {key}
    tree = syntax(path)
    bindings = imports(tree, path)
    if isinstance(node, ast.Name):
        for item in tree.body:
            if isinstance(item, (ast.Assign, ast.AnnAssign)):
                targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                if any(isinstance(t, ast.Name) and t.id == node.id for t in targets):
                    return resolve(item.value, path, seen)
        if node.id in bindings:
            module, name = bindings[node.id]
            target = module_file(module)
            if target:
                return resolve(ast.Name(id=name), target, seen)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in bindings:
        module, name = bindings[node.value.id]
        target = module_file(module + '.' + name)
        if target:
            return resolve(ast.Name(id=node.attr), target, seen)
    if isinstance(node, ast.Call):
        args = [resolve(arg, path, seen) for arg in node.args]
        return ast.unparse(node.func) + '(' + ', '.join(args) + ')'
    return ast.unparse(node)


def routes(path):
    # shortcut: 这里只推导源码门禁和注册顺序，获准运行隔离应用后再对照真实路由表。
    source = read(path)
    tree = ast.parse(source)
    env = constants(tree)
    def expand(expression):
        return resolve(ast.parse(expression, mode='eval').body, path)
    prefixes, router_dependencies = {}, {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == 'APIRouter':
            prefixes[ast.unparse(node.targets[0])] = next((literal(k.value, env) for k in node.value.keywords if k.arg == 'prefix'), '')
            router_dependencies[ast.unparse(node.targets[0])] = [ast.unparse(x) for k in node.value.keywords if k.arg == 'dependencies' for x in k.value.elts]
    result = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in fn.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute) or dec.func.attr not in {'get', 'post', 'put', 'delete', 'patch'}:
                continue
            if not dec.args or not isinstance(dec.args[0], ast.Constant):
                continue
            router = ast.unparse(dec.func.value)
            deps, permissions, calls = list(router_dependencies.get(router, [])), [], []
            bindings = imports(tree, path)
            for n in ast.walk(fn):
                if not isinstance(n, ast.Call):
                    continue
                name = ast.unparse(n.func)
                if name == 'Depends':
                    expanded = expand(ast.unparse(n.args[0])) if n.args else ''
                    deps.append('Depends(' + expanded + ')')
                    if 'require_permission(' in expanded or 'require_any_permission(' in expanded:
                        codes = re.findall(r"['\"]([A-Za-z][\w]*(?:\.[\w*]+)+)['\"]", expanded)
                        if codes:
                            permissions.append({'mode': 'any' if 'any_permission' in expanded else 'all', 'codes': codes, 'expression': expanded})
                    if n.args and isinstance(n.args[0], ast.Name):
                        helper = next((x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == n.args[0].id), None)
                        if helper:
                            for call in ast.walk(helper):
                                if isinstance(call, ast.Call) and ast.unparse(call.func) == 'enforce_permission' and len(call.args) >= 2:
                                    try:
                                        code = ast.literal_eval(expand(ast.unparse(call.args[1])))
                                        if isinstance(code, str):
                                            permissions.append({'mode': 'all', 'codes': [code], 'expression': helper.name + ':' + str(call.lineno)})
                                    except (ValueError, SyntaxError):
                                        pass
                if name.split('.')[-1] in {'require_permission', 'require_any_permission'}:
                    vals = []
                    unresolved = False
                    for arg in n.args:
                        try:
                            val = ast.literal_eval(expand(ast.unparse(arg)))
                            if isinstance(val, str) and '.' in val:
                                vals.append(val)
                            else:
                                unresolved = True
                        except (ValueError, KeyError, TypeError, SyntaxError):
                            unresolved = True
                    permissions.append({'mode': 'any' if 'any_permission' in name else 'all', 'codes': [] if unresolved else vals, 'expression': expand(ast.unparse(n))})
                base = name.split('.')[0]
                imported = bindings.get(base, ('', ''))
                if ('.' in name and any(x in name for x in ('svc.', 'service.', 'legacy.', 'guard.', 'authority.', 'execution.'))) or '.services' in imported[0]:
                    calls.append(name)
            roles = [{'line': n.lineno, 'expression': ast.unparse(n)} for n in ast.walk(fn)
                     if isinstance(n, ast.If) and any(x in ast.unparse(n.test) for x in ('ACADEMIC_ADMIN', 'SCHOOL_ADMIN', 'COLLEGE_ADMIN', 'currentRoleCode', 'userType'))]
            summary = next((k.value.value for k in dec.keywords if k.arg == 'summary' and isinstance(k.value, ast.Constant)), '')
            helpers = {x.name: x for x in tree.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))}
            pending = [ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)]
            visited = {fn.name}
            while pending:
                name = pending.pop()
                if name in visited or name not in helpers:
                    continue
                visited.add(name)
                helper = helpers[name]
                calls.append(name + '（本文件:' + str(helper.lineno) + '）')
                for n in ast.walk(helper):
                    if not isinstance(n, ast.Call):
                        continue
                    nested = ast.unparse(n.func)
                    imported = bindings.get(nested.split('.')[0], ('', ''))
                    if '.services' in imported[0]:
                        calls.append(nested)
                    if nested in helpers:
                        pending.append(nested)
            if any('require_academic_process_request_permission' in dep for dep in deps):
                action = 'view' if dec.func.attr == 'get' else 'export' if '/export' in dec.args[0].value else 'manage'
                permissions.append({'mode': 'all', 'codes': ['academicAffairs.process.' + action], 'expression': 'domain_request_permissions.py:34-39（按实际判断顺序）'})
            if path.startswith(AA + '/routers/'):
                deps.append('聚合依赖：_require_aa_route_user / require_module(academicAffairs)')
            result.append({'method': dec.func.attr.upper(), 'path': '/api/v1' + prefixes.get(router, '') + dec.args[0].value,
                           'file': path, 'line': fn.lineno, 'handler': fn.name, 'dependencies': sorted(set(deps)),
                           'permissionChecks': permissions, 'roleChecks': roles, 'serviceCalls': sorted(set(calls)),
                           'summary': summary, 'access': '读' if dec.func.attr == 'get' else '写或命令（预检也按命令登记）',
                           'risk': '需复核：发布/审批/删除/导出/归档' if re.search(r'publish|review|approve|delete|export|archive|confirm', fn.name + dec.args[0].value) else '常规（未做风险评级）'})
    return result


def main():
    assert (ROOT / 'backend/app/core/permissions.py').is_file(), ROOT
    env = constants(ast.parse(read('backend/app/core/permissions.py')))
    roles = env['ROLE_PERMISSIONS']
    catalog = json.loads(read('shared/contracts/permission-catalog.json'))['entries']
    extension = json.loads(read('shared/contracts/permission-catalog-b8-concrete.json'))
    compatibility = json.loads(read('shared/contracts/permission-catalog-b8-compatibility.json'))
    universe = {e['permissionCode'] for e in catalog if e.get('lifecycle') == 'ACTIVE' and e.get('plane') == 'TENANT' and e.get('tenantAssignable')}
    universe.update(extension['entries'])
    universe.update(compatibility['entries'])
    assert match(['academicAffairs.*'], 'academicAffairs.grade.view')
    assert match(['*.view'], 'academicAffairs.grade.view')
    assert not match(['*.view'], 'academicAffairs.grade.publish')
    js = r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { NAV_PLAN, PLATFORM_PLAN, ACADEMIC_NAV_SOURCE_MODULES, getVisibleNavPlan, matchPermission } from './frontend/src/config/navPlan.js';
import { projectAcademicTeacherModules } from './frontend/src/modules/academicAffairs/config/academicTeacherNavigation.js';
import { projectAcademicCollegeModules } from './frontend/src/modules/academicAffairs/config/academicCollegeNavigation.js';
import { academicAffairsRoutes } from './frontend/src/modules/academicAffairs/academic-affairs.routes.js';
import academicRoutes from './frontend/src/modules/academicAffairs/routes/academic.routes.js';
import { projectNavigationRoutePermissions } from './frontend/src/router/navigationRouteProjection.js';
import { RECIPES, TODO_TYPE_ROUTES, TEMPLATE_ROLE_COVERAGE, resolveRecipe } from './frontend/src/modules/workbench/config/workbenchRecipes.js';
const roles = JSON.parse(fs.readFileSync(0, 'utf8'));
const flatten = (routes,parent='',meta={}) => routes.flatMap(r=>{
  const path = (r.path.startsWith('/') ? r.path : parent+'/'+r.path).replace(/\/{2,}/g,'/').replace(/\/$/,'') || '/';
  const merged = {...meta,...r.meta};
  return [{path,name:r.name,meta:merged,redirect:r.redirect},...flatten(r.children||[],path,merged)];
});
const rawRoutes = flatten([...academicAffairsRoutes,academicRoutes]);
const projectedRoutes = flatten(projectNavigationRoutePermissions([...academicAffairsRoutes,academicRoutes],[...NAV_PLAN,PLATFORM_PLAN]));
const routeMatch=(pattern,path)=>new RegExp('^'+pattern.split('/').filter(Boolean).map(s=>s.startsWith(':')?(s.endsWith('?')?'(?:/[^/]+)?':'/[^/]+'):'/'+s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('')+'/?$').test(path.split('?')[0]);
assert.ok(routeMatch('/schedule/:id?','/schedule'));
assert.ok(routeMatch('/schedule/:id?','/schedule/123'));
assert.ok(!routeMatch('/schedule/:id','/schedule'));
const routeAllowed=(meta,p)=>meta.permissionAny?.length ? meta.permissionAny.some(k=>matchPermission(p,k)) : meta.permissionKey ? matchPermission(p,meta.permissionKey) : meta.permissionAll?.length ? meta.permissionAll.every(k=>matchPermission(p,k)) : false;
const group = ms => ms.map(m => ({key:m.key,label:m.label,count:m.children.length,children:m.children}));
const result = {};
const mismatches = {};
for (const [role, patterns] of Object.entries(roles)) {
  const ctx = { currentRole: {roleCode:role} };
  const before = getVisibleNavPlan({permissionPatterns:patterns,ctxKey:role}).find(g=>g.key==='academic-affairs')?.children || [];
  const after = projectAcademicCollegeModules(projectAcademicTeacherModules(before,ctx),ctx);
  result[role] = {before:group(before),after:group(after),beforeCount:before.reduce((n,m)=>n+m.children.length,0),afterCount:after.reduce((n,m)=>n+m.children.length,0)};
  const leaves=after.flatMap(m=>m.children);
  mismatches[role]={
    visibleButDenied:leaves.filter(l=>!projectedRoutes.some(r=>routeMatch(r.path,l.path||'')&&routeAllowed(r.meta,patterns))).map(l=>({label:l.label,path:l.path})),
    allowedWithoutMenu:projectedRoutes.filter(r=>!r.redirect&&r.name&&routeAllowed(r.meta,patterns)&&!leaves.some(l=>routeMatch(r.path,l.path||''))).map(r=>({name:r.name,path:r.path,permissionAny:r.meta.permissionAny,permissionKey:r.meta.permissionKey}))
  };
}
assert.equal(result.ACADEMIC_TEACHER.afterCount, result.ACADEMIC_TEACHER.after.reduce((n,m)=>n+m.count,0));
assert.equal(result.COLLEGE_ADMIN.beforeCount,result.COLLEGE_ADMIN.afterCount);
const empty = getVisibleNavPlan({permissionPatterns:[]}).find(g=>g.key==='academic-affairs')?.children || [];
assert.ok(empty.every(m=>m.children.every(leaf=>!leaf.permissionKey && !leaf.permissionAny?.length && !leaf.menuRequiresAny?.length)));
console.log(JSON.stringify({roles:result,source:ACADEMIC_NAV_SOURCE_MODULES,normalized:NAV_PLAN.find(g=>g.key==='academic-affairs').children,
  rawRoutes,projectedRoutes,roleRouteMismatches:mismatches,workbench:{recipes:RECIPES,todoTypeRoutes:TODO_TYPE_ROUTES,coverage:TEMPLATE_ROLE_COVERAGE,resolved:Object.fromEntries(Object.keys(roles).map(role=>[role,resolveRecipe(role)]))},
  nullPermissions:getVisibleNavPlan({permissionPatterns:null}).find(g=>g.key==='academic-affairs')?.children || [],
  emptyPermissions:getVisibleNavPlan({permissionPatterns:[]}).find(g=>g.key==='academic-affairs')?.children || []}));
'''
    nav = json.loads(subprocess.run(['node', '--input-type=module', '-e', js], cwd=ROOT,
                                    input=json.dumps({k: sorted(v) for k, v in roles.items()}),
                                    text=True, encoding='utf-8', capture_output=True, check=True).stdout)
    role_data = {}
    for role, patterns in roles.items():
        expanded = sorted(c for c in universe if match(patterns, c))
        groups = {}
        for code in expanded:
            groups.setdefault('.'.join(code.split('.')[:2]), []).append(code)
        source_counts = []
        visible = [leaf for group in nav['roles'][role]['before'] for leaf in group['children']]
        for group in nav['source']:
            raw = [leaf for leaf in group['children'] if not leaf.get('permissionKey') or match(patterns, leaf['permissionKey'])]
            actual = [leaf for leaf in visible if str(leaf.get('sourceKey', '')).split(':')[0] == group['key']]
            source_counts.append({'key': group['key'], 'label': group['label'], 'rawTotal': len(group['children']), 'permissionOnly': len(raw), 'visibleBeforeRoleProjection': len(actual)})
        role_data[role] = {'runtimeStatus': '需模板数据，未计算' if not role.startswith('PLATFORM_') else '平台角色，不属于学校教务岗位',
                           'runtimePermissions': None, 'runtimeMenus': None,
                           'staticBaseline': {'patterns': sorted(patterns), 'permissions': expanded, 'byDomain': groups, 'menus': nav['roles'][role], 'sourceGroupCounts': source_counts}}
    role_catalog = []
    for node in ast.walk(syntax('backend/app/services/saas_role_templates.py')):
        if isinstance(node, ast.Call) and ast.unparse(node.func) == '_role':
            values = [ast.literal_eval(x) for x in node.args]
            role_catalog.append(dict(zip(['roleCode', 'name', 'category', 'defaultScope'], values),
                                     line=node.lineno,
                                     options={k.arg: ast.literal_eval(k.value) for k in node.keywords}))
    route_files = sorted((ROOT / AA / 'routers').glob('*.py'))
    all_routes = [row for p in route_files for row in routes(p.relative_to(ROOT).as_posix())]
    for p in sorted((ROOT / 'backend/app/api/v1').glob('*.py')):
        if p.name == 'academic.py' or 'academic' in p.name or p.name == 'mobile.py':
            rows = routes(p.relative_to(ROOT).as_posix())
            all_routes += [r for r in rows if p.name != 'mobile.py' or re.search(r'academic|schedule|grade|exam|course|textbook|attendance|teaching|workload', r['path'])]
    bundle = read(AA + '/routers/academic_affairs_bundle.py')
    order = re.findall(r'import_module\(\s*f"\{__package__\}\.([\w]+)"', bundle)
    order.insert(order.index('term_calendar_router'), 'scheduling_rule_router')
    # 选课最终路由在文件末尾追加整个 course_selection_router，先于历史大路由。
    assert 'router.routes.extend(course_selection_router.router.routes)' in read(AA + '/routers/academic_selection_final_router.py')
    order.insert(order.index('academic_selection_final_router') + 1, 'course_selection_router')
    order += ['academic_affairs'] + constants(ast.parse(bundle))['_EXTENSION_ROUTER_MODULES']
    extensions = set(constants(ast.parse(bundle))['_EXTENSION_ROUTER_MODULES']) | {'scheduling_rule_router'}
    exact_replaced = {(r['method'], r['path']) for r in all_routes if Path(r['file']).stem in extensions}
    active, seen = [], {}
    for module in order:
        for row in all_routes:
            if Path(row['file']).stem != module:
                continue
            if module == 'academic_affairs' and (row['method'], row['path']) in exact_replaced:
                row['mountStatus'] = '注册器先移除：扩展路由替代'
                continue
            key = (row['method'], re.sub(r'\{[^/{}]+\}', '{}', row['path']))
            if key in seen:
                row['mountStatus'] = '同形后注册被跳过：' + seen[key]
            else:
                row['mountStatus'] = '静态注册顺序保留（运行表未核实）'
                seen[key] = row['file'] + ':' + str(row['line'])
                active.append(row)
    for row in all_routes:
        if row['file'].startswith('backend/app/api/v1/'):
            row['mountStatus'] = '另行注册（运行表未核实）'
            active.append(row)
        row.setdefault('mountStatus', '未在聚合顺序发现，须追踪其他注册点')
        matrix = {}
        for role, patterns in roles.items():
            checks = row['permissionChecks']
            if not checks or any(not c['codes'] for c in checks):
                matrix[role] = '待核：身份或服务内门禁'
            else:
                ok = all((any if c['mode'] == 'any' else all)(match(patterns, code) for code in c['codes']) for c in checks)
                matrix[role] = '静态权限命中；仍需范围/角色/状态校验' if ok else '静态权限不命中'
        row['staticPermissionMatrix'] = matrix
    installs, role_hits, scope_hits = [], [], []
    for p in sorted((ROOT / AA).rglob('*.py')):
        path = p.relative_to(ROOT).as_posix()
        source = read(path)
        tree = ast.parse(source)
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in {'install', 'install_mobile_facade'}:
                installs.append({'file': path, 'line': n.lineno, 'body': ast.get_source_segment(source, n)})
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for i, line in enumerate(source.splitlines()[n.lineno-1:n.end_lineno], n.lineno):
                    if re.search(r'allowed_class_ids|build_affairs_context|_scope|assert_.*authority', line) and not line.lstrip().startswith('#'):
                        scope_hits.append({'file': path, 'function': n.name, 'line': i, 'code': line.strip()})
        for i, line in enumerate(source.splitlines(), 1):
            if 'ACADEMIC_ADMIN' in line or 'SCHOOL_ADMIN' in line:
                role_hits.append({'file': path, 'line': i, 'code': line.strip(), 'kind': '注释' if line.lstrip().startswith('#') else '代码或字符串，需结合所属函数复核'})
    references = {}
    for category, paths in {
        '后端业务': ['backend/app'], '前端': ['frontend/src'], '小程序': ['miniapp/src'],
        '学生端': ['student-portal/src'], '企业端': ['enterprise-portal/src'],
        '测试夹具': ['backend/tests', 'frontend/tests', 'miniapp/tests', 'student-portal/tests'],
        '脚本': ['backend/scripts', 'scripts'], '历史迁移': ['backend/alembic/versions'],
        '持续集成': ['.github/workflows'], '文档': ['docs'],
    }.items():
        found = subprocess.run(['git', '-c', 'core.quotepath=false', 'grep', '-l', '-w', 'COLLEGE_ADMIN', 'HEAD', '--', *paths],
                               cwd=ROOT, text=True, encoding='utf-8', capture_output=True)
        if found.returncode not in (0, 1):
            raise RuntimeError(found.stderr)
        references[category] = sorted(line.removeprefix('HEAD:') for line in found.stdout.splitlines())
    payload = {'schemaVersion': 1, 'sourceCommit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'limitations': ['未读取任何数据库；运行权限/发布模板未知', '接口表为语法树与源码注册顺序分析，未实例化应用', '静态矩阵不是端到端能否办理结论', '范围命中索引不等于完整查询安全验证'],
               'roles': role_data, 'roleCatalog': role_catalog, 'navigation': {k:v for k,v in nav.items() if k != 'roles'},
               'routerFileCount': len(route_files), 'routerOrder': order, 'routes': all_routes,
               'activeRouteCount': len(active), 'installFunctions': installs, 'roleMentions': role_hits,
               'scopeCallIndex': scope_hits, 'collegeAdminReferenceFiles': references,
               'sourceHashes': {p:hashlib.sha256(read(p).encode()).hexdigest() for p in ['backend/app/core/permissions.py','frontend/src/config/navPlan.js',AA+'/routers/academic_affairs_bundle.py']}}
    assert len(roles) > 10 and len(all_routes) > 100 and len(universe) > 100
    selected_route = next(r for r in active if r['handler'] == 'sel_batch_publish')
    assert any('academicAffairs.selection.manage' in check['codes'] for check in selected_route['permissionChecks'])
    assert any(Path(r['file']).stem == 'course_selection_router' for r in active)
    grade_publish = next(r for r in active if r['handler'] == 'grade_publish')
    assert grade_publish['staticPermissionMatrix']['ACADEMIC_TEACHER'] == '静态权限不命中'
    assert all(row['runtimePermissions'] is None for row in role_data.values())
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('仅源码静态基线；实际发布模板：需模板数据，未计算')
    print('角色数', len(roles), '路由文件数', len(route_files), '接口定义数', len(all_routes), '静态保留接口数', len(active))
    for role in ['ACADEMIC_ADMIN','COLLEGE_ADMIN','ACADEMIC_TEACHER','COUNSELOR','LEADER','SCHOOL_ADMIN']:
        m = role_data[role]['staticBaseline']['menus']
        print(role, '代码默认菜单投影前/后', m['beforeCount'], m['afterCount'])


if __name__ == '__main__':
    main()
