#!/usr/bin/env python3
"""Read-only M0 reference index. Candidates are not resolved data ownership.

Index AST model names/import aliases, explicit table strings and enclosing
symbols. ORM, raw SQL, JSON indirection and dynamic dispatch still require
review. Never use reference counts or module path labels as delete selectors.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path
import re


def load_check(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def module_path(path):
    if not path.startswith('backend/'):
        return None
    parts = Path(path).with_suffix('').parts[1:]
    return '.'.join(parts[:-1] if parts[-1] == '__init__' else parts)


def index_references(repo: Path, inventory: dict) -> dict:
    models = inventory.get('models')
    if not models:
        raise ValueError('MISSING_MODEL_INVENTORY')
    names, qualified = defaultdict(list), {}
    for model in models:
        names[model['model']].append(model['table'])
        qualified[(module_path(model['path']), model['model'])] = model['table']
    known_tables = {model['table'] for model in models}
    result, unresolved_imports, dynamic_sites = [], [], []
    for path in sorted((repo / 'backend/app').rglob('*.py')):
        if path.is_symlink() or not path.resolve().is_relative_to(repo.resolve()):
            raise ValueError('UNSAFE_SOURCE')
        relative = path.relative_to(repo).as_posix()
        source = path.read_text(encoding='utf-8-sig')
        tree = ast.parse(source, filename=relative)
        aliases, modules = {}, {}
        own_module = module_path(relative)
        for model in models:
            if model['path'] == relative:
                aliases[model['model']] = model['table']
        # Alias map is file-scoped: local rebinding is reported, not silently
        # promoted to resolved runtime ownership or an executable relation.
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        modules[alias.asname] = alias.name
                    else:
                        modules[alias.name.split('.')[0]] = alias.name.split('.')[0]
            elif isinstance(node, ast.ImportFrom):
                origin = node.module or ''
                if node.level:
                    package = own_module.split('.')[:-1] if path.name != '__init__.py' else own_module.split('.')
                    origin = '.'.join(package[:len(package) - node.level + 1] + ([origin] if origin else []))
                for alias in node.names:
                    local = alias.asname or alias.name
                    table = qualified.get((origin, alias.name))
                    if origin == 'app.models' and len(names.get(alias.name, [])) == 1:
                        table = names[alias.name][0]
                    if table:
                        aliases[local] = table
                    else:
                        modules[local] = origin + '.' + alias.name
                        if alias.name in names or alias.name == '*':
                            unresolved_imports.append({'path': relative, 'line': node.lineno, 'name': alias.name, 'from': origin})
        class Visitor(ast.NodeVisitor):
            def __init__(self):
                self.scope = []
                self.ancestors = []
            def visit(self, node):
                self.ancestors.append(node)
                super().visit(node)
                self.ancestors.pop()
            def generic_scope(self, node):
                self.scope.append(node.name)
                self.generic_visit(node)
                self.scope.pop()
            visit_FunctionDef = generic_scope
            visit_AsyncFunctionDef = generic_scope
            visit_ClassDef = generic_scope
            def emit(self, node, table, kind):
                calls = [ast.unparse(parent.func) for parent in self.ancestors if isinstance(parent, ast.Call)]
                result.append({'table': table, 'path': relative, 'line': node.lineno,
                    'symbol': '.'.join(self.scope) or '<module>', 'kind': kind,
                    'enclosingCall': calls[-1] if calls else None,
                    'referenceResolvedOnlySyntactically': True, 'reviewStatus': 'CANDIDATE', 'purgeAuthorized': False})
            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load) and node.id in aliases:
                    self.emit(node, aliases[node.id], 'MODEL_SYMBOL')
            def visit_Attribute(self, node):
                dotted = ast.unparse(node).split('.')
                if len(dotted) >= 2 and dotted[0] in modules:
                    expanded = modules[dotted[0]].split('.') + dotted[1:]
                    table = qualified.get(('.'.join(expanded[:-1]), expanded[-1]))
                    if table:
                        self.emit(node, table, 'QUALIFIED_MODEL')
                self.generic_visit(node)
            def visit_Constant(self, node):
                if isinstance(node.value, str):
                    for table in sorted(set(re.findall(r'\bt_[A-Za-z0-9_]+\b', node.value)) & known_tables):
                        self.emit(node, table, 'TABLE_STRING_REVIEW')
            def visit_Call(self, node):
                name = ast.unparse(node.func)
                if name in {'getattr', '__import__', 'importlib.import_module'}:
                    dynamic_sites.append({'path': relative, 'line': node.lineno, 'symbol': '.'.join(self.scope) or '<module>', 'call': name})
                self.generic_visit(node)
        Visitor().visit(tree)
    unique = {(r['table'], r['path'], r['line'], r['symbol'], r['kind']): r for r in result}
    result = sorted(unique.values(), key=lambda r: (r['table'], r['path'], r['line'], r['kind']))
    by_table = defaultdict(list)
    for r in result:
        by_table[r['table']].append(r)
    records = []
    for model in models:
        refs = by_table[model['table']]
        consumers = [r for r in refs if r['path'] != model['path']]
        records.append({'table': model['table'], 'declaration': {'path': model['path'], 'symbol': model['model'], 'line': model['startLine']},
            'tenantScope': 'DIRECT_FIELD_CANDIDATE' if model['tenantScopedSyntactic'] else 'PARENT_OR_GLOBAL_REVIEW',
            'logicalIdFieldsToReview': model['logicalIdFieldsToReview'], 'referenceSites': len(consumers),
            'candidateConsumerFiles': sorted({r['path'] for r in consumers}), 'ownershipClass': 'UNKNOWN',
            'consumerClosure': 'UNRESOLVED', 'purgeAuthorized': False})
    return {'schemaVersion': 1, 'sourceSha': inventory.get('sourceSha'), 'sourceManifestHash': inventory['sourceManifestHash'],
        'evidenceLevel': 'STATIC_REFERENCE_CANDIDATES', 'resources': records, 'references': result,
        'unresolvedImports': unresolved_imports, 'dynamicDispatchSites': dynamic_sites,
        'summary': {'resourceCount': len(records), 'referenceSites': len(result),
                    'candidateConsumerFiles': len({r['path'] for r in result}), 'referenceKinds': dict(Counter(r['kind'] for r in result)),
                    'resourcesWithoutExternalReferences': [r['table'] for r in records if r['referenceSites'] == 0]},
        'limitations': ['AST imports may be rebound/shadowed; all sites remain candidates.',
            'Dynamic table construction, raw SQL interpolation, JSON IDs, background dispatch and external copies require manual review.',
            'No reference found is not proof of no consumers. Frontend/worker execution is not validated by this scan.'],
        'm0Complete': False, 'deletionAuthorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--inventory', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--expected-head', required=True)
    args = parser.parse_args()
    repo, output = args.repo.resolve(strict=True), args.output.resolve()
    if output.is_relative_to(repo) or output.exists():
        parser.error('output must be a new file outside the repository')
    tool = load_check('module-commercial-inventory')
    verify = load_check('module-commercial-reconcile').verify_source
    source = json.loads(args.inventory.read_text(encoding='utf-8'))
    if tool.git_read(repo, 'rev-parse', 'HEAD') != args.expected_head or tool.git_read(repo, 'status', '--porcelain'):
        parser.error('expected clean exact-head checkout')
    verify(repo, source, args.expected_head)
    result = index_references(repo, source)
    verify(repo, source, args.expected_head)
    if tool.git_read(repo, 'rev-parse', 'HEAD') != args.expected_head or tool.git_read(repo, 'status', '--porcelain'):
        parser.error('source changed while indexing')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result['summary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
