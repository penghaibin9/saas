"""毕设施工前静态基线：只读源码，不导入应用，不连接数据库。

在仓库根目录直接运行本文件；仅写同目录 graduation_role_baseline.json。
权限展开是静态后备口径；发布模板、临时授权及真实业务关系一律未计算。
路由为源码注册链推导，不冒充 FastAPI 运行时验收。
"""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).with_suffix('.json')
GD = 'app.modules.graduation'
ROLES = {
    'GRADUATION_ADMIN': '校级毕设管理员', 'GD_COLLEGE_ADMIN': '学院毕设管理员',
    'GD_MAJOR_ADMIN': '专业毕设负责人', 'GD_MENTOR': '指导教师',
    'GD_REVIEWER': '评阅教师', 'GD_DEFENSE_SECRETARY': '答辩秘书',
    'GD_DEFENSE_EXPERT': '答辩专家', 'GD_GRADE_ADMIN': '成绩管理员',
    'COLLEGE_ADMIN': '学院综合管理员', 'LEADER': '领导',
    'SCHOOL_ADMIN': '学校管理员', 'STUDENT': '学生',
}
HTTP = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}


def design_path(key):
    return any(x in key for x in ['/api/v1/graduation/', '/api/v1/mobile/graduation/',
               '/api/v1/mobile/teacher/graduation', '/api/v1/portal/graduation/',
               '/api/v1/mobile/student/graduation/'])


def read(path):
    return (ROOT / path).read_text(encoding='utf-8-sig')


def ref(path, node):
    return f'{path}:{node.lineno}'


def literal(node, env=None):
    """仅解释常量集合语法，不使用 eval/exec，也不调用源码函数。"""
    env = env or {}
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        result = []
        for item in node.elts:
            result.extend(literal(item.value, env)) if isinstance(item, ast.Starred) else result.append(literal(item, env))
        return set(result) if isinstance(node, ast.Set) else result
    if isinstance(node, ast.Dict):
        result = {}
        for key, value in zip(node.keys, node.values):
            if key is None:
                result.update(literal(value, env))
            else:
                result[literal(key, env)] = literal(value, env)
        return result
    if isinstance(node, ast.JoinedStr):
        return ''.join(str(literal(x.value, env)) if isinstance(x, ast.FormattedValue) else x.value for x in node.values)
    if isinstance(node, ast.SetComp) and len(node.generators) == 1:
        gen = node.generators[0]
        assert isinstance(gen.target, ast.Name) and not gen.ifs
        return {literal(node.elt, {**env, gen.target.id: x}) for x in literal(gen.iter, env)}
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        values = [literal(x, env) for x in node.args]
        if node.func.id in {'set', 'frozenset'}:
            return set(values[0]) if values else set()
        if node.func.id == '_group':
            return dict.fromkeys(values[1:], values[0])
    raise ValueError(f'不支持的常量语法：{ast.dump(node)[:100]}')


def constants(path):
    env = {}
    tree = ast.parse(read(path))
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(target, ast.Name) and node.value is not None:
                try:
                    env[target.id] = literal(node.value, env)
                except (ValueError, KeyError, TypeError):
                    pass
    return env


def matches(code, patterns):
    return any(p == '*' or p == code or (p.endswith('.*') and (code == p[:-2] or code.startswith(p[:-1])))
               or (p.startswith('*.') and code.endswith(p[1:])) for p in patterns)


class Sources:
    def __init__(self):
        self.modules = {}
        self.functions = {}
        for path in sorted((ROOT / 'backend/app').rglob('*.py')):
            relative = path.relative_to(ROOT).as_posix()
            if not ('/modules/graduation/' in relative or '/student_portal/' in relative
                    or '/api/v1/' in relative and ('graduation' in path.name or path.name in {'mobile.py', 'platform_integrity.py'})
                    or '/services/mobile_' in relative or path.name == '_mobile_teacher_service_impl.py'):
                continue
            module = relative.removeprefix('backend/').removesuffix('.py').replace('/', '.')
            if module.endswith('.__init__'):
                module = module.removesuffix('.__init__')
            source = read(relative)
            tree = ast.parse(source, filename=relative)
            imports = {}
            scoped_imports = []
            scopes = [x for x in ast.walk(tree) if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))]
            for node in ast.walk(tree):
                found = {}
                if isinstance(node, ast.ImportFrom):
                    package = module if path.name == '__init__.py' else module.rsplit('.', 1)[0]
                    base = node.module or ''
                    if node.level:
                        base = '.'.join(package.split('.')[:len(package.split('.')) - node.level + 1]) + ('.' + base if base else '')
                    for alias in node.names:
                        found[alias.asname or alias.name] = base + '.' + alias.name
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        found[alias.asname or alias.name] = alias.name
                if found:
                    owners = [x for x in scopes if x.lineno <= node.lineno <= x.end_lineno]
                    if owners:
                        owner = min(owners, key=lambda x:x.end_lineno-x.lineno)
                        scoped_imports.append((owner.lineno, owner.end_lineno, found))
                    else:
                        imports.update(found)
            late_imports = {alias.asname or alias.name: node.lineno for node in tree.body
                            if isinstance(node, ast.ImportFrom) for alias in node.names}
            aliases = {node.targets[0].id: (ast.unparse(node.value), node.lineno) for node in tree.body
                       if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                       and isinstance(node.value, (ast.Name, ast.Attribute))}
            for node in tree.body:
                if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                        and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) in {'sanitize_xlsx_export', '_conflict_guard'}
                        and node.value.args and isinstance(node.value.args[0], ast.Name)):
                    aliases[node.targets[0].id] = (node.value.args[0].id, node.lineno)
            info = {'path': relative, 'source': source, 'tree': tree, 'imports': imports, 'import_lines':late_imports}
            info['aliases'] = aliases
            info['scoped_imports'] = scoped_imports
            self.modules[module] = info
            self._functions(module, tree.body, '')

    def _functions(self, module, body, prefix):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + node.name
                self.functions[module + '.' + name] = (module, node)
                self._functions(module, node.body, name + '.')

    def imports_at(self, module, line):
        result = dict(self.modules[module]['imports'])
        for start, end, values in sorted(self.modules[module]['scoped_imports'], key=lambda x:x[1]-x[0], reverse=True):
            if start <= line <= end:
                result.update(values)
        return result

    def resolve(self, module, expr):
        name = ast.unparse(expr)
        head, *tail = name.split('.')
        imports = self.imports_at(module, getattr(expr, 'lineno', 1))
        alias = self.modules[module]['aliases'].get(head)
        if alias and alias[0] != head and head not in imports:
            return self.resolve(module, ast.parse(alias[0], mode='eval').body) + ('.' + '.'.join(tail) if tail else '')
        if not tail and head not in imports and module + '.' + head not in self.functions:
            nested = [k for k in self.functions if k.startswith(module + '.') and k.endswith('.' + head)]
            if len(nested) == 1:
                return nested[0]
        return imports.get(head, module + '.' + head) + ('.' + '.'.join(tail) if tail else '')

    def canonical(self, name):
        seen = set()
        while name not in seen:
            seen.add(name)
            module, _, symbol = name.rpartition('.')
            if module not in self.modules:
                break
            if module == 'app.services.mobile_teacher_service' and name not in self.functions:
                name = 'app.services._mobile_teacher_service_impl.' + symbol
                continue
            alias = self.modules[module]['aliases'].get(symbol)
            if alias and (name not in self.functions or alias[1] > self.functions[name][1].lineno):
                name = self.resolve(module, ast.parse(alias[0], mode='eval').body)
                continue
            if name in self.functions and self.modules[module]['import_lines'].get(symbol, 0) < self.functions[name][1].lineno:
                break
            target = self.modules[module]['imports'].get(symbol)
            if not target:
                break
            name = target
        return name

    def evidence(self, module, node):
        return ref(self.modules[module]['path'], node)

    def calls(self, module, node):
        result = set()
        for call in (x for x in ast.walk(node) if isinstance(x, ast.Call)):
            for expr in [call.func, *call.args]:
                if not isinstance(expr, (ast.Name, ast.Attribute)):
                    continue
                symbol = self.canonical(self.resolve(module, expr))
                head = ast.unparse(expr).split('.')[0]
                imported = head in self.imports_at(module, getattr(expr, 'lineno', 1))
                if symbol in self.functions or (imported and symbol.startswith(GD) and any(x in symbol for x in ('.services.', '.materials.', '.policies.'))):
                    result.add(symbol)
        return sorted(result)

    def router(self, module, var='router', prefix='', dependencies=(), stack=()):
        assert (module, var) not in stack, (module, var)
        info = self.modules[module]
        own_prefix = ''
        own_deps = []
        for node in info['tree'].body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == var for t in node.targets):
                if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == 'APIRouter':
                    for kw in node.value.keywords:
                        if kw.arg == 'prefix':
                            own_prefix = literal(kw.value)
                        if kw.arg == 'dependencies':
                            own_deps.append(ast.unparse(kw.value))
        base = prefix + own_prefix
        deps = list(dependencies) + own_deps
        rows = []
        for node in info['tree'].body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for deco in node.decorator_list:
                    if not (isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute)
                            and ast.unparse(deco.func.value) == var and deco.func.attr in HTTP):
                        continue
                    route_path = base + literal(deco.args[0])
                    if not design_path(route_path):
                        continue
                    explicit = sorted({x.args[0].value for x in ast.walk(node)
                                       if isinstance(x, ast.Call) and ast.unparse(x.func) in {'require_permission', 'enforce_permission'}
                                       and x.args and isinstance(x.args[0], ast.Constant) and isinstance(x.args[0].value, str)})
                    default_deps = [ast.unparse(x) for x in [*node.args.defaults, *node.args.kw_defaults]
                                    if x is not None and 'Depends' in ast.unparse(x)]
                    text = '\n'.join(info['source'].splitlines()[node.lineno-1:node.end_lineno])
                    rows.append({'method': deco.func.attr.upper(), 'path': route_path,
                                 'handler': module + '.' + node.name, 'evidence': self.evidence(module, node),
                                 'registration': self.evidence(module, deco),
                                 'dependencies': deps + default_deps, 'explicit_permissions': explicit,
                                 'summary': next((literal(k.value) for k in deco.keywords if k.arg == 'summary'), ''),
                                 'calls': self.calls(module, node),
                                 'endpoint_guards': [{'evidence': f"{info['path']}:{node.lineno+i}", 'code': line.strip()}
                                     for i, line in enumerate(text.splitlines()) if re.search(r'role|_student\(|_require|_assert|scope|batch|tenant|no_permission', line, re.I)],
                                 'operation': '读取（仍需检查服务副作用）' if deco.func.attr in {'get','head','options'} else '写入或动作（导出也用提交方法）',
                                 'sensitive': '涉及学生/论文/成绩/审计，按对象再裁决' if re.search(r'student|material|final|proposal|review|grade|archive|download|export|audit|taskbook|defense', route_path) else '批次/题目/配置；仍需租户与范围检查'})
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                if isinstance(call.func, ast.Attribute) and ast.unparse(call.func.value) == var and call.func.attr == 'include_router':
                    target = self.resolve(module, call.args[0])
                    child_module, child_var = target.rsplit('.', 1)
                    if child_module not in self.modules:
                        continue
                    kw = {k.arg: k.value for k in call.keywords}
                    extra = [ast.unparse(kw['dependencies'])] if 'dependencies' in kw else []
                    rows.extend(self.router(child_module, child_var, base + (literal(kw['prefix']) if 'prefix' in kw else ''),
                                            deps + extra, stack + ((module, var),)))
        return rows


def permission_data():
    c = constants('backend/app/core/graduation_permissions.py')
    codes = c['GRADUATION_PERMISSION_CODES'] | {'graduationDesign.topic.submit'}
    generic = c['GRADUATION_ENDPOINT_PERMISSIONS']
    overrides = c['GRADUATION_ENDPOINT_PERMISSION_OVERRIDES']
    extension_path = 'backend/app/modules/graduation/services/graduation_permission_extensions.py'
    tree = ast.parse(read(extension_path))
    fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'register_graduation_permission_extensions')
    env = {}
    for node in fn.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                env[node.targets[0].id] = literal(node.value, env)
            except (ValueError, KeyError):
                pass
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == '_register':
            module, code, *names = [literal(x, env) for x in node.value.args]
            overrides.update({f'{module}.{n}': code for n in names})
    generic['submit_gd_topic_review'] = 'graduationDesign.topic.submit'
    overrides['graduation_topic.submit_gd_topic_review'] = 'graduationDesign.topic.submit'
    return codes, generic, overrides, c['GRADUATION_DYNAMIC_PERMISSION_ENDPOINTS']


def patches(sources):
    rows = []
    for module, info in sources.modules.items():
        if not module.startswith(GD + '.services.'):
            continue
        if not re.search(r'def (?:install\w*|_install_\w+)\(', info['source']):
            continue
        for node in ast.walk(info['tree']):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute):
                        head = ast.unparse(target).split('.')[0]
                        imported = sources.imports_at(module, node.lineno).get(head, '')
                        if imported not in sources.modules and imported not in {'app.core.permissions', 'app.core.graduation_permissions'} and head != 'module':
                            continue
                        rows.append({'target': sources.resolve(module, target),
                                     'replacement': sources.resolve(module, node.value),
                                     'expression': ast.unparse(node), 'evidence': sources.evidence(module, node)})
            if isinstance(node, ast.Call) and ast.unparse(node.func) in {'event.listen', 'setattr'}:
                rows.append({'target': ast.unparse(node.func), 'expression': ast.unparse(node),
                             'evidence': sources.evidence(module, node)})
    return rows


def self_check():
    assert matches('graduationDesign.grade.view', {'*.view'})
    assert not matches('graduationDesign.grade.publish', {'*.view'})
    assert not matches('graduationDesign.gradeEvil.view', {'graduationDesign.grade.*'})
    assert literal(ast.parse('{f"x.{a}" for a in ("read", "write")}', mode='eval').body) == {'x.read', 'x.write'}
    try:
        literal(ast.parse('__import__("socket")', mode='eval').body)
    except ValueError:
        pass
    else:
        raise AssertionError('常量解释器不应执行导入')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    self_check()
    assert (ROOT / 'backend/app/core/permissions.py').is_file(), '必须位于完整仓库内'
    codes, generic, overrides, dynamic = permission_data()
    action_codes = set(codes)
    catalogs = {}
    for path in sorted((ROOT/'shared/contracts').glob('permission-catalog*.json')):
        raw = read(path.relative_to(ROOT))
        catalogs[path.name] = sorted(set(re.findall(r'"(graduationDesign\.[A-Za-z.]+)"', raw)))
    codes |= set().union(*map(set, catalogs.values()))
    role_values = constants('backend/app/core/permissions.py')['ROLE_PERMISSIONS']
    nav = json.loads(read('shared/contracts/navigation-surface-contract.json'))
    menus = [x for x in nav['surfaces'] if x['moduleKey'] == 'graduationDesign' and not x['hidden'] and not x['disabled']]
    if not menus:
        menus = [x for x in nav['surfaces'] if x['groupLabel'] == '毕业设计中心' and not x['hidden'] and not x['disabled']]
    workspace_path = 'frontend/src/modules/graduation/config/graduationWorkspaces.js'
    workspace = read(workspace_path)
    manager_block = re.search(r'export const GRADUATION_MANAGER_KEYS = \[(.*?)\]', workspace, re.S)
    assert manager_block, '管理者菜单规则已改变'
    manager_keys = re.findall(r"'(graduationDesign\.[^']+)'", manager_block.group(1))
    leaves = {}
    for number, line in enumerate(workspace.splitlines(), 1):
        match = re.search(r"\{ label: '([^']+)', path: '([^']+)'", line)
        if match:
            leaves[(match.group(1), match.group(2))] = (number, 'menuRequiresAny: MANAGER' in line)
    for menu in menus:
        number, manager_only = leaves[(menu['label'], menu['path'])]
        menu['menuRequiresAny'] = manager_keys if manager_only else []
        menu['source_evidence'] = f'{workspace_path}:{number}'
    groups = list(dict.fromkeys(x['workspaceLabel'] for x in menus))
    roles = {}
    for role, label in ROLES.items():
        patterns = role_values[role]
        expanded = sorted(code for code in codes if matches(code, patterns))
        if matches('graduationDesign.topic.create', patterns) and 'graduationDesign.topic.submit' not in expanded:
            expanded.append('graduationDesign.topic.submit')
            expanded.sort()
        visible = [m for m in menus if (not m['permissionKey'] or matches(m['permissionKey'], expanded))
                   and (not m['permissionAny'] or any(matches(p, expanded) for p in m['permissionAny']))
                   and (not m['menuRequiresAny'] or any(matches(p, expanded) for p in m['menuRequiresAny']))
                   and all(matches(p, expanded) for p in m['permissionAll'])]
        roles[role] = {'label': label, 'static_patterns': sorted(patterns),
                       'static_permissions': expanded if role != 'SCHOOL_ADMIN' else None,
                       'static_menu_groups': {g: [x for x in visible if x['workspaceLabel'] == g] for g in groups} if role != 'SCHOOL_ADMIN' else None,
                       'static_menu_count': len(visible) if role != 'SCHOOL_ADMIN' else None,
                       'runtime_permissions': None, 'runtime_menus': None,
                       'runtime_status': '学生本人端点不使用管理端角色码授权；关系数据未核实' if role == 'STUDENT' else '需模板数据，未计算；无角色上下文时才可使用静态后备，学校管理员仍读模板',
                       'runtime_additions': '临时授权、导师/评阅/秘书/专家关系自动身份未计算'}
    src = Sources()
    mobile_module = GD + '.services.graduation_mobile_teacher_service'
    mobile_node = src.functions[mobile_module + '._review_submit'][1]
    mobile_calls = src.calls(mobile_module, mobile_node)
    assert GD + '.services.graduation_review_service.submit_review' in mobile_calls
    assert not any('graduation_defense_score_service.submit_review' in x for x in mobile_calls), '局部导入别名串线'
    archive_module = GD + '.routers.graduation_archive_sensitive_router'
    archive_node = src.functions[archive_module + '.file_record'][1]
    assert GD + '.materials.manifest_service.file_archive' in src.calls(archive_module, archive_node), '模块别名未解析'
    roots = [
        (GD + '.routers.' + name, ['教职工', '模块授权', 'require_graduation_request_permission'])
        for name in ['graduation_p0_guard', 'graduation_sensitive_router', 'graduation_archive_sensitive_router',
                     'graduation_material_sensitive_router', 'graduation', 'graduation_material_center']
    ]
    roots.append((GD + '.routers.graduation_extension', ['教职工', '模块授权', '端点显式权限']))
    roots += [(GD + '.routers.' + name, ['教职工', '模块授权', 'require_graduation_request_permission'])
              for name in ['graduation_batch', 'graduation_student', 'graduation_topic', 'graduation_topic_round',
                           'graduation_topic_change', 'graduation_mentor', 'graduation_student_eval', 'graduation_risk',
                           'graduation_template', 'graduation_more']]
    roots += [('app.api.v1.' + name, deps) for name, deps in [
        ('mobile_graduation_extension_teacher', ['教职工', '模块授权', '端点显式权限']),
        ('mobile_graduation_teacher_context', ['教职工', '模块授权', 'require_mobile_graduation_request_permission']),
        ('mobile_graduation_material_center', ['require_mobile_graduation_request_permission']),
        ('mobile_graduation_guard', []), ('mobile', ['require_mobile_graduation_request_permission']),
        ('student_portal_graduation_guard', []), ('platform_integrity', [])]]
    roots.append(('app.student_portal.router', ['学生门户商业模块门禁（见商业表面补装器）']))
    registration = ast.parse(read('backend/app/api/v1/route_registration.py'))
    register_gd = next(n for n in registration.body if isinstance(n, ast.FunctionDef) and n.name == 'register_graduation_routes')
    registered = []
    for node in register_gd.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == 'api_router.include_router':
            registered.append(ast.unparse(node.value.args[0]).removesuffix('.router'))
        elif isinstance(node, ast.For) and isinstance(node.iter, ast.Tuple):
            registered.extend(ast.unparse(x) for x in node.iter.elts)
    assert registered == [m.rsplit('.', 1)[-1] for m, _ in roots if m.startswith(GD)], '模块注册顺序改变，须重新追踪'
    routes = []
    mobile_map = constants('backend/app/core/mobile_graduation_permissions.py')['MOBILE_GRADUATION_ENDPOINT_PERMISSIONS']
    for module, deps in roots:
        routes.extend(src.router(module, prefix='/api/v1', dependencies=deps))
    for row in routes:
        short = '.'.join(row['handler'].split('.')[-2:])
        name = row['handler'].split('.')[-1]
        row['catalog_mapping'] = overrides.get(short) or (generic.get(name) if row['handler'].startswith(GD) else mobile_map.get(name))
        row['dynamic_permission'] = short in dynamic or (name == 'review_material' and 'mobile' in row['path'])
        row['permissions'] = row['explicit_permissions'] or ([row['catalog_mapping']] if row['catalog_mapping'] else [])
        row['permission_status'] = '按材料种类动态判定' if row['dynamic_permission'] else ('已提取' if row['permissions'] else '学生本人/对象门禁或另域权限：须读服务，不推测动作码')
    table = defaultdict(list)
    normalized = defaultdict(list)
    for row in routes:
        key = row['method'] + ' ' + row['path']
        table[key].append(row['handler'])
        normalized[re.sub(r'\{[^}]+\}', '{}', key)].append({'key': key, 'handler': row['handler']})
    snapshot = json.loads(read('backend/tests/fixtures/graduation_route_snapshot.json'))
    expected = {k: v for k, v in snapshot.items() if design_path(k)}
    actual = {k: v[0] for k, v in table.items() if design_path(k)}
    diff = {'method': '仅源码注册链推导；未导入应用、未运行测试',
            'missing': sorted(set(expected) - set(actual)), 'added': sorted(set(actual) - set(expected)),
            'changed': {k: {'snapshot': expected[k], 'source': actual[k]} for k in sorted(set(expected) & set(actual)) if expected[k] != actual[k]},
            'exact_duplicates': {k: v for k, v in table.items() if len(v) > 1},
            'parameter_name_collisions': {k: v for k, v in normalized.items() if len(v) > 1},
            'excluded_other_domains': {k:v for k,v in snapshot.items() if not design_path(k)}}
    functions = {}
    for name, (module, node) in src.functions.items():
        if not (module.startswith(GD) or module.startswith('app.student_portal.services.graduation')
                or module in {m for m, _ in roots} or module.startswith('app.services.mobile_')
                or module == 'app.services._mobile_teacher_service_impl'):
            continue
        info = src.modules[module]
        lines = info['source'].splitlines()
        fragments = [{'evidence': f"{info['path']}:{i+1}", 'code': lines[i].strip()}
                     for i in range(node.lineno-1, node.end_lineno)
                     if re.search(r'assert_|ensure_|require_|scope|tenant_id|\.status\s*=|audit|version|recus|回避|查重|审核人|提交人', lines[i], re.I)]
        functions[name] = {'evidence': src.evidence(module, node), 'end_line': node.end_lineno,
                           'calls': src.calls(module, node), 'scope_state_audit_evidence': fragments}
    models = []
    for file in ['graduation.py','graduation_extension.py','graduation_material.py','graduation_review_evidence.py']:
        path = 'backend/app/models/' + file
        for node in ast.parse(read(path)).body:
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, ast.Assign) and any(isinstance(t,ast.Name) and t.id == '__tablename__' for t in child.targets):
                        models.append({'model':node.name,'table':literal(child.value),'evidence':ref(path,node)})
        for node in ast.walk(ast.parse(read(path))):
            if isinstance(node, ast.Call) and ast.unparse(node.func) == 'sa.Table' and node.args:
                models.append({'model':'表元数据（非声明模型类）','table':literal(node.args[0]),'evidence':ref(path,node)})
    source_paths = sorted({x['path'] for x in src.modules.values()} |
                          {'backend/app/core/permissions.py','backend/app/core/graduation_permissions.py',
                           'backend/app/core/mobile_graduation_permissions.py','backend/app/api/v1/route_registration.py',
                           'frontend/src/modules/graduation/routes.js', workspace_path,
                           'backend/tests/fixtures/graduation_route_snapshot.json',
                           'shared/contracts/navigation-surface-contract.json'} |
                          {'shared/contracts/' + name for name in catalogs})
    result = {'source_commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
              'boundary':'只读静态取证；数据库、模板实值、运行时路由、浏览器、业务与权限实测均未验证',
              'source_hashes': {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths},
              'permission_codes': sorted(codes), 'action_permission_codes':sorted(action_codes),
              'catalog_only_codes':sorted(codes-action_codes),
              'permission_catalogs': catalogs, 'roles':roles, 'menus':menus,
              'action_mapping':constants('backend/app/modules/graduation/routers/graduation.py')['_ACTION_PERMISSION_MAP'],
              'route_roots':roots,'routes':routes,'snapshot_diff':diff,'runtime_patches':patches(src),
              'resolved_bindings':{name:src.canonical(name) for name in src.functions if src.canonical(name) != name},
              'functions':functions,'models':models,
              'test_files':[p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'backend/tests').glob('*graduation*.py'))],
              'self_check':'常量解释器拒绝导入；通配符边界；同名局部服务导入隔离；模块别名到材料归档；注册顺序断言通过',
              'analysis_limits':'仅静态候选调用图；含分支与回调，不证明运行时全部执行。闭包保存的旧函数、任意动态反射及数据库模板不推测。'}
    assert len(menus) == 29 and len(groups) == 8, '菜单基线改变，请核查而非静默沿用旧结论'
    assert roles['GRADUATION_ADMIN']['static_permissions'] == roles['GD_COLLEGE_ADMIN']['static_permissions']
    assert all(p in codes for r in routes if r['handler'].startswith(GD) for p in r['permissions'])
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'提交号':result['source_commit'],'权限码':len(codes),'菜单':len(menus),'菜单组':len(groups),
                      '接口记录':len(routes),'模型表':len(models),'运行时替换记录':len(result['runtime_patches']),
                      '快照缺失':len(diff['missing']),'快照新增':len(diff['added']),'处理函数变化':len(diff['changed']),
                      '同结构路径冲突':len(diff['parameter_name_collisions']), '输出':str(OUT)},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
